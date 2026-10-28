# app/services/quiz_service.py
import json
import logging
import os
import random
import uuid
import re
from typing import Any, Dict, List, Optional

from app.rag.retriever import Retriever
from app.services.gemini_service import (
    AIAuthenticationError,
    AIResponseError,
    AIServiceError,
    AITimeoutError,
    GeminiService,
)
from app.services.question_bank_service import QuestionBankService
from app.services.settings_manager import SettingsManager
from app.services.token_budget import TokenBudget

logger = logging.getLogger(__name__)


class QuizError(Exception):
    """Lỗi chung từ QuizService."""

    pass


class QuizParseError(QuizError):
    """Lỗi không thể trích xuất hoặc parse JSON từ phản hồi AI."""

    pass


class QuizValidationError(QuizError):
    """Lỗi dữ liệu đề thi không đáp ứng schema hoặc yêu cầu."""

    pass


class QuizGenerationError(QuizError):
    """Lỗi tạo đề thất bại sau khi đã thử tất cả các bước/retry."""

    pass


class QuizService:

    def __init__(self, retriever: Retriever, gemini_service: GeminiService = None):
        self.retriever = retriever
        self.settings_manager = SettingsManager()
        self.token_budget = TokenBudget(budget=8000)
        self.qb_service = QuestionBankService()

        current_api_key = self.settings_manager.get_api_key()

        if gemini_service:
            self.gemini_service = gemini_service
            if current_api_key:
                self.gemini_service.set_api_key(current_api_key)
        else:
            self.gemini_service = GeminiService(api_key=current_api_key)

        self.max_context_chunks = 10

    def extract_json_from_response(self, raw_response: str) -> Any:
        if (
            not raw_response
            or not isinstance(raw_response, str)
            or not raw_response.strip()
        ):
            raise QuizParseError("Phản hồi từ AI rỗng hoặc không có dữ liệu.")

        text = raw_response.strip()

        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        first_brace = text.find("{")
        first_bracket = text.find("[")

        start_pos = -1
        if first_brace != -1 and first_bracket != -1:
            start_pos = min(first_brace, first_bracket)
        elif first_brace != -1:
            start_pos = first_brace
        elif first_bracket != -1:
            start_pos = first_bracket

        if start_pos != -1:
            substring = text[start_pos:]
            decoder = json.JSONDecoder()
            try:
                obj, _ = decoder.raw_decode(substring)
                return obj
            except json.JSONDecodeError:
                pass

            last_brace = text.rfind("}")
            last_bracket = text.rfind("]")
            end_pos = max(last_brace, last_bracket)

            if end_pos > start_pos:
                candidate = text[start_pos : end_pos + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    pass

        raise QuizParseError("Phản hồi từ AI không chứa cấu trúc JSON hợp lệ.")

    def normalize_quiz_data(self, data: Any) -> Dict[str, Any]:
        if not isinstance(data, (dict, list)):
            raise QuizValidationError(
                "Dữ liệu sau khi parse không phải là JSON object hoặc array."
            )

        exam_title = "Đề kiểm tra"
        subject_id = "default_subject"
        questions_raw = []

        if isinstance(data, list):
            questions_raw = data
        elif isinstance(data, dict):
            exam_title = data.get("exam_title") or data.get("title") or "Đề kiểm tra"
            subject_id = data.get("subject_id") or "default_subject"

            if "questions" in data and isinstance(data["questions"], list):
                questions_raw = data["questions"]
            elif "quiz" in data and isinstance(data["quiz"], list):
                questions_raw = data["quiz"]
            elif "items" in data and isinstance(data["items"], list):
                questions_raw = data["items"]
            elif "data" in data:
                d_val = data["data"]
                if isinstance(d_val, list):
                    questions_raw = d_val
                elif isinstance(d_val, dict):
                    questions_raw = (
                        d_val.get("questions")
                        or d_val.get("quiz")
                        or d_val.get("items")
                        or []
                    )

        normalized_questions = []
        labels_map = ["A", "B", "C", "D", "E", "F"]

        for idx, q in enumerate(questions_raw, start=1):
            if not isinstance(q, dict):
                continue

            q_id = str(q.get("id", f"q_{uuid.uuid4().hex[:8]}"))
            q_text = str(
                q.get("question") or q.get("text") or q.get("content") or ""
            ).strip()

            if not q_text:
                continue

            raw_type = str(q.get("type", "")).lower()
            if "essay" in raw_type or "tự luận" in raw_type:
                q_type = "essay"
            elif (
                "mc" in raw_type or "trắc nghiệm" in raw_type or "multiple" in raw_type
            ):
                q_type = "multiple_choice"
            else:
                if "model_answer" in q or "grading_rubric" in q:
                    q_type = "essay"
                else:
                    q_type = "multiple_choice"

            normalized_options_dict = {}
            normalized_options_list = []
            correct_ans = ""

            if q_type == "multiple_choice":
                raw_options = q.get("options") or q.get("choices") or q.get("answers")
                if isinstance(raw_options, dict):
                    for k, v in raw_options.items():
                        label = str(k).strip().upper()
                        text_val = str(v).strip()
                        normalized_options_dict[label] = text_val
                        normalized_options_list.append(
                            {"label": label, "text": text_val}
                        )
                elif isinstance(raw_options, list):
                    for i_opt, item in enumerate(raw_options):
                        if isinstance(item, dict):
                            lbl = (
                                str(
                                    item.get("label")
                                    or item.get("key")
                                    or labels_map[
                                        i_opt if i_opt < len(labels_map) else 0
                                    ]
                                )
                                .strip()
                                .upper()
                            )
                            txt = str(
                                item.get("text")
                                or item.get("value")
                                or item.get("content")
                                or ""
                            ).strip()
                        else:
                            lbl = (
                                labels_map[i_opt]
                                if i_opt < len(labels_map)
                                else f"OPT_{i_opt}"
                            )
                            txt = str(item).strip()
                            if (
                                len(txt) > 2
                                and txt[1] in [".", ":", ")"]
                                and txt[0].upper() in labels_map
                            ):
                                lbl = txt[0].upper()
                                txt = txt[2:].strip()
                        normalized_options_dict[lbl] = txt
                        normalized_options_list.append({"label": lbl, "text": txt})

                raw_corr = (
                    q.get("correct_answer")
                    or q.get("correct")
                    or q.get("answer")
                    or q.get("correct_option")
                )
                if isinstance(raw_corr, int):
                    if 0 <= raw_corr < len(labels_map):
                        correct_ans = labels_map[raw_corr]
                elif isinstance(raw_corr, str):
                    c_str = raw_corr.strip()
                    if c_str.upper() in normalized_options_dict:
                        correct_ans = c_str.upper()
                    else:
                        c_first = c_str[0].upper() if c_str else ""
                        if c_first in normalized_options_dict:
                            correct_ans = c_first
                        elif c_str in normalized_options_dict.values():
                            for k_opt, v_opt in normalized_options_dict.items():
                                if v_opt == c_str:
                                    correct_ans = k_opt
                                    break

            raw_source = q.get("source")
            normalized_source = {}
            if isinstance(raw_source, dict):
                normalized_source = {
                    "document": str(
                        raw_source.get("document")
                        or raw_source.get("source")
                        or raw_source.get("file")
                        or ""
                    ).strip(),
                    "page": raw_source.get("page", 1),
                    "chapter": str(raw_source.get("chapter") or "").strip(),
                }
            elif isinstance(raw_source, str):
                normalized_source = {
                    "document": raw_source.strip(),
                    "page": 1,
                    "chapter": "Tất cả chương",
                }
            else:
                normalized_source = {
                    "document": "Tài liệu học tập",
                    "page": 1,
                    "chapter": "Tất cả chương",
                }

            norm_q = {
                "id": q_id,
                "type": q_type,
                "question": q_text,
                "options": normalized_options_dict,
                "options_list": normalized_options_list,
                "correct_answer": correct_ans,
                "explanation": str(q.get("explanation") or "").strip(),
                "difficulty": str(q.get("difficulty") or "Trung bình").strip(),
                "source": normalized_source,
            }

            if q_type == "essay":
                norm_q["model_answer"] = str(
                    q.get("model_answer") or q.get("answer") or ""
                ).strip()
                kp = q.get("key_points")
                norm_q["key_points"] = (
                    kp if isinstance(kp, list) else ([str(kp)] if kp else [])
                )
                gr = q.get("grading_rubric")
                norm_q["grading_rubric"] = (
                    gr if isinstance(gr, list) else ([str(gr)] if gr else [])
                )

            normalized_questions.append(norm_q)

        return {
            "exam_title": str(exam_title),
            "subject_id": str(subject_id),
            "questions": normalized_questions,
        }

    def validate_single_question(
        self, q: Dict[str, Any], valid_doc_names: Optional[set] = None
    ) -> bool:
        if not isinstance(q, dict):
            return False

        q_text = str(q.get("question") or "").strip()
        if not q_text:
            return False

        q_type = q.get("type")
        if q_type == "multiple_choice":
            opts = q.get("options")
            if not isinstance(opts, dict) or not opts:
                return False

            if not all(
                k in opts and str(opts[k]).strip() for k in ["A", "B", "C", "D"]
            ):
                return False

            corr = q.get("correct_answer")
            if not corr or corr not in opts:
                return False

        elif q_type == "essay":
            if not str(q.get("model_answer") or "").strip():
                return False
        else:
            return False

        if valid_doc_names:
            raw_source = q.get("source")
            if isinstance(raw_source, dict):
                docname = str(raw_source.get("document") or "").strip()
            else:
                docname = str(raw_source or "").strip()
            if not docname:
                return False
            doc_l = docname.lower()
            if not any(
                str(v).lower() in doc_l or doc_l in str(v).lower()
                for v in valid_doc_names
            ):
                return False

        return True

    def validate_quiz_data(
        self,
        data: Dict[str, Any],
        expected_mc_count: Optional[int] = None,
        expected_essay_count: Optional[int] = None,
        quiz_type: Optional[str] = None,
        valid_doc_names: Optional[set] = None,
    ) -> None:
        if not isinstance(data, dict):
            raise QuizValidationError("Dữ liệu đề thi không phải là JSON object.")

        questions = data.get("questions")
        if not isinstance(questions, list) or not questions:
            raise QuizValidationError(
                "Đề thi không có danh sách câu hỏi hợp lệ (rỗng)."
            )

        for idx, q in enumerate(questions, start=1):
            if not self.validate_single_question(q, valid_doc_names):
                raise QuizValidationError(f"Câu {idx} không đáp ứng schema hợp lệ.")

        mc_n = sum(1 for q in questions if q.get("type") == "multiple_choice")
        essay_n = sum(1 for q in questions if q.get("type") == "essay")

        if expected_mc_count is not None and mc_n != expected_mc_count:
            raise QuizValidationError(
                f"Số câu trắc nghiệm không khớp (nhận {mc_n}, cần"
                f" {expected_mc_count})."
            )
        if expected_essay_count is not None and essay_n != expected_essay_count:
            raise QuizValidationError(
                f"Số câu tự luận không khớp (nhận {essay_n}, cần"
                f" {expected_essay_count})."
            )

    def _build_quiz_prompt(
        self,
        subject_name: str,
        subject_id: str,
        chapter: str,
        quiz_type: str,
        mc_count: int,
        essay_count: int,
        difficulty: str,
        context_str: str,
    ) -> str:
        return f"""You are an expert AI exam builder. You must respond strictly in valid JSON format.

Nhiệm vụ: Dựa vào các đoạn tài liệu nguồn RAG, hãy sinh đúng {mc_count} câu trắc nghiệm và {essay_count} câu tự luận cho môn: "{subject_name}" (ID: {subject_id}).

Phạm vi kiến thức: {chapter}
Độ khó: {difficulty}

QUY TẮC BẮT BUỘC VỀ ĐÁP ÁN TRẮC NGHIỆM:
1. Mỗi lựa chọn trắc nghiệm (A, B, C, D) phải diễn đạt trọn vẹn, đầy đủ nội dung từ tài liệu.
2. TUYỆT ĐỐI KHÔNG ĐƯỢC tự ý cắt ngắn hoặc thêm dấu ba chấm (...) ở cuối các phương án.
3. Lời giải thích (explanation) viết ngắn gọn 1-2 câu.
4. Trả về đúng 1 JSON object hợp lệ.

CẤU TRÚC JSON MẪU:
{{
  "exam_title": "Đề kiểm tra {subject_name} - {chapter}",
  "subject_id": "{subject_id}",
  "questions": [
    {{
      "type": "multiple_choice",
      "question": "Nội dung câu hỏi trắc nghiệm?",
      "options": {{"A": "Phương án A trọn vẹn", "B": "Phương án B trọn vẹn", "C": "Phương án C trọn vẹn", "D": "Phương án D trọn vẹn"}},
      "correct_answer": "A",
      "explanation": "Giải thích ngắn gọn.",
      "difficulty": "{difficulty}",
      "source": {{"document": "Tài liệu môn học", "page": 1, "chapter": "{chapter}"}}
    }}
  ]
}}

TÀI LIỆU NGUỒN (CONTEXT RAG):
{context_str}
"""

    def load_fallback_data(self, subject_id: str) -> List[Dict[str, Any]]:
        fallback_items = []
        data_dir = os.path.join(os.getcwd(), "data")

        faq_path = os.path.join(data_dir, "faq.json")
        if os.path.exists(faq_path):
            try:
                with open(faq_path, "r", encoding="utf-8") as f:
                    faq_data = json.load(f)
                    for item in faq_data:
                        s_id = item.get("subject_id", "")
                        if (
                            s_id == subject_id
                            or subject_id in s_id
                            or s_id in subject_id
                        ):
                            fallback_items.append(
                                {
                                    "question": item.get("question"),
                                    "answer": item.get("answer"),
                                    "sources": item.get("sources", []),
                                }
                            )
            except Exception as e:
                logger.error(f"[QUIZ FALLBACK] Lỗi đọc {faq_path}: {e}")

        cache_path = os.path.join(data_dir, "chat_cache.json")
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                    for key, val in cache_data.items():
                        if key.startswith(f"{subject_id}_") or subject_id in key:
                            parts = key.split("_all_")
                            q_text = parts[1] if len(parts) > 1 else key
                            fallback_items.append(
                                {
                                    "question": q_text,
                                    "answer": val.get("answer"),
                                    "sources": val.get("sources", []),
                                }
                            )
            except Exception as e:
                logger.error(f"[QUIZ FALLBACK] Lỗi đọc {cache_path}: {e}")

        return fallback_items

    def generate_quiz_from_fallback(
        self,
        subject_id: str,
        subject_name: str,
        mc_count: int,
        essay_count: int,
    ) -> List[Dict[str, Any]]:
        """Tự động chuyển đổi dữ liệu từ data/faq.json và data/chat_cache.json

        thành câu hỏi trắc nghiệm & tự luận chuẩn schema khi AI hết token.
        """
        raw_items = self.load_fallback_data(subject_id)
        if not raw_items:
            return []

        questions = []
        random.shuffle(raw_items)

        for idx, item in enumerate(raw_items):
            q_text = item.get("question")
            ans_text = item.get("answer", "")
            sources = item.get("sources", [])

            if not q_text or not ans_text:
                continue

            # 1. Làm sạch văn bản: Loại bỏ ký tự Markdown (**), gạch đầu dòng và đoạn chào mừng dư thừa
            clean_ans = re.sub(r"\*\*|\*|#|- |-", "", ans_text).strip()
            # Loại bỏ các câu kết/chào mừng ví dụ: "Em hãy học hỏi..."
            clean_ans = re.sub(
                r"Em hãy.*|Chúc em.*|Thầy.*|Cố vấn.*", "", clean_ans, flags=re.DOTALL
            ).strip()

            doc_name = (
                sources[0].get("source") if sources else f"Giáo trình {subject_name}"
            )
            page_num = sources[0].get("page") if sources else 1

            current_mc = len([q for q in questions if q["type"] == "multiple_choice"])
            current_essay = len([q for q in questions if q["type"] == "essay"])

            # Đối với dữ liệu từ Chat, ưu tiên chuyển thành CÂU HỎI TỰ LUẬN để giữ trọn vẹn kiến thức
            if current_essay < essay_count:
                questions.append(
                    {
                        "id": f"fb_es_{uuid.uuid4().hex[:6]}",
                        "type": "essay",
                        "question": q_text,
                        "model_answer": clean_ans,
                        "difficulty": "Trung bình",
                        "source": {
                            "document": doc_name,
                            "page": page_num,
                            "chapter": "Tất cả chương",
                        },
                    }
                )
            elif current_mc < mc_count:
                # Nếu cần trắc nghiệm, cắt lấy 1-2 câu đầu tiên cốt lõi nhất làm đáp án A
                sentences = [
                    s.strip() for s in clean_ans.split(".") if len(s.strip()) > 10
                ]
                core_ans = (
                    ". ".join(sentences[:2]) + "." if sentences else clean_ans[:150]
                )

                questions.append(
                    {
                        "id": f"fb_mc_{uuid.uuid4().hex[:6]}",
                        "type": "multiple_choice",
                        "question": q_text,
                        "options": {
                            "A": core_ans,
                            "B": "Là hình thức tổ chức xã hội dựa trên sở hữu tư nhân về tư liệu sản xuất.",
                            "C": "Là giai đoạn phát triển tự phát không có sự dẫn dắt của hệ tư tưởng tiến bộ.",
                            "D": "Là mô hình kinh tế tập trung bao cấp hoàn toàn do các tập đoàn quản lý.",
                        },
                        "correct_answer": "A",
                        "explanation": f"Theo giáo trình: {core_ans}",
                        "difficulty": "Trung bình",
                        "source": {
                            "document": doc_name,
                            "page": page_num,
                            "chapter": "Tất cả chương",
                        },
                    }
                )

            if len(questions) >= (mc_count + essay_count):
                break

        return questions

    def generate_quiz(
        self,
        subject_id: str,
        subject_name: str,
        selected_documents: List[str],
        chapter: str,
        quiz_type: str,
        mc_count: int = 10,
        essay_count: int = 0,
        difficulty: str = "Trung bình",
        specific_quiz_file: Optional[str] = None,
    ) -> Dict[str, Any]:
        requested_mc = (
            min(max(mc_count, 0), 20) if "trắc nghiệm" in quiz_type.lower() else 0
        )
        requested_essay = (
            min(max(essay_count, 0), 3) if "tự luận" in quiz_type.lower() else 0
        )

        total_requested = requested_mc + requested_essay

        if total_requested <= 0:
            requested_mc = 5
            total_requested = 5

        logger.info(
            "[QUIZ] generate_quiz ưu tiên file: subject_id=%s, chapter=%s,"
            " file=%s, mc_req=%d, essay_req=%d",
            subject_id,
            chapter,
            specific_quiz_file,
            requested_mc,
            requested_essay,
        )

        if not selected_documents:
            logger.error(
                "[QUIZ] generate_quiz: selected_documents rỗng cho subject_id=%s.",
                subject_id,
            )
            return {
                "exam_id": str(uuid.uuid4()),
                "exam_title": f"Đề kiểm tra {subject_name}",
                "subject_id": subject_id,
                "questions": [],
                "error": (
                    "Không có tài liệu nào được chọn. Vui lòng chọn ít nhất một tài"
                    " liệu."
                ),
            }

        bank_mc_questions = []
        if requested_mc > 0:
            try:
                bank_mc_questions = (
                    self.qb_service.get_questions_for_exam(
                        subject_id=subject_id,
                        chapter=chapter,
                        quiz_type="trắc nghiệm",
                        count=requested_mc,
                    )
                    or []
                )
            except Exception as e:
                logger.error(
                    f"[QUIZ] Lỗi lấy câu hỏi trắc nghiệm từ Question Bank: {e}"
                )
                bank_mc_questions = []

        bank_essay_questions = []
        if requested_essay > 0:
            try:
                bank_essay_questions = (
                    self.qb_service.get_questions_for_exam(
                        subject_id=subject_id,
                        chapter=chapter,
                        quiz_type="tự luận",
                        count=requested_essay,
                    )
                    or []
                )
            except Exception as e:
                logger.error(f"[QUIZ] Lỗi lấy câu hỏi tự luận từ Question Bank: {e}")
                bank_essay_questions = []

        existing_questions = bank_mc_questions + bank_essay_questions
        seen_fps = {
            self.qb_service.generate_fingerprint(str(q.get("question") or ""))
            for q in existing_questions
            if isinstance(q, dict) and str(q.get("question") or "").strip()
        }

        needed_mc = requested_mc - len(bank_mc_questions)
        needed_essay = requested_essay - len(bank_essay_questions)

        logger.info(
            f"[QUIZ] Lấy từ Question Bank / File: {len(bank_mc_questions)} TN,"
            f" {len(bank_essay_questions)} TL. Số câu cần AI sinh thêm:"
            f" {needed_mc} TN, {needed_essay} TL."
        )

        ai_generated_questions = []
        exam_title = f"Đề kiểm tra {subject_name}"
        last_ai_error = None

        if needed_mc > 0 or needed_essay > 0:
            retrieved_docs = []
            try:
                if hasattr(self.retriever, "retrieve_for_quiz"):
                    retrieved_docs = self.retriever.retrieve_for_quiz(
                        subject_id=subject_id,
                        document_ids=selected_documents,
                        chapter=chapter,
                        top_k=15,
                    )
                else:
                    retrieved_docs = self.retriever.retrieve(
                        query=f"Kiến thức môn {subject_name} chương {chapter}",
                        top_k=10,
                        subject_id=subject_id,
                        allowed_sources=selected_documents,
                    )
            except Exception as e:
                logger.exception(
                    "[QUIZ] Retrieval error cho subject=%s docs=%s",
                    subject_id,
                    selected_documents,
                )
                retrieved_docs = []

            context_parts = []
            valid_doc_names = set()
            for idx, doc in enumerate(retrieved_docs, start=1):
                if isinstance(doc, dict):
                    content = doc.get("text", doc.get("content", ""))
                    meta = doc.get("metadata", {})
                    source_doc = meta.get("source", doc.get("source", "Tài liệu"))
                    page = meta.get("page", doc.get("page", 1))
                    doc_chap = meta.get("chapter", chapter)
                else:
                    content = getattr(doc, "text", getattr(doc, "content", ""))
                    meta = getattr(doc, "metadata", {})
                    source_doc = meta.get("source", getattr(doc, "source", "Tài liệu"))
                    page = meta.get("page", getattr(doc, "page", 1))
                    doc_chap = meta.get("chapter", chapter)

                if source_doc:
                    valid_doc_names.add(str(source_doc))

                context_parts.append(
                    f"[{idx}] Tài liệu: {source_doc} (Trang {page},"
                    f" {doc_chap})\nNội dung: {content}"
                )

            prompt_template = self._build_quiz_prompt(
                subject_name=subject_name,
                subject_id=subject_id,
                chapter=chapter,
                quiz_type=quiz_type,
                mc_count=max(0, needed_mc),
                essay_count=max(0, needed_essay),
                difficulty=difficulty,
                context_str="",
            )

            optimized_chunks, final_ai_mc, final_ai_essay, estimates = (
                self.token_budget.optimize_request_parameters(
                    prompt_template=prompt_template,
                    context_parts=context_parts,
                    target_mc=max(0, needed_mc),
                    target_essay=max(0, needed_essay),
                    min_mc=min(5, max(0, needed_mc)),
                )
            )

            should_call_ai = True
            if not self.gemini_service.api_key:
                logger.warning(
                    "[QUIZ] API key chưa được cấu hình. Bỏ qua gọi AI sinh thêm."
                )
                should_call_ai = False

            if (
                estimates["total_tokens"] > self.token_budget.budget
                and final_ai_mc < 1
                and final_ai_essay < 1
            ):
                logger.info("[QUIZ TOKEN] Vượt ngân sách Token. Bỏ qua gọi AI.")
                should_call_ai = False

            if should_call_ai and (final_ai_mc > 0 or final_ai_essay > 0):
                context_str = "\n\n".join(optimized_chunks)
                ai_prompt = self._build_quiz_prompt(
                    subject_name=subject_name,
                    subject_id=subject_id,
                    chapter=chapter,
                    quiz_type=quiz_type,
                    mc_count=final_ai_mc,
                    essay_count=final_ai_essay,
                    difficulty=difficulty,
                    context_str=context_str,
                )

                best_partial = []
                max_attempts = 2
                for attempt in range(1, max_attempts + 1):
                    try:
                        raw_response = self.gemini_service.generate(
                            ai_prompt,
                            response_mime_type="application/json",
                        )
                        parsed_data = self.extract_json_from_response(raw_response)
                        normalized_data = self.normalize_quiz_data(parsed_data)
                        raw_qs = normalized_data.get("questions", [])
                        valid_qs = [
                            q
                            for q in raw_qs
                            if self.validate_single_question(q, valid_doc_names)
                        ]
                        if len(valid_qs) > len(best_partial):
                            best_partial = valid_qs
                            if normalized_data.get("exam_title"):
                                exam_title = str(normalized_data["exam_title"])

                        ai_generated_questions = valid_qs
                        last_ai_error = None
                        break
                    except AIAuthenticationError as e:
                        last_ai_error = e
                        logger.warning("[QUIZ] Lỗi xác thực API Key AI.")
                        break
                    except AITimeoutError as e:
                        last_ai_error = e
                        logger.warning(
                            "[QUIZ] Timeout khi gọi AI (lần %d/%d)",
                            attempt,
                            max_attempts,
                        )
                    except (QuizParseError, QuizValidationError, AIServiceError) as e:
                        last_ai_error = e
                        logger.warning("[QUIZ] Phản hồi AI không hợp lệ: %s", e)
                    except Exception as e:
                        last_ai_error = e
                        logger.exception("[QUIZ] Lỗi khi gọi AI sinh câu hỏi: %s", e)

                if not ai_generated_questions and best_partial:
                    ai_generated_questions = best_partial

                if ai_generated_questions:
                    try:
                        self.qb_service.save_questions(
                            ai_generated_questions,
                            subject_id=subject_id,
                            default_chapter=chapter,
                        )
                    except Exception:
                        logger.exception(
                            "[QUIZ] Không lưu được câu hỏi mới vào Question Bank"
                        )

        combined_questions = list(existing_questions)

        for q in ai_generated_questions:
            if isinstance(q, dict) and str(q.get("question") or "").strip():
                fp = self.qb_service.generate_fingerprint(str(q.get("question") or ""))
                if fp and fp not in seen_fps:
                    seen_fps.add(fp)
                    combined_questions.append(q)

        rem_mc = requested_mc - len(
            [q for q in combined_questions if q.get("type") == "multiple_choice"]
        )
        rem_essay = requested_essay - len(
            [q for q in combined_questions if q.get("type") == "essay"]
        )

        if rem_mc > 0 or rem_essay > 0:
            logger.info(
                "[QUIZ FALLBACK] Đang nạp thêm câu hỏi dự phòng từ thư mục data/..."
            )
            fb_questions = self.generate_quiz_from_fallback(
                subject_id=subject_id,
                subject_name=subject_name,
                mc_count=max(0, rem_mc),
                essay_count=max(0, rem_essay),
            )
            for q in fb_questions:
                fp = self.qb_service.generate_fingerprint(str(q.get("question") or ""))
                if fp and fp not in seen_fps:
                    seen_fps.add(fp)
                    combined_questions.append(q)

        random.shuffle(combined_questions)

        if not combined_questions:
            detail = (
                str(last_ai_error)
                if last_ai_error
                else (
                    "Không tìm thấy dữ liệu trong file trắc nghiệm, Question Bank hoặc"
                    " RAG."
                )
            )
            raise QuizGenerationError(f"Không thể tạo bài kiểm tra. {detail}")

        return {
            "exam_id": str(uuid.uuid4()),
            "exam_title": exam_title,
            "subject_id": subject_id,
            "questions": combined_questions,
        }

    def generate_exam(
        self,
        subject_id: str,
        subject_name: str,
        selected_documents: List[str],
        chapter: str,
        quiz_type: str,
        mc_count: int = 10,
        essay_count: int = 0,
        specific_quiz_file: Optional[str] = None,
        difficulty: str = "Trung bình",
    ) -> Dict[str, Any]:
        return self.generate_quiz(
            subject_id=subject_id,
            subject_name=subject_name,
            selected_documents=selected_documents,
            chapter=chapter,
            quiz_type=quiz_type,
            mc_count=mc_count,
            essay_count=essay_count,
            difficulty=difficulty,
            specific_quiz_file=specific_quiz_file,
        )

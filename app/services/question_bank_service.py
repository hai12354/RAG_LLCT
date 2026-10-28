# app/services/question_bank_service.py
import json
import os
import re
import sys
import hashlib
import random
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def get_data_file_path(filename: str) -> str:
    """Xác định đường dẫn tuyệt đối chuẩn xác cho các file JSON nằm trong thư mục data/
    Hỗ trợ chuẩn 100% cho cả môi trường Dev và file .exe PyInstaller.
    """
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).resolve().parent
        internal_data = base_dir / "_internal" / "data" / filename
        if internal_data.exists():
            return str(internal_data)

        outer_data = base_dir / "data" / filename
        if outer_data.exists():
            return str(outer_data)

        return str(outer_data)

    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent
    return str(project_root / "data" / filename)


class QuestionBankService:
    def __init__(
        self,
        storage_path: Optional[str] = None,
        history_path: Optional[str] = None,
    ):
        self.storage_path = storage_path or get_data_file_path("question_bank.json")
        self.history_path = history_path or get_data_file_path("exam_history.json")
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        self.questions = self._load_storage()
        self.history = self._load_history()

    def _load_storage(self) -> List[Dict[str, Any]]:
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        flat_questions = []
                        for item in data:
                            if isinstance(item, dict) and "questions" in item:
                                for q in item["questions"]:
                                    if isinstance(q, dict):
                                        q["subject_id"] = item.get(
                                            "subject_id", "default"
                                        )
                                        flat_questions.append(q)
                            elif isinstance(item, dict) and "question" in item:
                                flat_questions.append(item)
                        return flat_questions
            except Exception as e:
                logger.error(f"Error loading question bank storage: {e}")
                return []
        return []

    def _load_history(self) -> List[Dict[str, Any]]:
        if os.path.exists(self.history_path):
            try:
                with open(self.history_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading exam history: {e}")
                return []
        return []

    def _save_storage(self):
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self.questions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Lỗi lưu Question Bank: {e}")

    def _save_history(self):
        try:
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Lỗi lưu lịch sử thi: {e}")

    @staticmethod
    def normalize_question_text(text: str) -> str:
        if not text:
            return ""
        norm = text.lower().strip()
        norm = re.sub(r"[^\w\s]", "", norm)
        norm = re.sub(r"\s+", " ", norm)
        return norm

    @classmethod
    def generate_fingerprint(cls, question_text: str) -> str:
        norm_text = cls.normalize_question_text(question_text)
        return hashlib.md5(norm_text.encode("utf-8")).hexdigest()

    def save_questions(
        self,
        questions: List[Dict[str, Any]],
        subject_id: str = "",
        default_chapter: str = "Tất cả chương",
    ) -> int:
        existing_fingerprints = {
            self.generate_fingerprint(q.get("question", ""))
            for q in self.questions
            if isinstance(q, dict) and "question" in q
        }

        saved_count = 0
        now_str = datetime.now().isoformat()

        for q in questions:
            if not isinstance(q, dict):
                continue
            q_text = q.get("question", "").strip()
            if not q_text:
                continue

            fp = self.generate_fingerprint(q_text)
            if fp in existing_fingerprints:
                logger.info(f"[QUESTION BANK] Bỏ qua câu trùng: '{q_text[:40]}...'")
                continue

            q_record = dict(q)
            q_record["fingerprint"] = fp
            q_record["id"] = q.get("id") or fp
            q_record["subject_id"] = (
                subject_id or q.get("subject_id") or "default_subject"
            )

            source_info = q.get("source", {})
            if isinstance(source_info, dict):
                chap = source_info.get("chapter") or default_chapter
            else:
                chap = default_chapter

            q_record["chapter"] = chap
            q_record["created_at"] = q.get("created_at") or now_str
            q_record["usage_count"] = q.get("usage_count", 0)
            q_record["last_used_at"] = q.get("last_used_at", "")

            self.questions.append(q_record)
            existing_fingerprints.add(fp)
            saved_count += 1

        if saved_count > 0:
            self._save_storage()
            logger.info(
                f"[QUESTION BANK] Đã thêm {saved_count} câu hỏi mới vào Question Bank."
            )

        return saved_count

    def get_questions_for_exam(
        self,
        subject_id: str,
        chapter: Optional[str] = None,
        quiz_type: str = "trắc nghiệm",
        count: int = 5,
    ) -> List[Dict[str, Any]]:
        if count <= 0:
            return []

        candidates = []
        is_mc_req = (
            "trắc nghiệm" in quiz_type.lower() or "multiple_choice" in quiz_type.lower()
        )
        is_essay_req = "tự luận" in quiz_type.lower() or "essay" in quiz_type.lower()

        for q in self.questions:
            if not isinstance(q, dict):
                continue

            q_subj = str(q.get("subject_id") or "")
            if subject_id and q_subj != subject_id:
                continue

            q_chap = q.get("chapter", "Tất cả chương")
            if (
                chapter
                and chapter != "Tất cả chương"
                and q_chap != "Tất cả chương"
                and q_chap != chapter
            ):
                continue

            q_type = q.get("type", "multiple_choice")
            if is_mc_req and not is_essay_req and q_type != "multiple_choice":
                continue
            if is_essay_req and not is_mc_req and q_type != "essay":
                continue

            candidates.append(q)

        if not candidates:
            return []

        candidates.sort(key=lambda x: x.get("usage_count", 0))

        min_usage = candidates[0].get("usage_count", 0)
        low_usage_candidates = [
            c for c in candidates if c.get("usage_count", 0) <= min_usage + 2
        ]
        random.shuffle(low_usage_candidates)

        selected = low_usage_candidates[:count]

        now_str = datetime.now().isoformat()
        for q in selected:
            q["usage_count"] = q.get("usage_count", 0) + 1
            q["last_used_at"] = now_str

        self._save_storage()
        return selected

    def save_exam(self, exam_data: Dict[str, Any]):
        if not isinstance(exam_data, dict):
            return
        questions = exam_data.get("questions", [])
        subject_id = exam_data.get("subject_id", "default_subject")
        if questions:
            self.save_questions(questions, subject_id=subject_id)

    def get_exams_by_subject(self, subject_id: str) -> List[Dict[str, Any]]:
        return [q for q in self.questions if q.get("subject_id") == subject_id]

    def save_exam_history(self, history_record: Dict[str, Any]) -> None:
        """Lưu lịch sử nộp bài thi của người dùng vào data/exam_history.json."""
        if not isinstance(history_record, dict):
            return

        if "submitted_at" not in history_record:
            history_record["submitted_at"] = datetime.now().isoformat()

        current_history = []
        if os.path.exists(self.history_path):
            try:
                with open(self.history_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        current_history = data
            except Exception as e:
                logger.error(f"Lỗi đọc file exam_history.json: {e}")

        current_history.append(history_record)

        try:
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(current_history, f, ensure_ascii=False, indent=2)
            self.history = current_history
            logger.info("Đã lưu lịch sử bài thi thành công.")
        except Exception as e:
            logger.error(f"Lỗi khi ghi file exam_history.json: {e}")

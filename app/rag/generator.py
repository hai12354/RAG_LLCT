# app/rag/generator.py
import re
from typing import Any, Dict, List
from app.rag.retriever import Retriever
from app.services.gemini_service import GeminiService

# Prompt đóng vai Thầy giáo Lý luận Chính trị giảng bài
TEACHER_RAG_PROMPT = """Bạn là Cố vấn AI / Thầy giáo giảng dạy các môn Lý luận Chính trị.

YÊU CẦU TRÌNH BÀY (RẤT QUAN TRỌNG - BẮT BUỘC TUÂN THỦ):
1. Xưng "Thầy" - gọi "em" ân cần, gần gũi.
2. Trả lời NGẮN GỌN, TRỌNG TÂM, CÔ ĐỌNG (dưới 200 từ).
3. Không viết dài dòng lê thê, không lặp lại câu hỏi.
4. QUY TẮC CĂN LỀ & TRÌNH BÀY NGAY HÀNG THẲNG LỐI:
   - Các ý chính trình bày bằng các dòng gạch đầu dòng (-) thẳng hàng tuyệt đối.
   - Mỗi gạch đầu dòng (-) nằm trên 1 dòng riêng biệt, không thụt lề bất ngờ hay chèn khoảng trắng thừa ở đầu dòng.
   - Các dòng chữ viết liên tục, không tự ý xuống dòng vô lý ở giữa câu.
5. KHÔNG dùng bảng (table '|'), KHÔNG dùng ký tự markdown phức tạp như '###', '>', '**' lòng vòng.
6. Kết bài bằng 1 câu động viên/gợi mở ngắn gọn trên một dòng riêng.

GIÁO TRÌNH GỐC:
{context}

CÂU HỎI CỦA HỌC SINH:
{question}

BÀI GIẢNG CỦA THẦY:
"""


def format_clean_text(text: str) -> str:
    """Xóa bỏ các khoảng trắng thụt lề dư thừa ở đầu mỗi dòng giúp văn bản ngay hàng thẳng lối 100%."""
    if not text:
        return ""

    # Tách từng dòng, làm sạch khoảng trắng thụt lề ở đầu và cuối dòng
    lines = [line.strip() for line in text.splitlines()]

    # Loại bỏ các dòng rỗng liên tiếp (chỉ giữ tối đa 1 dòng trống giữa các đoạn)
    cleaned_lines = []
    for line in lines:
        if line or (cleaned_lines and cleaned_lines[-1] != ""):
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


class RAGGenerator:

    def __init__(self, retriever: Retriever, gemini_service: GeminiService):
        self.retriever = retriever
        self.gemini_service = gemini_service

    def verify_and_correct_answer(
        self, question: str, draft_answer: str, context: str
    ) -> str:
        """AI Fact-Checker: Kiểm tra câu trả lời nháp so với giáo trình gốc,

        đảm bảo tính chính xác nhưng vẫn giữ nguyên văn phong Thầy giáo giảng bài.
        """
        check_prompt = f"""
Bạn là chuyên gia thẩm định nội dung môn Lý luận chính trị.
Hãy kiểm tra bài giảng nháp dưới đây so với GIÁO TRÌNH GỐC.

GIÁO TRÌNH GỐC:
{context}

CÂU HỎI:
{question}

BÀI GIẢNG NHÁP:
{draft_answer}

YÊU CẦU:
1. So sánh bài giảng nháp với GIÁO TRÌNH GỐC.
2. Nếu bài giảng nháp đã hoàn toàn chính xác theo giáo trình, hãy giữ nguyên nội dung đó.
3. Nếu bài giảng nháp có điểm sai lệch về mặt kiến thức, hãy TỰ SỬA LẠI sao cho chuẩn xác 100% theo giáo trình.
4. VĂN PHONG: Giữ nguyên cách xưng hô "Thầy - em" ân cần, phong thái giảng giải gợi mở. Không viết lời nhận xét của người thẩm định, không dùng trích dẫn số [1].

BÀI GIẢNG CHUẨN XÁC NẤT CỦA THẦY:
"""
        try:
            verified_answer = self.gemini_service.generate(check_prompt)
            return (
                format_clean_text(verified_answer) if verified_answer else draft_answer
            )
        except Exception:
            return draft_answer

    def answer(
        self,
        question: str,
        top_k: int = 3,
        subject_id: str = None,
        document_type: str = None,
        selected_documents: list[str] = None,
        enable_fact_check: bool = False,
    ) -> Dict[str, Any]:
        """Thực hiện pipeline RAG: Tìm kiếm context -> Tạo prompt Thầy giáo -> Gọi LLM -> (Fact Check) -> Trả về kết quả."""
        if not question or not question.strip():
            return {
                "question": question,
                "answer": (
                    "Chào em, em chưa nhập câu hỏi nào cả. Em cần Thầy hỗ trợ phần"
                    " kiến thức nào nào?"
                ),
                "sources": [],
            }

        retrieved_docs = []
        doc_type_filter = (
            document_type if document_type and document_type != "all" else None
        )

        # 1. Truy xuất dữ liệu theo 3 tầng Fallback
        if hasattr(self.retriever, "retrieve"):
            retrieved_docs = self.retriever.retrieve(
                query=question,
                top_k=top_k,
                subject_id=subject_id,
                document_type=doc_type_filter,
                allowed_sources=selected_documents,
            )

        if (
            not retrieved_docs
            and doc_type_filter
            and hasattr(self.retriever, "retrieve")
        ):
            retrieved_docs = self.retriever.retrieve(
                query=question,
                top_k=top_k,
                subject_id=subject_id,
                document_type=None,
                allowed_sources=selected_documents,
            )

        if not retrieved_docs and hasattr(self.retriever, "retrieve"):
            retrieved_docs = self.retriever.retrieve(
                query=question,
                top_k=top_k,
                subject_id=None,
                document_type=None,
                allowed_sources=None,
            )

        if not retrieved_docs:
            return {
                "question": question,
                "answer": (
                    "Thầy đã tra cứu trong các tài liệu hiện có nhưng chưa tìm thấy"
                    " nội dung phù hợp cho câu hỏi này. Em thử chọn lại môn học hoặc"
                    " đổi cách đặt câu hỏi xem sao nhé!"
                ),
                "sources": [],
            }

        # Ghép context và trích xuất nguồn
        context_parts = []
        sources = []

        for idx, doc in enumerate(retrieved_docs, start=1):
            if isinstance(doc, dict):
                content = doc.get(
                    "text", doc.get("content", doc.get("page_content", ""))
                )
                metadata = doc.get("metadata", {})
                source_name = doc.get(
                    "source", metadata.get("source", "Tài liệu Lý luận chính trị")
                )
                page_num = doc.get("page", metadata.get("page", 1))
                score = doc.get("score", 0.0)
            else:
                content = getattr(
                    doc,
                    "text",
                    getattr(doc, "page_content", getattr(doc, "content", "")),
                )
                metadata = getattr(doc, "metadata", {})
                source_name = getattr(
                    doc, "source", metadata.get("source", "Tài liệu Lý luận chính trị")
                )
                page_num = getattr(doc, "page", metadata.get("page", 1))
                score = getattr(doc, "score", 0.0)

            cleaned_content = " ".join(content.split())
            context_parts.append(f"[{idx}] {cleaned_content}")
            sources.append(
                {"source": source_name, "page": page_num, "score": float(score)}
            )

        context_str = "\n\n".join(context_parts)

        # 2. Tạo Prompt Thầy giáo và sinh bài giảng
        prompt = TEACHER_RAG_PROMPT.format(context=context_str, question=question)
        try:
            raw_generated_answer = self.gemini_service.generate(prompt)
            # Làm sạch và căn lề văn bản ngay sau khi gọi AI
            generated_answer = format_clean_text(raw_generated_answer)
        except Exception as e:
            raise e

        # 3. Bước KIỂM DUYỆT VÀ TỰ SỬA (Fact-Check / Self-Correction)
        if enable_fact_check:
            generated_answer = self.verify_and_correct_answer(
                question=question, draft_answer=generated_answer, context=context_str
            )

        return {
            "question": question,
            "answer": generated_answer,
            "sources": sources,
        }

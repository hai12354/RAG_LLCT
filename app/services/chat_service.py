# app/services/chat_service.py
import json
import logging
import os
import re
import sys
from pathlib import Path
from PySide6.QtCore import QThread, Signal

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


CACHE_FILE = get_data_file_path("chat_cache.json")
FAQ_FILE = get_data_file_path("faq.json")


class RAGWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, rag_generator, question, subject_id, document_type):
        super().__init__()
        self.rag_generator = rag_generator
        self.question = question
        self.subject_id = subject_id
        self.document_type = document_type

    def run(self):
        try:
            result = self.rag_generator.answer(
                self.question,
                top_k=3,
                subject_id=self.subject_id,
                document_type=self.document_type,
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class ChatService:

    def __init__(self):
        self.cache_file = CACHE_FILE
        self.faq_file = FAQ_FILE
        self.cache_data = self.load_cache_and_seed_faq()

    def normalize_text(self, text: str) -> str:
        """Làm sạch câu hỏi: viết thường, loại bỏ dấu câu và khoảng trắng thừa."""
        if not text:
            return ""
        text = text.lower().strip()
        text = re.sub(r"[^\w\s]", "", text)
        return re.sub(r"\s+", " ", text)

    def load_cache_and_seed_faq(self):
        """Đọc file chat_cache.json. Nếu trống hoặc chưa có, tự động nạp sẵn dữ liệu từ data/faq.json."""
        cache_items = {}

        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    cache_items = json.load(f)
            except Exception as e:
                logger.error(f"[CACHE] Lỗi đọc chat_cache.json: {e}")

        if os.path.exists(self.faq_file):
            try:
                with open(self.faq_file, "r", encoding="utf-8") as f:
                    faq_list = json.load(f)
                    for item in faq_list:
                        subj = item.get("subject_id", "all")
                        doc_type = item.get("document_type", "all")
                        q_raw = item.get("question", "")
                        q_norm = self.normalize_text(q_raw)

                        cache_key = f"{subj}_{doc_type}_{q_norm}"

                        if cache_key not in cache_items:
                            cache_items[cache_key] = {
                                "answer": item.get("answer", ""),
                                "sources": item.get("sources", []),
                            }
                logger.info(
                    f"[FAQ] Đã nạp thành công câu hỏi FAQ mẫu từ {self.faq_file}."
                )
            except Exception as e:
                logger.error(
                    f"[FAQ] Không đọc được file faq.json tại {self.faq_file}: {e}"
                )
        else:
            logger.warning(
                f"[FAQ] Không tìm thấy file faq.json tại đường dẫn: {self.faq_file}"
            )

        return cache_items

    def save_cache(self):
        """Ghi Cache dữ liệu xuống file data/chat_cache.json."""
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[CACHE] Không lưu được file cache: {e}")

    def clear_cache(self):
        """Xóa sạch cache trong bộ nhớ và làm rỗng file chat_cache.json."""
        self.cache_data = {}
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
            logger.info(
                f"[CACHE] Đã xóa toàn bộ nội dung cache trong {self.cache_file}."
            )
        except Exception as e:
            logger.error(f"[CACHE] Không thể làm rỗng file cache: {e}")

    def get_cached_answer(self, subject_id, document_type, question):
        """Tra cứu câu trả lời đã lưu dựa theo subject_id và câu hỏi đã làm sạch."""
        norm_q = self.normalize_text(question)

        cache_key = f"{subject_id}_{document_type}_{norm_q}"
        if cache_key in self.cache_data:
            return self.cache_data[cache_key]

        fallback_key = f"{subject_id}_all_{norm_q}"
        if fallback_key in self.cache_data:
            return self.cache_data[fallback_key]

        return None

    def save_answer_to_cache(
        self, subject_id, document_type, question, answer, sources
    ):
        """CHỈ LƯU CACHE CHO CÁC CÂU TRẢ LỜI CÓ GIÁ TRỊ KIẾN THỨC VÀ CÓ TÀI LIỆU TRÍCH DẪN."""
        if not answer or not isinstance(answer, str):
            return

        # 1. Bắt buộc phải có tài liệu trích dẫn nguồn (RAG Sources)
        if not sources or len(sources) == 0:
            logger.info(
                "[CACHE] Bỏ qua không lưu cache do không có tài liệu nguồn trích dẫn."
            )
            return

        # 2. Loại bỏ các câu thông báo lỗi, giới hạn API hoặc không tìm thấy tài liệu
        invalid_keywords = [
            "chưa tìm thấy",
            "không tìm thấy",
            "không có thông tin",
            "chưa thể trả lời",
            "rate limit",
            "error code",
            "lỗi hệ thống",
            "thử chọn lại môn",
        ]

        ans_lower = answer.lower()
        if any(kw in ans_lower for kw in invalid_keywords):
            logger.info(
                "[CACHE] Bỏ qua không lưu cache cho câu phản hồi báo lỗi/không tìm thấy tài liệu."
            )
            return

        # 3. Câu trả lời quá ngắn (dưới 20 ký tự) thường không đủ giá trị kiến thức
        if len(answer.strip()) < 20:
            return

        norm_q = self.normalize_text(question)
        cache_key = f"{subject_id}_{document_type}_{norm_q}"

        self.cache_data[cache_key] = {"answer": answer, "sources": sources}
        self.save_cache()
        logger.info(
            f"[CACHE] Đã lưu câu trả lời chất lượng vào Cache: '{norm_q[:30]}...'"
        )

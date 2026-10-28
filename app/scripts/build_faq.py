# scripts/build_faq.py
import json
import os
import sys

# Xử lý đường dẫn tương thích EXE / Dev
if getattr(sys, "frozen", False):
    PROJECT_ROOT = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.rag.generator import RAGGenerator
from app.rag.retriever import Retriever
from app.services.gemini_service import GeminiService


def auto_fill_faq_sources():
    """Tự động điền nguồn thông qua RAGGenerator."""
    faq_path = os.path.join(PROJECT_ROOT, "data", "faq.json")

    if not os.path.exists(faq_path):
        faq_path = os.path.join(os.getcwd(), "data", "faq.json")

    if not os.path.exists(faq_path):
        print(f"Không tìm thấy file: {faq_path}")
        return

    try:
        with open(faq_path, "r", encoding="utf-8") as f:
            faq_data = json.load(f)
    except Exception as e:
        print(f"Lỗi đọc file FAQ: {e}")
        return

    # Khởi tạo RAG Pipeline
    try:
        retriever = Retriever(use_reranker=False)
        gemini_service = GeminiService()
        generator = RAGGenerator(retriever=retriever, gemini_service=gemini_service)
    except Exception as e:
        print(f"Lỗi khởi tạo RAG Pipeline: {e}")
        return

    print(f"Bắt đầu tự động tìm số trang cho {len(faq_data)} câu hỏi FAQ...")

    for i, item in enumerate(faq_data, 1):
        q = item.get("question")
        subj = item.get("subject_id")
        print(f"[{i}/{len(faq_data)}] Đang quét trang cho: '{q}'...")

        try:
            res = generator.answer(question=q, subject_id=subj, top_k=3)
            if res and res.get("sources"):
                item["sources"] = res["sources"]
        except Exception as e:
            print(f"   ⚠️ Lỗi khi quét câu hỏi '{q}': {e}")

    # Ghi lại kết quả vào file faq.json
    try:
        with open(faq_path, "w", encoding="utf-8") as f:
            json.dump(faq_data, f, ensure_ascii=False, indent=4)
        print(
            "✅ Đã tự động cập nhật xong toàn bộ tên file và số trang vào data/faq.json!"
        )
    except Exception as e:
        print(f"Lỗi khi ghi file FAQ: {e}")


if __name__ == "__main__":
    auto_fill_faq_sources()

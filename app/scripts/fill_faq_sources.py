# app/scripts/fill_faq_sources.py
import json
import os
import sys

# 1. Xử lý đường dẫn tương thích giữa môi trường Dev và file EXE (.exe)
if getattr(sys, "frozen", False):
    # Khi chạy từ file .exe đã đóng gói bằng PyInstaller
    PROJECT_ROOT = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
else:
    # Khi chạy file .py thông thường trong môi trường phát triển
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.rag.generator import RAGGenerator
from app.rag.retriever import Retriever
from app.services.gemini_service import GeminiService


def fill_sources_for_faq():
    """Tự động tìm kiếm nguồn trích dẫn và số trang từ ChromaDB để điền vào data/faq.json."""
    # Xác định đường dẫn file faq.json
    faq_path = os.path.join(PROJECT_ROOT, "data", "faq.json")

    # Nếu chạy EXE và file faq.json nằm ở thư mục hiện hành ngoài file .exe
    if not os.path.exists(faq_path):
        faq_path = os.path.join(os.getcwd(), "data", "faq.json")

    if not os.path.exists(faq_path):
        print(f"❌ Không tìm thấy file dữ liệu FAQ tại: {faq_path}")
        return

    try:
        with open(faq_path, "r", encoding="utf-8") as f:
            faq_data = json.load(f)
    except Exception as e:
        print(f"❌ Lỗi khi đọc file {faq_path}: {e}")
        return

    print("⏳ Đang khởi tạo Retriever và ChromaDB...")
    try:
        retriever = Retriever(use_reranker=False)
        gemini_service = GeminiService()
        generator = RAGGenerator(retriever=retriever, gemini_service=gemini_service)
    except Exception as e:
        print(f"❌ Lỗi khởi tạo RAG/ChromaDB: {e}")
        return

    updated_count = 0
    print(f"🔍 Bắt đầu quét nguồn cho {len(faq_data)} câu hỏi trong FAQ...\n")

    for idx, item in enumerate(faq_data, 1):
        q = item.get("question", "").strip()
        subj = item.get("subject_id")

        if not q:
            continue

        print(f"[{idx}/{len(faq_data)}] Đang tìm nguồn cho câu hỏi: '{q}'...")

        # Step 1: Lọc theo subject_id trước
        retrieved_docs = []
        if hasattr(retriever, "retrieve"):
            try:
                retrieved_docs = retriever.retrieve(query=q, top_k=3, subject_id=subj)
            except Exception as err:
                print(f"   ⚠️ Lỗi khi retrieve lượt 1: {err}")

        # Step 2: FALLBACK - Bỏ lọc subject_id nếu quét lượt 1 không ra kết quả
        if not retrieved_docs and hasattr(retriever, "retrieve"):
            try:
                retrieved_docs = retriever.retrieve(query=q, top_k=3, subject_id=None)
            except Exception as err:
                print(f"   ⚠️ Lỗi khi retrieve lượt 2 (fallback): {err}")

        sources = []
        seen = set()

        # Parse thông tin trích dẫn từ tài liệu trả về
        for doc in retrieved_docs:
            if isinstance(doc, dict):
                metadata = doc.get("metadata", {})
                src_name = doc.get(
                    "source", metadata.get("source", "Tài liệu Lý luận chính trị")
                )
                page_num = str(doc.get("page", metadata.get("page", 1)))
            else:
                metadata = getattr(doc, "metadata", {})
                src_name = getattr(
                    doc,
                    "source",
                    metadata.get("source", "Tài liệu Lý luận chính trị"),
                )
                page_num = str(getattr(doc, "page", metadata.get("page", 1)))

            identifier = (src_name, page_num)
            if identifier not in seen:
                seen.add(identifier)
                sources.append({"source": src_name, "page": page_num})

        if sources:
            item["sources"] = sources
            updated_count += 1
            print(f"   └─ ✅ Đã tìm thấy {len(sources)} nguồn trích dẫn.")
        else:
            print("   └─ ⚠️ Không tìm thấy nguồn phù hợp trong ChromaDB.")

    # Ghi đè cập nhật lại file data/faq.json
    try:
        os.makedirs(os.path.dirname(faq_path), exist_ok=True)
        with open(faq_path, "w", encoding="utf-8") as f:
            json.dump(faq_data, f, ensure_ascii=False, indent=2)
        print(
            f"\n🎉 Hoàn thành! Đã cập nhật trích dẫn cho {updated_count}/{len(faq_data)} câu hỏi vào {faq_path}."
        )
    except Exception as e:
        print(f"❌ Lỗi khi ghi file faq.json: {e}")


if __name__ == "__main__":
    fill_sources_for_faq()

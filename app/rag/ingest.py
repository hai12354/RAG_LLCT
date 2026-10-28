# app/rag/ingest.py
import json
import logging
import os
import time
from app.rag.document_loader import DocumentLoader, DocumentLoadError
from app.rag.chunker import TextChunker
from app.rag.embedding import EmbeddingService
from app.rag.vector_store import VectorStore
from app.rag.chapter_parser import parse_chapters_from_pages
from app.rag.convert_docx import read_docx_pages

logger = logging.getLogger(__name__)


class IngestError(Exception):
    """Lỗi khi đọc, chia chunk, embedding hoặc lưu vector."""


def _load_documents_catalog(docs_dir: str) -> dict:
    meta_path = os.path.join(docs_dir, "documents_meta.json")
    catalog = {}
    if not os.path.exists(meta_path):
        return catalog
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                filename = os.path.basename(item.get("filename") or "")
                if filename:
                    catalog[filename.lower()] = item
    except Exception:
        logger.exception("[INGEST] Không đọc được documents_meta.json")
    return catalog


def ingest_file(
    file_path: str,
    subject_id: str,
    document_type: str = "giao_trinh",
    persist_directory: str = "data/chroma",
    collection_name: str = "llct_documents",
    embedding_service: EmbeddingService = None,
    vector_store: VectorStore = None,
) -> dict:
    if not file_path or not os.path.exists(file_path):
        raise IngestError(f"Không tìm thấy file: {file_path}")

    if not subject_id:
        raise IngestError("Thiếu subject_id khi ingest tài liệu.")

    ext = os.path.splitext(file_path)[1].lower()
    filename = os.path.basename(file_path)

    # 1. Xử lý theo định dạng file
    if ext in [".docx", ".doc"]:
        try:
            pages_data = read_docx_pages(file_path)
            total_p = len(pages_data)
            text_p = total_p
            scanned_p = 0
        except Exception as e:
            raise IngestError(f"Lỗi đọc file Word '{filename}': {e}") from e
    elif ext == ".pdf":
        loader = DocumentLoader(os.path.dirname(file_path) or ".")
        try:
            pages_data, total_p, text_p, scanned_p = loader.load_pdf(
                file_path, raise_on_error=True
            )
        except DocumentLoadError as e:
            raise IngestError(str(e)) from e
    else:
        raise IngestError(
            f"Định dạng '{ext}' chưa được hỗ trợ. Hệ thống hỗ trợ PDF và Word (.docx)."
        )

    # 2. Nhận diện tiêu đề chương
    pages_data = parse_chapters_from_pages(pages_data)

    # 3. Tổng hợp danh sách các chương đọc được từ các trang
    found_chapters = list(
        dict.fromkeys(
            [
                p.get("metadata", {}).get("chapter", "").strip()
                for p in pages_data
                if p.get("metadata", {}).get("chapter")
            ]
        )
    )
    extracted_chapter = ", ".join(found_chapters[:3]) if found_chapters else ""

    # 4. Phân chia chunks và lưu Vector
    chunker = TextChunker()
    file_chunks = []
    for p_data in pages_data:
        if not p_data.get("text"):
            continue

        page_no = p_data.get("metadata", {}).get("page", 1)
        chapter_title = p_data.get("metadata", {}).get("chapter", "")

        extra_metadata = {
            "subject_id": subject_id,
            "document_type": document_type or "khac",
            "chapter": chapter_title,
        }

        chunks = chunker.split_text(
            p_data["text"], filename, page_no, extra_metadata=extra_metadata
        )
        file_chunks.extend(chunks)

    if not file_chunks:
        raise IngestError(f"Không trích xuất được nội dung chữ từ '{filename}'.")

    try:
        embedding_service = embedding_service or EmbeddingService()
        vector_store = vector_store or VectorStore(
            persist_directory=persist_directory, collection_name=collection_name
        )
        batch_size = 64
        for i in range(0, len(file_chunks), batch_size):
            batch_chunks = file_chunks[i : i + batch_size]
            batch_texts = [c["text"] for c in batch_chunks]
            batch_embeddings = embedding_service.embed_documents(batch_texts)
            vector_store.add_chunks(batch_chunks, batch_embeddings)
    except Exception as e:
        logger.exception("[INGEST] Lưu vector thất bại cho %s", filename)
        raise IngestError(
            f"Không lưu được vector vào ChromaDB cho '{filename}': {e}"
        ) from e

    return {
        "filename": filename,
        "chunk_count": len(file_chunks),
        "page_count": total_p,
        "text_pages": text_p,
        "scanned_pages": scanned_p,
        "chapter": extracted_chapter,
    }


def run_ingestion():
    docs_dir = "data/documents"
    loader = DocumentLoader(docs_dir)
    chunker = TextChunker()
    embedding_service = EmbeddingService()
    vector_store = VectorStore()
    catalog = _load_documents_catalog(docs_dir)

    print("====================================")
    print("LLCT RAG INGESTION")
    print("====================================\n")

    if not os.path.exists(docs_dir):
        print(f"ERROR: Thư mục {docs_dir} không tồn tại!")
        return False

    supported_files = [
        f for f in os.listdir(docs_dir) if f.lower().endswith((".pdf", ".docx", ".doc"))
    ]
    print(f"Documents found: {len(supported_files)}\n")

    if not supported_files:
        print("STOP: Không tìm thấy file PDF hay Word nào!")
        return False

    print("Processing:")
    total_pages_all = 0
    total_text_pages_all = 0
    total_scanned_pages_all = 0
    all_chunks = []

    for idx, filename in enumerate(supported_files, 1):
        file_path = os.path.join(docs_dir, filename)
        meta = catalog.get(filename.lower(), {})
        extra_metadata = {}
        if meta.get("subject_id"):
            extra_metadata["subject_id"] = meta["subject_id"]
        if meta.get("document_type"):
            extra_metadata["document_type"] = meta["document_type"]

        ext = os.path.splitext(filename)[1].lower()
        actual_pdf_path = file_path
        converted_pdf_created = False

        if ext in [".docx", ".doc"]:
            try:
                actual_pdf_path = read_docx_pages(file_path)
                converted_pdf_created = True
            except Exception as e:
                print(f"   Lỗi convert {filename}: {e}\n")
                continue

        pages_data, total_p, text_p, scanned_p = loader.load_pdf(actual_pdf_path)

        if converted_pdf_created and os.path.exists(actual_pdf_path):
            try:
                os.remove(actual_pdf_path)
            except Exception:
                pass

        total_pages_all += total_p
        total_text_pages_all += text_p
        total_scanned_pages_all += scanned_p

        pages_data = parse_chapters_from_pages(pages_data)

        file_chunks = []
        for p_data in pages_data:
            if p_data.get("text"):
                chunk_meta = dict(extra_metadata)
                chunk_meta["chapter"] = p_data.get("metadata", {}).get("chapter", "")

                chunks = chunker.split_text(
                    p_data["text"],
                    filename,
                    p_data.get("metadata", {}).get("page", 1),
                    extra_metadata=chunk_meta or None,
                )
                file_chunks.extend(chunks)

        all_chunks.extend(file_chunks)

        print(f"{idx}. {filename}")
        print(f"   Pages: {total_p}")
        print(f"   Text pages: {text_p}")
        print(f"   Chunks: {len(file_chunks)}\n")

    print("------------------------------------")
    print("TOTAL")
    print("------------------------------------")
    print(f"Files: {len(supported_files)}")
    print(f"Pages: {total_pages_all}")
    print(f"Text pages: {total_text_pages_all}")
    print(f"Scanned pages: {total_scanned_pages_all}")
    print(f"Chunks: {len(all_chunks)}")

    print("\nGenerating embeddings and storing into ChromaDB...")
    start_time = time.time()

    batch_size = 64
    for i in range(0, len(all_chunks), batch_size):
        batch_chunks = all_chunks[i : i + batch_size]
        batch_texts = [c["text"] for c in batch_chunks]
        batch_embeddings = embedding_service.embed_documents(batch_texts)
        vector_store.add_chunks(batch_chunks, batch_embeddings)
        print(
            f"Processed batch {i // batch_size + 1}/{(len(all_chunks) + batch_size - 1) // batch_size}"
        )

    print(f"Embedding dimension: {embedding_service.dimension}")
    print("Chroma collection: 'llct_documents'")
    print(f"Chroma records count: {vector_store.count()}")
    print(f"Time elapsed: {round(time.time() - start_time, 2)}s")
    print("\nStatus: PASS")
    return True


if __name__ == "__main__":
    run_ingestion()

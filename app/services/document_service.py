# app/services/document_service.py
import json
import logging
import os
from pathlib import Path
import shutil
import sys
import time
import uuid

from app.models.document import Document
from app.rag.ingest import IngestError, ingest_file

logger = logging.getLogger(__name__)

# Các định dạng tài liệu hỗ trợ tự động quét
SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".doc", ".txt")


def get_default_data_dir() -> str:
    """Xác định đường dẫn thư mục data/documents chuẩn cho cả Dev và PyInstaller .exe."""
    if getattr(sys, "frozen", False):
        # Môi trường chạy file .exe
        base_dir = Path(sys.executable).resolve().parent
    else:
        # Môi trường Dev Python
        base_dir = Path(__file__).resolve().parent.parent.parent

    data_dir = base_dir / "data" / "documents"
    data_dir.mkdir(parents=True, exist_ok=True)
    return str(data_dir)


class DocumentDuplicateError(ValueError):
    """Tài liệu đã tồn tại trong môn học."""


class DocumentService:

    def __init__(self, data_dir: str = None):
        # Nếu không truyền data_dir thì tự động lấy đường dẫn chuẩn theo môi trường
        self.data_dir = data_dir or get_default_data_dir()
        os.makedirs(self.data_dir, exist_ok=True)
        self.metadata_file = os.path.join(self.data_dir, "documents_meta.json")

        # Khởi tạo lười: chỉ nạp model embedding / mở ChromaDB khi thật sự cần
        self._embedding_service = None
        self._vector_store = None
        self._init_storage()

    # ------------------------------------------------------------------
    # Lưu trữ metadata & Đồng bộ 2 chiều (Auto Sync Add/Delete)
    # ------------------------------------------------------------------
    def _init_storage(self):
        if not os.path.exists(self.metadata_file):
            self._save_all([])

    def auto_scan_and_sync(self):
        """Tự động đồng bộ 2 chiều giữa file thực tế trên đĩa và metadata/ChromaDB:

        1. Xóa metadata + vector nếu file (.pdf, .docx, .doc, .txt) đã bị xóa khỏi ổ đĩa.
        2. Thêm mới metadata nếu có file tài liệu mới xuất hiện trong thư mục.
        """
        if not os.path.exists(self.data_dir):
            return

        docs = self._load_all()
        has_change = False

        # --- 1. CHIỀU XÓA: Loại bỏ tài liệu không còn file thực tế trên đĩa ---
        valid_docs = []
        for d in docs:
            file_p = getattr(d, "file_path", "") or os.path.join(
                self.data_dir, d.filename
            )
            if os.path.exists(file_p):
                valid_docs.append(d)
            else:
                # File đã bị xóa trên đĩa -> Xóa vector tương ứng trong ChromaDB
                source_name = os.path.basename(file_p)
                self._delete_vectors(source_name)
                has_change = True
                logger.info(
                    "[DOCUMENT] Đã xóa metadata của file không còn tồn tại: %s",
                    d.filename,
                )

        docs = valid_docs
        existing_paths = {
            os.path.normcase(os.path.abspath(d.file_path))
            for d in docs
            if hasattr(d, "file_path") and d.file_path
        }

        # --- 2. CHIỀU THÊM: Tự động quét các file tài liệu mới xuất hiện ---
        try:
            for filename in os.listdir(self.data_dir):
                ext = os.path.splitext(filename)[1].lower()
                if ext in SUPPORTED_EXTENSIONS:
                    full_path = os.path.abspath(os.path.join(self.data_dir, filename))

                    if os.path.normcase(full_path) not in existing_paths:
                        subject_id = "all"
                        clean_name = filename

                        if "__" in filename:
                            parts = filename.split("__", 1)
                            subject_id = parts[0]
                            clean_name = parts[1]

                        # Phân loại tài liệu
                        doc_type = "giao_trinh"
                        fn_lower = filename.lower()
                        if (
                            "trac-nghiem" in fn_lower
                            or "trac_nghiem" in fn_lower
                            or "cau-hoi" in fn_lower
                            or "cau_hoi" in fn_lower
                        ):
                            doc_type = "on_trac_nghiem"

                        new_doc = Document(
                            id=str(uuid.uuid4())[:8],
                            subject_id=subject_id,
                            filename=clean_name,
                            file_path=full_path,
                            document_type=doc_type,
                            chapter=f"Tài liệu: {clean_name}",
                            file_size=os.path.getsize(full_path),
                            page_count=1,
                            chunk_count=1,
                        )
                        docs.append(new_doc)
                        existing_paths.add(os.path.normcase(full_path))
                        has_change = True

            if has_change:
                self._save_all(docs)
                logger.info("[DOCUMENT] Đã tự động đồng bộ lại danh sách tài liệu!")
        except Exception as e:
            logger.warning(f"[DOCUMENT] Lỗi khi tự động quét file tài liệu: {e}")

    def _load_all(self) -> list[Document]:
        if not os.path.exists(self.metadata_file):
            return []
        try:
            with open(self.metadata_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                docs = [Document(**item) for item in data]
            for d in docs:
                self._repair_file_path(d)
            return docs
        except Exception:
            logger.exception("[DOCUMENT] Không đọc được %s", self.metadata_file)
            return []

    def _repair_file_path(self, doc: Document):
        """Dữ liệu cũ có thể lưu đường dẫn tuyệt đối sai.
        Nếu file thật nằm trong data_dir thì trỏ lại cho đúng.
        """
        path = getattr(doc, "file_path", "") or ""
        if path and os.path.exists(path):
            return
        names = []
        if path:
            names.append(os.path.basename(path))
        names.append(doc.filename)
        for name in names:
            candidate = os.path.abspath(os.path.join(self.data_dir, name))
            if os.path.exists(candidate):
                doc.file_path = candidate
                return

    def _save_all(self, docs: list[Document]):
        tmp = self.metadata_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump([d.to_dict() for d in docs], f, ensure_ascii=False, indent=4)
        os.replace(tmp, self.metadata_file)

    # ------------------------------------------------------------------
    # Vector store
    # ------------------------------------------------------------------
    def _get_embedding_service(self):
        if self._embedding_service is None:
            from app.rag.embedding import EmbeddingService

            self._embedding_service = EmbeddingService()
        return self._embedding_service

    def _get_vector_store(self):
        if self._vector_store is None:
            from app.rag.vector_store import VectorStore

            self._vector_store = VectorStore()
        return self._vector_store

    def _delete_vectors(self, source_name: str) -> bool:
        """Xóa mọi chunk có metadata source == source_name khỏi ChromaDB."""
        try:
            vs = self._get_vector_store()
            if hasattr(vs, "delete_by_source"):
                vs.delete_by_source(source_name)
                return True
            collection = getattr(vs, "collection", None)
            if collection is not None:
                collection.delete(where={"source": source_name})
                return True
            logger.error(
                "[DOCUMENT] VectorStore không có delete_by_source/collection, "
                "không xóa được vector của %s",
                source_name,
            )
        except Exception:
            logger.exception("[DOCUMENT] Xóa vector thất bại cho %s", source_name)
        return False

    # ------------------------------------------------------------------
    # File trên đĩa
    # ------------------------------------------------------------------
    def _remove_file(self, path: str, retries: int = 5, delay: float = 0.3) -> bool:
        """Xóa file, thử lại vài lần vì Windows hay giữ khóa file."""
        for attempt in range(retries):
            try:
                if os.path.exists(path):
                    os.remove(path)
                return True
            except OSError:
                if attempt < retries - 1:
                    time.sleep(delay)
        logger.warning("[DOCUMENT] Không xóa được file (đang bị khóa?): %s", path)
        return False

    def _stored_name(self, subject_id: str, filename: str) -> str:
        """Tên file lưu trong data_dir: tách theo môn để không đụng tên."""
        return f"{subject_id}__{filename}"

    def _path_in_use(self, docs: list[Document], abs_path: str) -> bool:
        target = os.path.normcase(os.path.abspath(abs_path))
        for d in docs:
            p = getattr(d, "file_path", "") or ""
            if p and os.path.normcase(os.path.abspath(p)) == target:
                return True
        return False

    # ------------------------------------------------------------------
    # API Public
    # ------------------------------------------------------------------
    def list_documents(self, subject_id: str = None) -> list[Document]:
        # Tự động quét & đồng bộ file tài liệu (chiều thêm + chiều xóa) trước khi trả về danh sách
        self.auto_scan_and_sync()
        docs = self._load_all()
        if subject_id and subject_id != "all":
            return [d for d in docs if d.subject_id == subject_id]
        return docs

    def add_document(
        self, subject_id: str, file_path: str, document_type: str = "khac"
    ) -> Document:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Không tìm thấy file: {file_path}")

        filename = os.path.basename(file_path)
        docs = self._load_all()

        for existing in docs:
            if existing.subject_id == subject_id and existing.filename == filename:
                raise DocumentDuplicateError(
                    f"Tài liệu '{filename}' đã tồn tại trong môn học này."
                )

        abs_src = os.path.abspath(file_path)
        copied = False

        if self._is_inside_data_dir(abs_src):
            if self._path_in_use(docs, abs_src):
                raise DocumentDuplicateError(
                    f"File '{filename}' đang được dùng bởi một tài liệu khác."
                )
            stored_path = abs_src
        else:
            stored_name = self._stored_name(subject_id, filename)
            stored_path = os.path.abspath(os.path.join(self.data_dir, stored_name))

            if self._path_in_use(docs, stored_path):
                raise DocumentDuplicateError(
                    f"File '{filename}' đang được dùng bởi một tài liệu khác."
                )

            if os.path.exists(stored_path):
                logger.warning(
                    "[DOCUMENT] Phát hiện file mồ côi %s, dọn dẹp", stored_name
                )
                self._delete_vectors(stored_name)
                if not self._remove_file(stored_path):
                    stored_name = self._stored_name(
                        subject_id, f"{uuid.uuid4().hex[:6]}__{filename}"
                    )
                    stored_path = os.path.abspath(
                        os.path.join(self.data_dir, stored_name)
                    )

            shutil.copy2(file_path, stored_path)
            copied = True

        source_name = os.path.basename(stored_path)
        self._delete_vectors(source_name)

        try:
            ingest_result = ingest_file(
                stored_path,
                subject_id=subject_id,
                document_type=document_type or "khac",
                embedding_service=self._get_embedding_service(),
                vector_store=self._get_vector_store(),
            )
        except IngestError:
            self._delete_vectors(source_name)
            if copied:
                self._remove_file(stored_path)
            raise
        except Exception as e:
            self._delete_vectors(source_name)
            if copied:
                self._remove_file(stored_path)
            logger.exception("[DOCUMENT] Ingest thất bại cho %s", filename)
            raise IngestError(f"Không lập chỉ mục được '{filename}': {e}") from e

        extracted_chapter = ingest_result.get("chapter", "").strip()
        if not extracted_chapter:
            clean_name = os.path.splitext(filename)[0]
            extracted_chapter = f"Tài liệu: {clean_name}"

        doc = Document(
            id=str(uuid.uuid4())[:8],
            subject_id=subject_id,
            filename=filename,
            file_path=stored_path,
            document_type=document_type,
            chapter=extracted_chapter,
            file_size=os.path.getsize(stored_path),
            page_count=ingest_result.get("page_count", 0),
            chunk_count=ingest_result.get("chunk_count", 0),
        )

        docs.append(doc)
        try:
            self._save_all(docs)
        except Exception:
            logger.exception("[DOCUMENT] Ghi metadata thất bại, rollback %s", filename)
            self._delete_vectors(source_name)
            if copied:
                self._remove_file(stored_path)
            raise

        logger.info(
            "[DOCUMENT] Đã thêm và ingest %s (chunks=%s subject=%s)",
            filename,
            doc.chunk_count,
            subject_id,
        )
        return doc

    def _is_inside_data_dir(self, abs_path: str) -> bool:
        base = os.path.normpath(os.path.abspath(self.data_dir)).lower()
        target_dir = os.path.normpath(
            os.path.dirname(os.path.abspath(abs_path))
        ).lower()
        return target_dir == base

    def delete_document(self, doc_id: str) -> bool:
        docs = self._load_all()
        target = next((d for d in docs if d.id == doc_id), None)
        if target is None:
            return False

        stored_path = os.path.abspath(
            getattr(target, "file_path", "")
            or os.path.join(self.data_dir, target.filename)
        )
        source_name = os.path.basename(stored_path)

        self._delete_vectors(source_name)

        new_docs = [d for d in docs if d.id != doc_id]
        self._save_all(new_docs)

        if not self._path_in_use(new_docs, stored_path):
            if os.path.exists(stored_path):
                self._remove_file(stored_path)

        return True

    def cleanup_orphans(self) -> int:
        docs = self._load_all()
        removed = 0
        for name in os.listdir(self.data_dir):
            if name == os.path.basename(self.metadata_file) or name.endswith(".tmp"):
                continue
            path = os.path.abspath(os.path.join(self.data_dir, name))
            if os.path.isfile(path) and not self._path_in_use(docs, path):
                self._delete_vectors(name)
                if self._remove_file(path):
                    removed += 1
        if removed:
            logger.info("[DOCUMENT] Đã dọn %d file mồ côi", removed)
        return removed

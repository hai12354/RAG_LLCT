import logging
import os
import sys
from pathlib import Path
import chromadb
from pathlib import Path

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_CHROMA_DIR = str(BASE_DIR / "data" / "chroma")


def _get_default_persist_dir() -> str:
    """Xác định đường dẫn tuyệt đối đến thư mục data/chroma.
    Tự động tương thích khi chạy mã nguồn hoặc đóng gói bằng PyInstaller (.exe).
    """
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).parent
    else:
        # Giả định vị trí file ở app/rag/vector_store.py -> lùi 2 cấp lên thư mục gốc
        base_dir = Path(__file__).resolve().parent.parent.parent

    return str(base_dir / "data" / "chroma")


class VectorStore:

    def __init__(
        self,
        persist_directory: str | None = None,
        collection_name: str = "llct_documents",
    ):
        # 1. Tự động lấy đường dẫn mặc định nếu không truyền vào
        if persist_directory is None:
            persist_directory = _get_default_persist_dir()
        else:
            persist_directory = os.path.abspath(str(persist_directory))

        self.persist_directory = persist_directory

        # 2. Tạo thư mục nếu chưa tồn tại
        os.makedirs(self.persist_directory, exist_ok=True)

        # 3. Khởi tạo PersistentClient với try-except để bắt lỗi khởi tạo
        try:
            self.client = chromadb.PersistentClient(path=self.persist_directory)
            self.collection = self.client.get_or_create_collection(name=collection_name)
            logger.info(
                "[VECTOR STORE] Kết nối ChromaDB thành công tại: %s (Collection: %s)",
                self.persist_directory,
                collection_name,
            )
        except Exception:
            logger.exception(
                "[VECTOR STORE] Không thể kết nối ChromaDB tại: %s",
                self.persist_directory,
            )
            raise

    def add_chunks(self, chunks: list[dict], embeddings: list[list[float]]):
        """Thêm hoặc cập nhật (upsert) các chunk vào ChromaDB để tránh trùng lặp."""
        if not chunks:
            return

        if len(embeddings) != len(chunks):
            raise ValueError(
                f"Số embedding ({len(embeddings)}) không khớp số chunk ({len(chunks)})."
            )

        ids = [c["id"] for c in chunks]
        documents = [c["text"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]

        self.collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def count(self) -> int:
        return self.collection.count()

    def query(self, query_embeddings: list[list[float]], top_k: int = 5):
        """Tìm kiếm tương đồng trong vector store."""
        empty = {"documents": [[]], "metadatas": [[]], "distances": [[]]}
        if top_k <= 0:
            return empty
        try:
            total = self.collection.count()
        except Exception:
            logger.exception("[VECTOR STORE] Không đọc được số lượng bản ghi ChromaDB")
            total = 0

        if not total:
            return empty

        n_results = min(top_k, total)
        try:
            results = self.collection.query(
                query_embeddings=query_embeddings, n_results=n_results
            )
            return results
        except Exception:
            logger.exception("[VECTOR STORE] Truy vấn ChromaDB thất bại")
            return empty

    def delete_by_source(self, source_name: str) -> None:
        """Xóa tất cả các vector chunk tương ứng với tên file tài nguyên (source)."""
        if not source_name:
            return
        try:
            self.collection.delete(where={"source": source_name})
            logger.info(
                "[VECTOR STORE] Đã xóa thành công các chunk của source: %s",
                source_name,
            )
        except Exception:
            logger.exception(
                "[VECTOR STORE] Lỗi khi xóa chunk với source: %s", source_name
            )

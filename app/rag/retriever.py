# app/rag/retriever.py
import logging
import os
import unicodedata

from app.rag.embedding import EmbeddingService
from app.rag.vector_store import VectorStore

logger = logging.getLogger(__name__)

# Trùng với DocumentService mặc định; dùng để phát hiện catalog đã cũ
DOCUMENTS_META_PATH = os.path.join("data", "documents", "documents_meta.json")

# Alias đã chuẩn hóa (không dấu, chữ thường, khoảng trắng -> "_")
DOCUMENT_TYPE_ALIASES = {
    "textbook": "giao_trinh",
    "giao_trinh": "giao_trinh",
    "lecture": "bai_giang",
    "bai_giang": "bai_giang",
}


def _strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.replace("đ", "d").replace("Đ", "D")


class Retriever:
    # Số lần mở rộng vùng tìm kiếm khi có bộ lọc mà chưa đủ kết quả
    _FETCH_MULTIPLIERS = (3, 10, 30)

    def __init__(
        self,
        persist_directory: str = "data/chroma",
        collection_name: str = "llct_documents",
        reranker_model: str = "BAAI/bge-reranker-v2-m3",
        use_reranker: bool = True,
    ):
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStore(
            persist_directory=persist_directory, collection_name=collection_name
        )
        self._source_catalog = None
        self._id_to_filename = None
        self._catalog_mtime = None

        # Cấu hình Re-ranker
        self.use_reranker = use_reranker
        self.reranker_model_name = reranker_model
        self._reranker = None  # Singleton Lazy Loading

    # ------------------------------------------------------------------
    # Lazy Load Re-ranker Model
    # ------------------------------------------------------------------
    @property
    def reranker(self):
        """Khởi tạo Re-ranker theo cơ chế Lazy Loading để tối ưu bộ nhớ RAM."""
        if not self.use_reranker:
            return None

        if self._reranker is None:
            try:
                from sentence_transformers import CrossEncoder

                logger.info(
                    "[RETRIEVER] Đang nạp mô hình Re-ranker: %s...",
                    self.reranker_model_name,
                )
                self._reranker = CrossEncoder(self.reranker_model_name)
                logger.info("[RETRIEVER] Nạp mô hình Re-ranker thành công!")
            except Exception as e:
                logger.error("[RETRIEVER] Không nạp được mô hình Re-ranker: %s", e)
                self.use_reranker = False
                self._reranker = None

        return self._reranker

    # ------------------------------------------------------------------
    # Catalog (metadata tài liệu từ DocumentService)
    # ------------------------------------------------------------------
    def _get_source_catalog(self) -> dict:
        """filename (lowercase) -> {subject_id, document_type}.
        Dùng cho chunk cũ thiếu metadata."""
        now_mtime = self._meta_mtime()
        if self._source_catalog is not None and now_mtime == self._catalog_mtime:
            return self._source_catalog
        catalog = {}
        id_map = {}
        try:
            from app.services.document_service import DocumentService

            docs = DocumentService().list_documents()
            for doc in docs:
                filename = os.path.basename(getattr(doc, "filename", "") or "")
                if not filename:
                    continue
                catalog[filename.lower()] = {
                    "subject_id": getattr(doc, "subject_id", "") or "",
                    "document_type": getattr(doc, "document_type", "") or "",
                }
                doc_id = str(getattr(doc, "id", "") or "").strip()
                if doc_id:
                    id_map[doc_id.lower()] = filename.lower()
        except Exception:
            logger.exception("[RETRIEVER] Không đọc được catalog metadata tài liệu")
        self._source_catalog = catalog
        self._id_to_filename = id_map
        self._catalog_mtime = now_mtime
        return catalog

    @staticmethod
    def _meta_mtime():
        try:
            return os.path.getmtime(DOCUMENTS_META_PATH)
        except OSError:
            return None

    def invalidate_catalog(self):
        """Gọi sau khi thêm/xóa tài liệu để catalog không bị cũ."""
        self._source_catalog = None
        self._id_to_filename = None
        self._catalog_mtime = None

    # ------------------------------------------------------------------
    # Chuẩn hóa
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_document_type(value: str) -> str:
        raw = _strip_accents((value or "").strip().lower())
        raw = raw.replace("-", " ")
        raw = "_".join(raw.split())
        return DOCUMENT_TYPE_ALIASES.get(raw, raw)

    def _normalize_allowed_sources(self, allowed_sources) -> set | None:
        """Chuyển danh sách (tên file hoặc id tài liệu) thành tập tên file lowercase."""
        if allowed_sources is None:
            return None
        self._get_source_catalog()
        id_map = self._id_to_filename or {}
        result = set()
        for item in allowed_sources:
            if not item:
                continue
            key = str(item).strip().lower()
            if key in id_map:
                result.add(id_map[key])
            else:
                result.add(os.path.basename(key))
        return result

    def _resolve_subject_and_type(self, meta: dict, doc_source: str):
        doc_subject = str(meta.get("subject_id") or "").strip()
        doc_type = str(meta.get("document_type") or "").strip()
        if doc_subject and doc_type:
            return doc_subject, self._normalize_document_type(doc_type)

        catalog = self._get_source_catalog()
        key = os.path.basename(doc_source or "").lower()
        info = catalog.get(key) or {}
        if not doc_subject:
            doc_subject = str(info.get("subject_id") or "").strip()
        if not doc_type:
            doc_type = str(info.get("document_type") or "").strip()
        return doc_subject, self._normalize_document_type(doc_type)

    # ------------------------------------------------------------------
    # Truy xuất & Lọc kết quả
    # ------------------------------------------------------------------
    def _collection_size(self) -> int:
        try:
            return int(self.vector_store.count())
        except Exception:
            return 0

    def _filter_results(
        self,
        results: dict,
        target_count: int,
        subject_id,
        wanted_type: str,
        allowed: set | None,
    ) -> list[dict]:
        formatted = []
        if not (results and results.get("documents") and results["documents"][0]):
            return formatted

        docs = results["documents"][0]
        metadatas = results["metadatas"][0] if results.get("metadatas") else []
        distances = (
            results["distances"][0]
            if "distances" in results and results["distances"]
            else [0.0] * len(docs)
        )

        for i, doc in enumerate(docs):
            meta = metadatas[i] if i < len(metadatas) else {}
            if not isinstance(meta, dict):
                meta = {}
            distance = distances[i] if i < len(distances) else 0.0
            score = round(1.0 / (1.0 + distance), 4)

            doc_source = str(meta.get("source") or "")
            doc_subject, doc_type = self._resolve_subject_and_type(meta, doc_source)

            if subject_id and subject_id != "all":
                if doc_subject != str(subject_id).strip():
                    continue

            if wanted_type and wanted_type != "all":
                if doc_type and doc_type != wanted_type:
                    continue

            if allowed is not None:
                if not allowed:
                    continue
                if os.path.basename(doc_source).lower() not in allowed:
                    continue

            formatted.append(
                {
                    "text": doc,
                    "source": doc_source,
                    "page": meta.get("page", 0),
                    "score": score,
                    "metadata": meta,
                }
            )
            if len(formatted) >= target_count:
                break
        return formatted

    # ------------------------------------------------------------------
    # Logic Re-ranking
    # ------------------------------------------------------------------
    def _apply_reranker(
        self, query: str, candidates: list[dict], top_k: int
    ) -> list[dict]:
        """Sử dụng Cross-Encoder để sắp xếp lại danh sách ứng viên thu được."""
        if not candidates or not self.reranker:
            return candidates[:top_k]

        try:
            # Tạo cặp câu hỏi & đoạn văn bản
            pairs = [[query, doc["text"]] for doc in candidates]
            scores = self.reranker.predict(pairs)

            for doc, score in zip(candidates, scores):
                doc["score"] = float(score)

            # Sắp xếp giảm dần theo điểm tương quan của Cross-Encoder
            candidates.sort(key=lambda x: x["score"], reverse=True)
            logger.info(
                "[RETRIEVER] Đã thực hiện Re-ranking cho %d chunks.", len(candidates)
            )
        except Exception as e:
            logger.error("[RETRIEVER] Lỗi trong quá trình Re-ranking: %s", e)

        return candidates[:top_k]

    # ------------------------------------------------------------------
    # Hàm Retrieve chính
    # ------------------------------------------------------------------
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        subject_id: str = None,
        document_type: str = None,
        allowed_sources: list[str] = None,
    ) -> list[dict]:
        """Tìm các đoạn tài liệu liên quan, lọc theo môn, loại tài liệu, tên file

        Tích hợp bước Re-ranking tự động nếu `use_reranker=True`.
        """
        if not query or not query.strip():
            return []

        try:
            query_embedding = self.embedding_service.embed_query(query)
        except Exception:
            logger.exception("[RETRIEVER] Không tạo được embedding cho câu hỏi")
            return []

        wanted_type = self._normalize_document_type(document_type or "")
        allowed = self._normalize_allowed_sources(allowed_sources)
        has_filter = bool(
            (subject_id and subject_id != "all")
            or (wanted_type and wanted_type != "all")
            or allowed is not None
        )

        # Mở rộng số lượng candidate lấy về nếu dùng Re-ranker (mặc định lấy x3 số top_k)
        candidate_k = top_k * 3 if self.use_reranker else top_k

        total = self._collection_size()
        multipliers = self._FETCH_MULTIPLIERS if has_filter else (3,)
        schedule = []
        for m in multipliers:
            k = max(candidate_k * m, candidate_k)
            if total:
                k = min(k, total)
            if k not in schedule:
                schedule.append(k)
        if has_filter and total and schedule[-1] < total:
            schedule.append(total)

        formatted_candidates = []
        for fetch_k in schedule:
            try:
                results = self.vector_store.query(
                    query_embeddings=[query_embedding], top_k=fetch_k
                )
            except Exception:
                logger.exception("[RETRIEVER] Truy vấn vector store thất bại")
                return []

            formatted_candidates = self._filter_results(
                results, candidate_k, subject_id, wanted_type, allowed
            )
            if len(formatted_candidates) >= candidate_k:
                break

        # Thực thi Re-ranking nếu bật
        final_results = self._apply_reranker(query, formatted_candidates, top_k)

        logger.info(
            "[RETRIEVER] retrieve() query='%s...' subject_id=%s document_type=%s "
            "allowed_sources=%s -> returned %d results",
            query[:60],
            subject_id,
            document_type,
            allowed_sources,
            len(final_results),
        )
        return final_results

    def retrieve_for_quiz(
        self,
        subject_id: str,
        document_ids: list[str],
        chapter: str = "Tất cả chương",
        top_k: int = 10,
    ) -> list[dict]:
        """Truy xuất context cho việc tạo đề kiểm tra."""
        if not subject_id:
            raise ValueError(
                "[RETRIEVER] retrieve_for_quiz: subject_id không được rỗng."
            )

        if not document_ids:
            logger.error(
                "[RETRIEVER] retrieve_for_quiz: document_ids rỗng cho subject_id=%s. "
                "Từ chối retrieval để tránh lấy nhầm tài liệu môn khác.",
                subject_id,
            )
            return []

        query = f"Kiến thức môn học chương {chapter}"
        logger.info(
            "[RETRIEVER] retrieve_for_quiz: subject_id=%s document_ids=%s chapter=%s top_k=%d",
            subject_id,
            document_ids,
            chapter,
            top_k,
        )

        results = self.retrieve(
            query=query,
            top_k=top_k,
            subject_id=subject_id,
            allowed_sources=document_ids,
        )

        logger.info(
            "[RETRIEVER] retrieve_for_quiz: returned %d chunks (subject=%s, docs=%s)",
            len(results),
            subject_id,
            document_ids,
        )
        return results

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Hàm tương thích ngược với code cũ (không có filter môn/file)."""
        return self.retrieve(query=query, top_k=top_k)

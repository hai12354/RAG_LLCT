# app/rag/embedding.py
import logging
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingService:
    _instance = None
    _model = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        # Áp dụng Singleton Pattern chuẩn
        if cls._instance is None:
            cls._instance = super(EmbeddingService, cls).__new__(cls)
        return cls._instance

    def __init__(
        self,
        # Chuyển sang mô hình tiếng Việt tối ưu hơn cho tài liệu Lý luận chính trị
        model_name: str = "bkai-foundation-models/vietnamese-bi-encoder",
    ):
        # Đảm bảo __init__ chỉ thực thi 1 lần duy nhất
        if not EmbeddingService._initialized:
            self.model_name = model_name
            logger.info(f"[EMBEDDING] Đang nạp mô hình: {self.model_name}...")
            EmbeddingService._model = SentenceTransformer(self.model_name)
            EmbeddingService._initialized = True
            logger.info("[EMBEDDING] Nạp mô hình embedding thành công!")

        self.model = EmbeddingService._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Tạo embedding cho danh sách văn bản (documents)."""
        if not texts:
            return []
        try:
            embeddings = self.model.encode(
                texts, show_progress_bar=False, normalize_embeddings=True
            )
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"[EMBEDDING] Lỗi khi tạo document embeddings: {e}")
            return []

    def embed_query(self, text: str) -> list[float]:
        """Tạo embedding cho câu hỏi truy vấn (query)."""
        if not text or not text.strip():
            return []
        try:
            # Normalize embeddings giúp tính Cosine Similarity chính xác hơn trong Vector Store
            embedding = self.model.encode(
                text, show_progress_bar=False, normalize_embeddings=True
            )
            return embedding.tolist()
        except Exception as e:
            logger.error(f"[EMBEDDING] Lỗi khi tạo query embedding: {e}")
            return []

    @property
    def dimension(self) -> int:
        """Trả về số chiều vector của mô hình."""
        return self.model.get_sentence_embedding_dimension()

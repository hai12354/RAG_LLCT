import re
import hashlib


class TextChunker:
    def __init__(self, chunk_size: int = 15000, chunk_overlap: int = 300):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    @staticmethod
    def clean_text(text: str) -> str:
        """Làm sạch khoảng trắng dư thừa, chuẩn hóa xuống dòng mà không làm thay đổi nội dung học thuật."""
        if not text:
            return ""
        # Thay thế các khoảng trắng liên tiếp bằng 1 khoảng trắng
        text = re.sub(r"[ \t]+", " ", text)
        # Chuẩn hóa các dòng trống liên tiếp
        text = re.sub(r"\n\s*\n", "\n\n", text)
        return text.strip()

    def generate_chunk_id(self, source: str, page: int, chunk_index: int) -> str:
        """Tạo ID ổn định (deterministic) để chống duplicate khi ingestion nhiều lần."""
        raw_id = f"{source}_p{page}_c{chunk_index}"
        return hashlib.md5(raw_id.encode("utf-8")).hexdigest()

    def split_text(
        self, text: str, source: str, page: int, extra_metadata: dict = None
    ):
        """Chia văn bản thành các chunk dựa trên ký tự với overlap."""
        cleaned = self.clean_text(text)
        if not cleaned:
            return []

        extra = extra_metadata or {}
        chunks = []
        start = 0
        length = len(cleaned)
        chunk_index = 0

        while start < length:
            end = min(start + self.chunk_size, length)

            # Cố gắng cắt tại khoảng trắng hoặc dấu câu gần nhất để không cắt đứt giữa câu nếu có thể
            if end < length:
                safe_end = max(
                    cleaned.rfind(" ", start, end),
                    cleaned.rfind(".", start, end),
                    cleaned.rfind("\n", start, end),
                )
                if safe_end > start + int(self.chunk_size * 0.5):
                    end = safe_end + 1

            chunk_text = cleaned[start:end].strip()
            if chunk_text:
                chunk_id = self.generate_chunk_id(source, page, chunk_index)
                metadata = {
                    "source": source,
                    "page": int(page) if page is not None else 0,
                    "chunk_id": chunk_id,
                    "chunk_index": chunk_index,
                }
                for key, value in extra.items():
                    if value is None:
                        continue
                    if isinstance(value, (str, int, float, bool)):
                        metadata[key] = value
                    else:
                        metadata[key] = str(value)
                chunks.append(
                    {
                        "id": chunk_id,
                        "text": chunk_text,
                        "metadata": metadata,
                    }
                )
                chunk_index += 1

            start = end - self.chunk_overlap
            if start >= length or end == length:
                break

        return chunks

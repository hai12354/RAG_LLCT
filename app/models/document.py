# app/models/document.py
import datetime


class Document:
    def __init__(
        self,
        id: str,
        subject_id: str,
        filename: str,
        file_path: str,
        document_type: str = "khac",
        chapter: str = "",
        page_count: int = 0,
        status: str = "active",
        created_at: str = None,
        file_size: int = 0,
        chunk_count: int = 0,
    ):
        self.id = id
        self.subject_id = subject_id
        self.filename = filename
        self.file_path = file_path
        self.document_type = document_type
        self.chapter = chapter
        self.page_count = page_count
        self.status = status
        self.created_at = created_at or datetime.datetime.now().isoformat()
        self.file_size = file_size
        self.chunk_count = chunk_count

    def to_dict(self):
        return {
            "id": self.id,
            "subject_id": self.subject_id,
            "filename": self.filename,
            "file_path": self.file_path,
            "document_type": self.document_type,
            "chapter": self.chapter,
            "page_count": self.page_count,
            "status": self.status,
            "created_at": self.created_at,
            "file_size": self.file_size,
            "chunk_count": self.chunk_count,
        }

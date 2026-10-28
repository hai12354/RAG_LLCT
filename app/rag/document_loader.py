# app/rag/document_loader.py
import logging
import os
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class DocumentLoadError(Exception):
    """Không đọc được nội dung tài liệu."""


class DocumentLoader:
    def __init__(self, documents_dir: str):
        self.documents_dir = documents_dir

    def load_pdf(self, pdf_path: str, raise_on_error: bool = False):
        """Đọc một file PDF tiêu chuẩn, trả về danh sách các trang kèm metadata và thống kê."""
        pages_data = []
        filename = os.path.basename(pdf_path)

        if not os.path.exists(pdf_path):
            if raise_on_error:
                raise DocumentLoadError(f"File không tồn tại: {pdf_path}")
            return [], 0, 0, 0

        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            text_pages_count = 0
            scanned_pages_count = 0

            for page_num in range(total_pages):
                try:
                    page = doc.load_page(page_num)
                    # Lấy text tiêu chuẩn từ trang PDF
                    text = page.get_text("text")

                    if text and text.strip():
                        text_pages_count += 1
                        is_scanned = False
                    else:
                        scanned_pages_count += 1
                        is_scanned = True
                        text = ""

                    pages_data.append(
                        {
                            "text": text,
                            "metadata": {
                                "source": filename,
                                "page": page_num + 1,
                                "is_scanned": is_scanned,
                            },
                        }
                    )
                except Exception as page_err:
                    logger.warning(
                        "[DOC LOADER] Lỗi đọc trang %d của file %s: %s",
                        page_num + 1,
                        filename,
                        page_err,
                    )
                    pages_data.append(
                        {
                            "text": "",
                            "metadata": {
                                "source": filename,
                                "page": page_num + 1,
                                "is_scanned": True,
                            },
                        }
                    )

            doc.close()

            if not pages_data and raise_on_error:
                raise DocumentLoadError(
                    f"File PDF '{filename}' không chứa dữ liệu trang nào."
                )

            return pages_data, total_pages, text_pages_count, scanned_pages_count

        except Exception as e:
            logger.exception("[DOC LOADER] Lỗi mở file %s", filename)
            if raise_on_error:
                raise DocumentLoadError(f"Không thể đọc PDF '{filename}': {e}") from e
            return [], 0, 0, 0

    def load_directory(self):
        """Quét toàn bộ thư mục documents và tải tất cả các file PDF."""
        all_pages = []

        if not os.path.exists(self.documents_dir):
            raise FileNotFoundError(
                f"Không tìm thấy thư mục tài liệu: {self.documents_dir}"
            )

        pdf_files = [
            f for f in os.listdir(self.documents_dir) if f.lower().endswith(".pdf")
        ]

        if not pdf_files:
            raise FileNotFoundError(
                f"Không tìm thấy file PDF nào trong thư mục {self.documents_dir}"
            )

        for filename in pdf_files:
            pdf_path = os.path.join(self.documents_dir, filename)
            pages, _total, _text_p, _scanned_p = self.load_pdf(pdf_path)
            all_pages.extend(pages)

        return all_pages, pdf_files

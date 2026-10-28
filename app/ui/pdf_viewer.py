# app/ui/pdf_viewer.py
import os
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox


def open_external_pdf(parent_widget, file_path):
    if not file_path or not os.path.exists(file_path):
        QMessageBox.warning(
            parent_widget,
            "Lỗi",
            f"Không tìm thấy file tài liệu tại đường dẫn: {file_path}",
        )
        return False

    # Mở file PDF bằng ứng dụng mặc định của hệ thống (Adobe Reader, Edge, Foxit Reader, v.v.)
    # Vừa nhanh, vừa không bị treo UI, không lỗi QWebEngineView trắng màn hình
    url = QUrl.fromLocalFile(os.path.abspath(file_path))
    success = QDesktopServices.openUrl(url)
    if not success:
        QMessageBox.warning(
            parent_widget, "Lỗi", "Không thể mở file PDF bằng ứng dụng hệ thống!"
        )
    return success

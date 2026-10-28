# app/main.py
import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor, QIcon
from app.ui.main_window import MainWindow

from app.rag.retriever import Retriever
from app.services.gemini_service import GeminiService


def resource_path(relative_path):
    """Lấy đường dẫn tuyệt đối chuẩn xác cho PyInstaller."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def main():
    app = QApplication(sys.argv)

    # 1. Ép giao diện Fusion màu sáng (không bị đen khi máy khách bật Windows Dark Mode)
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(245, 245, 245))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
    app.setPalette(palette)
    app.setStyleSheet(
        """
        QWidget {
            background-color: #ffffff;
            color: #0f172a;
        }
        QLineEdit, QTextEdit, QComboBox, QSpinBox {
            background-color: #ffffff;
            color: #0f172a;
            border: 1px solid #cbd5e1;
        }
    """
    )
    # 2. Khởi tạo các dịch vụ cốt lõi
    retriever = Retriever()
    gemini_service = GeminiService()

    # 3. Truyền vào cửa sổ chính & Ép nạp Icon App
    window = MainWindow(retriever=retriever, gemini_service=gemini_service)

    # Nạp icon cửa sổ bằng đường dẫn resource_path
    app_icon_path = resource_path("assets/icons/logo.png")
    if os.path.exists(app_icon_path):
        window.setWindowIcon(QIcon(app_icon_path))
        app.setWindowIcon(QIcon(app_icon_path))

    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

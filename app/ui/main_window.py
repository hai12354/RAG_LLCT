# app/ui/main_window.py
import os
import sys
from PySide6.QtCore import QSize, Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.models.subject import DOCUMENT_TYPES, SUBJECTS
from app.services.document_service import DocumentService
from app.ui.chat_page import ChatPage
from app.ui.help_page import HelpPage
from app.ui.pdf_viewer import open_external_pdf
from app.ui.quiz_page import QuizPage
from app.ui.settings_page import SettingsPage


import os
import sys


def resource_path(relative_path: str) -> str:
    """
    Lấy đường dẫn tuyệt đối tới tài nguyên.
    Hỗ trợ cả môi trường Development và PyInstaller (.exe).
    """
    try:
        # Trường hợp chạy ứng dụng đã đóng gói PyInstaller
        # sys._MEIPASS chính là thư mục gốc _internal chứa assets
        base_path = sys._MEIPASS
    except AttributeError:
        # Trường hợp chạy môi trường dev (.py)
        # Lấy thư mục gốc dự án (chứa thư mục assets/)
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        # LƯU Ý: Nếu file code nằm trong app/ (vd: app/ui/sidebar.py), dùng "..",
        # Nếu file code nằm ngay ngoài gốc (vd: main.py), đổi thành os.path.abspath(".")

    return os.path.join(base_path, relative_path)


class SubjectsPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("📚 DANH MỤC MÔN HỌC & TÀI LIỆU LÝ LUẬN CHÍNH TRỊ")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a365d;")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")

        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(16)

        self.doc_service = DocumentService()

        for idx, subj in enumerate(SUBJECTS):
            card = QFrame()
            card.setStyleSheet(
                "background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px;"
            )
            card_layout = QVBoxLayout(card)

            lbl_name = QLabel(subj["name"])
            lbl_name.setStyleSheet(
                "font-weight: bold; font-size: 15px; color: #1e293b; margin-bottom: 16px;"
            )
            card_layout.addWidget(lbl_name)

            btn_open = QPushButton("Xem môn học")
            btn_open.setStyleSheet(
                """
                QPushButton {
                    background-color: #0ea5e9;
                    color: white;
                    padding: 8px;
                    font-weight: bold;
                    border-radius: 6px;
                    font-size: 13px;
                    outline: none;
                }
                QPushButton:hover {
                    background-color: #0284c7;
                }
                QPushButton:pressed {
                    background-color: #0369a1;
                }
                """
            )
            btn_open.setCursor(Qt.PointingHandCursor)
            btn_open.setFocusPolicy(Qt.NoFocus)
            btn_open.clicked.connect(
                lambda checked=False, s=subj: self.main_window.open_subject_detail(s)
            )
            card_layout.addWidget(btn_open)

            grid.addWidget(card, idx // 2, idx % 2)

        scroll.setWidget(container)
        layout.addWidget(scroll)


class DocumentUploadWorker(QThread):
    progress_signal = Signal(int, str)
    finished_signal = Signal(list)
    error_signal = Signal(str)

    def __init__(self, doc_service: DocumentService, subject_id: str, files: list):
        super().__init__()
        self.doc_service = doc_service
        self.subject_id = subject_id
        self.files = files

    def run(self):
        success_files = []
        errors = []
        total_files = len(self.files)

        for idx, f in enumerate(self.files, 1):
            filename = os.path.basename(f)
            base_percent = int(((idx - 1) / total_files) * 100)
            self.progress_signal.emit(
                base_percent + 10,
                f"⏳ Đang đọc PDF {idx}/{total_files} ({filename})...",
            )

            try:
                self.progress_signal.emit(base_percent + 40, "⏳ Đang phân tích...")
                doc = self.doc_service.add_document(
                    self.subject_id, f, document_type="giao_trinh"
                )

                current_percent = int((idx / total_files) * 100)
                self.progress_signal.emit(
                    current_percent,
                    f"⏳ Đã tạo Vector xong {idx}/{total_files} ({current_percent}%)...",
                )
                success_files.append(f)
            except Exception as e:
                errors.append(f"{filename}: {str(e)}")

        if errors and not success_files:
            self.error_signal.emit("\n".join(errors))
        else:
            self.finished_signal.emit(success_files)


class SubjectDetailWidget(QWidget):
    def __init__(self, subject, back_callback):
        super().__init__()
        self.subject = subject
        self.back_callback = back_callback
        self.doc_service = DocumentService()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        top_row = QHBoxLayout()
        btn_back = QPushButton("← Quay lại danh sách môn")
        btn_back.setStyleSheet(
            "background: transparent; color: #0284c7; font-weight: bold; border: none;"
        )
        btn_back.clicked.connect(self.back_callback)
        top_row.addWidget(btn_back)
        top_row.addStretch()
        layout.addLayout(top_row)

        header_card = QFrame()
        header_card.setStyleSheet(
            "background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px;"
        )
        h_layout = QHBoxLayout(header_card)

        left_h = QVBoxLayout()
        icon_str = subject.get("icon", "🏛️")
        self.title_lbl = QLabel(f"{icon_str}  {subject['name'].upper()}")
        self.title_lbl.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #1e293b;"
        )
        left_h.addWidget(self.title_lbl)

        docs = self.doc_service.list_documents(subject["id"])
        self.meta_lbl = QLabel(f"Tổng số: {len(docs)} tài liệu")
        self.meta_lbl.setStyleSheet("color: #64748b;")
        left_h.addWidget(self.meta_lbl)
        h_layout.addLayout(left_h)

        h_layout.addStretch()

        btn_add = QPushButton("+ Thêm tài liệu")
        btn_add.setStyleSheet(
            """
            QPushButton {
                background-color: #10b981;
                color: white;
                padding: 10px 16px;
                font-weight: bold;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
            QPushButton:pressed {
                background-color: #047857;
            }
            """
        )
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.clicked.connect(self.add_documents)
        h_layout.addWidget(btn_add)

        layout.addWidget(header_card)

        list_label = QLabel("<b>Danh sách tài liệu môn học</b>")
        list_label.setStyleSheet("margin-top: 10px; color: #1e293b;")
        layout.addWidget(list_label)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(
            "background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px;"
        )
        layout.addWidget(self.list_widget)

        self.load_documents()

    def load_documents(self):
        self.list_widget.clear()
        docs = self.doc_service.list_documents(self.subject["id"])
        self.meta_lbl.setText(f"Tổng số: {len(docs)} tài liệu")

        for doc in docs:
            item_widget = QWidget()
            item_widget.setStyleSheet(
                "background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px;"
            )
            row_layout = QHBoxLayout(item_widget)
            row_layout.setContentsMargins(14, 12, 14, 12)

            type_name = DOCUMENT_TYPES.get(doc.document_type, "Khác")
            info_text = QLabel(
                f"📄 <b>{doc.filename}</b> &nbsp;&nbsp;|&nbsp;&nbsp; Loại: {type_name} &nbsp;&nbsp;|&nbsp;&nbsp; <span style='color: #10b981;'>Trạng thái: Đã lập chỉ mục ✓</span>"
            )
            info_text.setStyleSheet(
                "border: none; background: transparent; color: #1e293b; font-size: 13px;"
            )
            row_layout.addWidget(info_text)
            row_layout.addStretch()

            btn_view = QPushButton("📖 Xem PDF")
            btn_view.setStyleSheet(
                """
                QPushButton {
                    background-color: #0284c7;
                    color: white;
                    border-radius: 4px;
                    padding: 6px 14px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #0369a1;
                }
                QPushButton:pressed {
                    background-color: #03588c;
                }
                """
            )
            btn_view.setCursor(Qt.PointingHandCursor)
            btn_view.setFocusPolicy(Qt.NoFocus)
            btn_view.clicked.connect(
                lambda checked=False, path=doc.file_path, name=doc.filename: self.open_pdf_viewer(
                    path, name
                )
            )
            row_layout.addWidget(btn_view)

            btn_delete = QPushButton("🗑️ Xóa")
            btn_delete.setStyleSheet(
                """
                QPushButton {
                    background-color: #ef4444;
                    color: white;
                    border-radius: 4px;
                    padding: 6px 12px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #dc2626;
                }
                QPushButton:pressed {
                    background-color: #b91c1c;
                }
                """
            )
            btn_delete.setCursor(Qt.PointingHandCursor)
            btn_delete.setFocusPolicy(Qt.NoFocus)
            btn_delete.clicked.connect(
                lambda checked=False, doc_id=doc.id, name=doc.filename: self.delete_document_item(
                    doc_id, name
                )
            )
            row_layout.addWidget(btn_delete)

            list_item = QListWidgetItem(self.list_widget)
            list_item.setSizeHint(item_widget.sizeHint().expandedTo(QSize(0, 50)))
            self.list_widget.setItemWidget(list_item, item_widget)

    def delete_document_item(self, doc_id, filename):
        confirm = QMessageBox.question(
            self,
            "Xác nhận xóa",
            f"Bạn có chắc chắn muốn xóa tài liệu <b>{filename}</b> khỏi hệ thống không?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            success = self.doc_service.delete_document(doc_id)
            if success:
                QMessageBox.information(
                    self, "Thành công", "Đã xóa tài liệu thành công khỏi hệ thống!"
                )
                self.load_documents()
            else:
                QMessageBox.warning(self, "Lỗi", "Không thể xóa tài liệu này.")

    def open_pdf_viewer(self, file_path, filename):
        open_external_pdf(self, file_path)

    def add_documents(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Chọn tài liệu học tập", "", "Tài liệu (*.pdf *.docx *.txt)"
        )
        if not files:
            return

        sender_btn = self.sender()
        if sender_btn and isinstance(sender_btn, QPushButton):
            sender_btn.setEnabled(False)
            sender_btn.setText("⏳ Đang khởi tạo (0%)...")

        self.upload_worker = DocumentUploadWorker(
            self.doc_service, self.subject["id"], files
        )

        def on_progress(percent, message):
            if sender_btn and isinstance(sender_btn, QPushButton):
                sender_btn.setText(f"⏳ {percent}% - {message}")

        def on_finished(success_files):
            if sender_btn and isinstance(sender_btn, QPushButton):
                sender_btn.setEnabled(True)
                sender_btn.setText("+ Thêm tài liệu")
            self.load_documents()
            QMessageBox.information(
                self,
                "Thành công",
                f"🎉 Đã nạp thành công {len(success_files)} tài liệu và cập nhật chỉ mục RAG!",
            )

        def on_error(err_msg):
            if sender_btn and isinstance(sender_btn, QPushButton):
                sender_btn.setEnabled(True)
                sender_btn.setText("+ Thêm tài liệu")
            QMessageBox.warning(
                self,
                "Lỗi thêm tài liệu",
                f"Không thể thêm tài liệu:\n{err_msg}",
            )

        self.upload_worker.progress_signal.connect(on_progress)
        self.upload_worker.finished_signal.connect(on_finished)
        self.upload_worker.error_signal.connect(on_error)
        self.upload_worker.start()


class MainWindow(QMainWindow):
    def __init__(self, retriever, gemini_service):
        super().__init__()
        self.retriever = retriever
        self.gemini_service = gemini_service
        self.setWindowTitle("Hỗ trợ học tập Lý luận chính trị")
        self.resize(1280, 768)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. TOP HEADER BAR
        header_bar = QWidget()
        header_bar.setStyleSheet("background-color: #1e3a8a; color: #ffffff;")
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(16, 8, 16, 8)

        logo_title_layout = QVBoxLayout()
        app_title = QLabel("Cố vấn học tập ")
        app_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        app_sub = QLabel("Hỗ trợ học tập Lý luận chính trị")
        app_sub.setStyleSheet("font-size: 11px; color: #93c5fd;")
        logo_title_layout.addWidget(app_title)
        logo_title_layout.addWidget(app_sub)
        header_layout.addLayout(logo_title_layout)

        header_layout.addStretch()
        root_layout.addWidget(header_bar)

        # 2. BODY LAYOUT (Sidebar + Stacked Content)
        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # Sidebar
        sidebar = QWidget()
        sidebar.setStyleSheet("background-color: #0f172a; color: #f8fafc;")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 16, 12, 16)
        sidebar_layout.setSpacing(4)

        self.stack = QStackedWidget()

        self.chat_page = ChatPage(self)
        self.subjects_page = SubjectsPage(self)
        self.quiz_page = QuizPage(self.retriever, self.gemini_service)
        self.settings_page = SettingsPage()
        self.help_page = HelpPage()

        self.stack.addWidget(self.chat_page)  # Index 0
        self.stack.addWidget(self.subjects_page)  # Index 1
        self.stack.addWidget(self.quiz_page)  # Index 2
        self.stack.addWidget(self.settings_page)  # Index 3
        self.stack.addWidget(self.help_page)  # Index 4

        nav_buttons = [
            ("💬 Hỏi đáp", 0),
            ("📚 Môn học", 1),
            ("📝 Luyện tập", 2),
            ("⚙️ Cài đặt", 3),
            ("❓ Hướng dẫn", 4),
        ]

        self.nav_btns = []
        for text, idx in nav_buttons:
            btn = QPushButton(text)
            btn.setStyleSheet(
                """
                QPushButton {
                    text-align: left;
                    background-color: transparent;
                    color: #cbd5e1;
                    border: none;
                    padding: 10px 12px;
                    font-size: 13px;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #1e293b;
                    color: #ffffff;
                }
            """
            )
            btn.setFocusPolicy(Qt.NoFocus)
            btn.clicked.connect(lambda checked=False, i=idx: self.switch_page(i))
            sidebar_layout.addWidget(btn)
            self.nav_btns.append(btn)

        # Section: 6 MÔN HỌC in Sidebar
        lbl_subjects_header = QLabel("6 MÔN HỌC")
        lbl_subjects_header.setStyleSheet(
            "color: #64748b; font-size: 11px; font-weight: bold; margin-top: 16px; margin-bottom: 6px;"
        )
        sidebar_layout.addWidget(lbl_subjects_header)

        for subj in SUBJECTS:
            icon_str = subj.get("icon", "🏛️")
            s_btn = QPushButton(f"{icon_str}  {subj['name']}")
            s_btn.setStyleSheet(
                """
                QPushButton {
                    text-align: left;
                    background-color: transparent;
                    color: #94a3b8;
                    border: none;
                    padding: 6px 8px;
                    font-size: 12px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #1e293b;
                    color: #ffffff;
                }
            """
            )
            s_btn.setFocusPolicy(Qt.NoFocus)
            s_btn.clicked.connect(
                lambda checked=False, s=subj: self.open_subject_detail(s)
            )
            sidebar_layout.addWidget(s_btn)

        sidebar_layout.addStretch()

        # ==========================================
        # CHÈN ĐOẠN CODE LOGO NẠP CHUẨN RESOURCE_PATH:
        # ==========================================
        footer_container = QWidget()
        footer_layout = QVBoxLayout(footer_container)
        footer_layout.setContentsMargins(0, 10, 0, 0)
        footer_layout.setSpacing(6)

        logo_lbl = QLabel()
        logo_lbl.setStyleSheet("background: transparent;")

        # Bọc đường dẫn bằng resource_path để hỗ trợ chuẩn cả môi trường Dev và .exe
        logo_path = resource_path(os.path.join("assets", "icons", "logo.png"))
        print(f"[DEBUG Logo Path]: {logo_path}")
        print(f"[DEBUG File Exists]: {os.path.exists(logo_path)}")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            logo_lbl.setPixmap(
                pixmap.scaled(110, 110, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            print(f"[ERROR]: Không tìm thấy logo tại đường dẫn: {logo_path}")
        logo_lbl.setAlignment(Qt.AlignCenter)

        footer_text = QLabel(
            "<b>Phân hiệu Trường Đại học Thủy Lợi</b><br><span style='font-size: 10px; color: #64748b;'>Học để làm chủ tương lai</span>"
        )
        footer_text.setStyleSheet("color: #94a3b8; font-size: 11px;")
        footer_text.setAlignment(Qt.AlignCenter)

        footer_layout.addWidget(logo_lbl)
        footer_layout.addWidget(footer_text)

        sidebar_layout.addWidget(footer_container)
        # ==========================================

        sidebar.setFixedWidth(240)
        body_layout.addWidget(sidebar)
        body_layout.addWidget(self.stack)

        root_layout.addLayout(body_layout)

    def switch_page(self, index):
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_btns):
            if i == index:
                btn.setStyleSheet(
                    """
                    QPushButton {
                        text-align: left;
                        background-color: #2563eb;
                        color: #ffffff;
                        border: none;
                        padding: 10px 12px;
                        font-size: 13px;
                        border-radius: 6px;
                        font-weight: bold;
                    }
                    """
                )
            else:
                btn.setStyleSheet(
                    """
                    QPushButton {
                        text-align: left;
                        background-color: transparent;
                        color: #cbd5e1;
                        border: none;
                        padding: 10px 12px;
                        font-size: 13px;
                        border-radius: 6px;
                    }
                    QPushButton:hover {
                        background-color: #1e293b;
                        color: #ffffff;
                    }
                    """
                )

    def open_subject_detail(self, subject):
        detail_widget = SubjectDetailWidget(
            subject, lambda: self.stack.setCurrentIndex(1)
        )
        self.stack.addWidget(detail_widget)
        self.stack.setCurrentWidget(detail_widget)

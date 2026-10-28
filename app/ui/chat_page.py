# app/ui/chat_page.py
import logging
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QScrollArea,
    QFrame,
    QComboBox,
)
from app.rag.retriever import Retriever
from app.services.gemini_service import GeminiService
from app.rag.generator import RAGGenerator
from app.services.settings_manager import SettingsManager
from app.services.document_service import DocumentService
from app.services.chat_service import ChatService, RAGWorker

logger = logging.getLogger(__name__)

# Danh sách 6 môn học chuẩn đồng bộ với Database / Metadata
SUBJECTS = [
    {"id": "triet_hoc", "name": "Triết học Mác – Lênin"},
    {"id": "kinh_te_chinh_tri", "name": "Kinh tế chính trị Mác – Lênin"},
    {"id": "chu_nghia_xa_hoi", "name": "Chủ nghĩa xã hội khoa học"},
    {"id": "lich_su_dang", "name": "Lịch sử Đảng Cộng sản Việt Nam"},
    {"id": "tu_tuong_ho_chi_minh", "name": "Tư tưởng Hồ Chí Minh"},
    {"id": "phap_luat", "name": "Pháp luật đại cương"},
]

DOC_TYPES = [
    {"id": "all", "name": "Tất cả tài liệu"},
]

# CSS dùng chung giúp ComboBox cố định Light Mode chuẩn 100% trên mọi máy khách
COMBOBOX_STYLE = """
QComboBox {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    font-weight: 500;
}
QComboBox:hover {
    border-color: #2563eb;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: none;
}
/* Style danh sách sổ xuống */
QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    outline: none;
    padding: 4px;
}
QComboBox QAbstractItemView::item {
    min-height: 28px;
    padding: 4px 8px;
    color: #0f172a;
}
"""


class ChatPage(QWidget):
    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.settings_manager = SettingsManager()
        self.doc_service = DocumentService()
        self.chat_service = ChatService()

        # Layout chính chia thành Trái (Chat) và Phải (Tài liệu liên quan)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Khung Chat
        chat_container = QWidget()
        chat_layout = QVBoxLayout(chat_container)
        chat_layout.setContentsMargins(0, 0, 0, 0)

        # Header Title
        top_chat_bar = QHBoxLayout()
        chat_title_lbl = QLabel("💬 HỎI ĐÁP & TRA CỨU TÀI LIỆU")
        chat_title_lbl.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #1e293b;"
        )
        top_chat_bar.addWidget(chat_title_lbl)
        top_chat_bar.addStretch()

        history_btn = QPushButton("🕒 Xóa lịch sử cache")
        history_btn.setStyleSheet(
            "background: transparent; color: #64748b; border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 8px;"
        )
        history_btn.setCursor(Qt.PointingHandCursor)
        history_btn.clicked.connect(self.clear_cache_ui)
        top_chat_bar.addWidget(history_btn)
        chat_layout.addLayout(top_chat_bar)

        subtitle_lbl = QLabel(
            "Tra cứu và hỏi đáp thông minh dựa trên tài liệu thực tế của từng môn học."
        )
        subtitle_lbl.setStyleSheet(
            "color: #64748b; font-size: 12px; margin-bottom: 6px;"
        )
        chat_layout.addWidget(subtitle_lbl)

        # Dropdowns Chọn Môn học & Loại tài liệu
        filter_frame = QFrame()
        filter_frame.setStyleSheet(
            "background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px;"
        )
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(8, 4, 8, 4)

        # Dropdown Môn học
        subj_layout = QVBoxLayout()
        subj_lbl = QLabel("<b>Môn học:</b>")
        subj_lbl.setStyleSheet("font-size: 11px; color: #475569;")
        self.subject_combo = QComboBox()
        self.subject_combo.setStyleSheet(COMBOBOX_STYLE)
        for subj in SUBJECTS:
            self.subject_combo.addItem(f" {subj['name']}", subj["id"])
        self.subject_combo.setCurrentIndex(0)
        self.subject_combo.currentIndexChanged.connect(self.on_subject_changed)
        subj_layout.addWidget(subj_lbl)
        subj_layout.addWidget(self.subject_combo)

        # Dropdown Loại tài liệu
        doc_layout = QVBoxLayout()
        doc_lbl = QLabel("<b>Tài liệu sử dụng:</b>")
        doc_lbl.setStyleSheet("font-size: 11px; color: #475569;")
        self.doc_type_combo = QComboBox()
        self.doc_type_combo.setStyleSheet(COMBOBOX_STYLE)
        for dtype in DOC_TYPES:
            self.doc_type_combo.addItem(dtype["name"], dtype["id"])
        self.doc_type_combo.setCurrentIndex(0)
        self.doc_type_combo.currentIndexChanged.connect(self.on_subject_changed)
        doc_layout.addWidget(doc_lbl)
        doc_layout.addWidget(self.doc_type_combo)

        filter_layout.addLayout(subj_layout, stretch=2)
        filter_layout.addLayout(doc_layout, stretch=2)
        chat_layout.addWidget(filter_frame)

        # Badge hiển thị môn hiện tại
        self.current_badge_lbl = QLabel(
            " Đang chọn: Triết học Mác – Lênin (Tất cả tài liệu)"
        )
        self.current_badge_lbl.setStyleSheet(
            "color: #0284c7; font-weight: bold; font-size: 12px; margin-top: 4px;"
        )
        chat_layout.addWidget(self.current_badge_lbl)

        # Khung chứa hội thoại Chat
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet(
            "background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px;"
        )

        self.msg_container = QWidget()
        self.msg_container.setStyleSheet("background-color: #ffffff;")
        self.msg_layout = QVBoxLayout(self.msg_container)
        self.msg_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.msg_container)

        chat_layout.addWidget(self.scroll_area)

        # Label Trạng thái đang tải
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet(
            "color: #0284c7; font-style: italic; font-size: 12px;"
        )
        chat_layout.addWidget(self.status_lbl)

        # Khung Nhập câu hỏi
        input_frame = QFrame()
        input_frame.setStyleSheet(
            "background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 4px;"
        )
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(8, 4, 8, 4)

        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("Nhập câu hỏi dựa trên tài liệu môn học...")
        self.input_box.setStyleSheet(
            "border: none; background: transparent; font-size: 13px; padding: 6px; color: #0f172a;"
        )
        self.input_box.returnPressed.connect(self.send_question)

        self.send_btn = QPushButton("➤ Gửi")
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1d4ed8; }
            QPushButton:disabled { background-color: #94a3b8; }
        """
        )
        self.send_btn.clicked.connect(self.send_question)

        input_layout.addWidget(self.input_box)
        input_layout.addWidget(self.send_btn)

        chat_layout.addWidget(input_frame)
        layout.addWidget(chat_container, stretch=3)

        # Panel Phải: Tài liệu môn học
        right_panel = QWidget()
        right_panel.setStyleSheet(
            "background-color: #f8fafc; border-left: 1px solid #e2e8f0;"
        )
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(12, 12, 12, 12)

        right_top_bar = QHBoxLayout()
        btn_rel = QPushButton("Tài liệu môn học")
        btn_rel.setStyleSheet(
            "border: none; font-weight: bold; color: #1e293b; background: transparent; border-bottom: 2px solid #2563eb; padding-bottom: 4px;"
        )
        right_top_bar.addWidget(btn_rel)
        right_layout.addLayout(right_top_bar)

        self.related_scroll = QScrollArea()
        self.related_scroll.setWidgetResizable(True)
        self.related_scroll.setStyleSheet("border: none; background: transparent;")

        self.related_container = QWidget()
        self.related_layout = QVBoxLayout(self.related_container)
        self.related_layout.setAlignment(Qt.AlignTop)

        self.refresh_related_documents()

        self.related_scroll.setWidget(self.related_container)
        right_layout.addWidget(self.related_scroll)

        right_panel.setFixedWidth(280)
        layout.addWidget(right_panel, stretch=1)

        # Khởi tạo Retriever & RAG Services
        self.retriever = None
        self.gemini_service = None
        self.rag_generator = None
        self._api_key = None
        self.reload_api_key()

        # Thông điệp chào mừng
        self.add_ai_message(
            "Chào em! Thầy là Cố vấn AI môn Lý luận Chính trị. Em đang vướng mắc phần kiến thức nào hoặc cần Thầy giải thích nội dung nào, cứ chọn môn học ở trên rồi nhập câu hỏi bên dưới nhé!"
        )

    def reload_api_key(self):
        if self.retriever is None:
            try:
                self.retriever = Retriever(use_reranker=False)
            except Exception:
                logger.exception("[CHAT] Không khởi tạo được Retriever")
                self.rag_generator = None
                return False

        api_key = self.settings_manager.get_api_key()
        self._api_key = api_key
        try:
            self.gemini_service = GeminiService(api_key=api_key)
            self.rag_generator = RAGGenerator(
                retriever=self.retriever, gemini_service=self.gemini_service
            )
            return True
        except Exception:
            logger.exception("[CHAT] Không khởi tạo được RAGGenerator (API key?)")
            self.rag_generator = None
            return False

    def _ensure_generator_up_to_date(self):
        current_key = self.settings_manager.get_api_key()
        if self.rag_generator is None or current_key != self._api_key:
            self.reload_api_key()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_related_documents()

    def clear_cache_ui(self):
        self.chat_service.clear_cache()
        self.add_ai_message(
            "Đã xóa toàn bộ cache câu hỏi. Các câu hỏi tiếp theo sẽ được truy vấn mới từ API."
        )

    def on_subject_changed(self):
        subj_name = self.subject_combo.currentText()
        dtype_name = self.doc_type_combo.currentText()
        self.current_badge_lbl.setText(f"Đang chọn: {subj_name} | {dtype_name}")
        self.refresh_related_documents()

    def refresh_related_documents(self):
        while self.related_layout.count():
            item = self.related_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        subj_id = self.subject_combo.currentData()
        docs = []
        try:
            docs = self.doc_service.list_documents(subj_id)
        except Exception:
            pass

        lbl_section = QLabel(f"<b>Danh sách tài liệu ({len(docs)})</b>")
        lbl_section.setStyleSheet("color: #475569; margin-top: 8px;")
        self.related_layout.addWidget(lbl_section)

        if not docs:
            lbl_empty = QLabel(
                "Chưa có tài liệu cho môn học này.\nVui lòng thêm trong mục Môn học."
            )
            lbl_empty.setStyleSheet(
                "color: #94a3b8; font-size: 11px; font-style: italic;"
            )
            self.related_layout.addWidget(lbl_empty)
        else:
            for doc in docs:
                box = QFrame()
                box.setStyleSheet(
                    "background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px; margin-bottom: 4px;"
                )
                b_lay = QVBoxLayout(box)
                b_lay.setContentsMargins(6, 6, 6, 6)
                b_lay.addWidget(QLabel(f"📄 <b>{doc.filename}</b>"))
                b_lay.addWidget(
                    QLabel(
                        f"<span style='color: #64748b; font-size: 11px;'>Loại: {doc.document_type if hasattr(doc, 'document_type') else 'Chung'}</span>"
                    )
                )
                self.related_layout.addWidget(box)

    def add_message(self, text, is_user=False):
        bubble = QWidget()
        b_layout = QHBoxLayout(bubble)
        b_layout.setContentsMargins(0, 4, 0, 4)

        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            "background-color: #e0f2fe; color: #0369a1; padding: 10px 14px; border-radius: 12px; font-size: 13px;"
            if is_user
            else "background-color: #f1f5f9; color: #0f172a; padding: 10px 14px; border-radius: 12px; font-size: 13px;"
        )
        if is_user:
            b_layout.addStretch()
            b_layout.addWidget(lbl)
        else:
            b_layout.addWidget(lbl)
            b_layout.addStretch()

        self.msg_layout.addWidget(bubble)

    def add_ai_message(self, answer_text, sources=None, from_cache=False):
        bubble = QWidget()
        b_layout = QVBoxLayout(bubble)
        b_layout.setContentsMargins(0, 4, 0, 4)

        content_frame = QFrame()
        content_frame.setStyleSheet(
            "background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px;"
        )
        c_layout = QVBoxLayout(content_frame)
        c_layout.setContentsMargins(0, 0, 0, 0)

        header_row = QHBoxLayout()
        bot_icon = QLabel(
            "🎓 <b>Cố vấn AI</b>"
            + (
                " <span style='color: #10b981; font-weight: bold; font-size: 11px;'>(Đã lưu Cache)</span>"
                if from_cache
                else ""
            )
        )
        bot_icon.setStyleSheet("color: #2563eb;")
        header_row.addWidget(bot_icon)
        header_row.addStretch()
        c_layout.addLayout(header_row)

        ans_lbl = QLabel(answer_text)
        ans_lbl.setWordWrap(True)
        # Render Markdown đẹp mắt, loại bỏ ký tự thô
        ans_lbl.setTextFormat(Qt.MarkdownText)
        ans_lbl.setStyleSheet(
            "color: #1e293b; font-size: 13px; margin-top: 6px; line-height: 1.5;"
        )
        c_layout.addWidget(ans_lbl)

        if sources:
            src_box = QFrame()
            src_box.setStyleSheet(
                "background-color: #f8fafc; border-left: 3px solid #0284c7; padding: 6px; margin-top: 8px;"
            )
            s_layout = QVBoxLayout(src_box)
            s_layout.setContentsMargins(6, 4, 6, 4)
            s_layout.addWidget(QLabel("<b>📚 Nguồn tham khảo:</b>"))
            for i, s in enumerate(sources, 1):
                page_str = f" - Trang {s.get('page')}" if s.get("page") else ""
                s_layout.addWidget(QLabel(f"{i}. {s.get('source')}{page_str}"))
            c_layout.addWidget(src_box)

        b_layout.addWidget(content_frame)
        self.msg_layout.addWidget(bubble)

    def send_question(self):
        q = self.input_box.text().strip()
        if not q:
            return

        subject_id = self.subject_combo.currentData()
        document_type = self.doc_type_combo.currentData()

        self.add_message(q, is_user=True)
        self.input_box.clear()

        # 1. Kiểm tra Cache
        cached_res = self.chat_service.get_cached_answer(subject_id, document_type, q)
        if cached_res:
            self.add_ai_message(
                cached_res.get("answer"),
                sources=cached_res.get("sources"),
                from_cache=True,
            )
            return

        # 2. Nếu chưa có trong Cache, gọi RAG
        self._ensure_generator_up_to_date()
        if not self.rag_generator:
            self.add_ai_message(
                "Chưa cấu hình RAG Generator hoặc API Key trong Cài đặt."
            )
            return

        self.send_btn.setEnabled(False)
        self.status_lbl.setText("Thầy đang đọc tài liệu và chuẩn bị bài giảng...")

        self.worker = RAGWorker(self.rag_generator, q, subject_id, document_type)
        self.worker.finished.connect(
            lambda res, sid=subject_id, dt=document_type, que=q: self.handle_rag_result(
                res, sid, dt, que
            )
        )
        self.worker.error.connect(self.handle_rag_error)
        self.worker.start()

    def handle_rag_result(self, result, subject_id, document_type, question):
        self.status_lbl.clear()
        self.send_btn.setEnabled(True)

        ans = result.get(
            "answer", "Không tìm thấy nội dung phù hợp trong tài liệu môn học này."
        )

        # Chỉ loại bỏ ký tự trích dẫn nguồn dạng [1], [2]
        ans = re.sub(r"\s*\[\d+(?:,\s*\d+)*\]", "", ans)

        raw_sources = result.get("sources", [])

        seen = set()
        sources = []
        for s in raw_sources:
            src_name = s.get("source", "Tài liệu RAG")
            page_num = str(s.get("page", "1"))
            identifier = (src_name, page_num)

            if identifier not in seen:
                seen.add(identifier)
                sources.append({"source": src_name, "page": page_num})

        if (
            ans
            and "Rate limit" not in ans
            and "Error code" not in ans
            and "Lỗi hệ thống" not in ans
        ):
            self.chat_service.save_answer_to_cache(
                subject_id, document_type, question, ans, sources
            )

        self.add_ai_message(ans, sources=sources, from_cache=False)

    def handle_rag_error(self, err_msg):
        self.status_lbl.clear()
        self.send_btn.setEnabled(True)
        self.add_ai_message(f"Lỗi hệ thống khi xử lý RAG: {err_msg}")

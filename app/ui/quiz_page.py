# app/ui/quiz_page.py
import logging
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTabWidget, QMessageBox
from PySide6.QtCore import QThread, Signal
from app.rag.retriever import Retriever
from app.services.gemini_service import GeminiService
from app.services.quiz_service import QuizService
from app.services.question_bank_service import QuestionBankService
from app.services.settings_manager import SettingsManager
from app.ui.quiz_config_widget import QuizConfigWidget
from app.ui.quiz_taking_widget import QuizTakingWidget
from app.ui.quiz_history_widget import QuizHistoryWidget

logger = logging.getLogger(__name__)


class QuizWorker(QThread):
    finished_signal = Signal(dict)
    error_signal = Signal(str)

    def __init__(self, quiz_service: QuizService, config: dict):
        super().__init__()
        self.quiz_service = quiz_service
        self.config = config

    def run(self):
        try:
            exam_data = self.quiz_service.generate_exam(
                subject_id=self.config["subject_id"],
                subject_name=self.config["subject_name"],
                selected_documents=self.config["selected_documents"],
                specific_quiz_file=self.config.get("specific_quiz_file"),
                chapter=self.config["chapter"],
                quiz_type=self.config["quiz_type"],
                mc_count=self.config["mc_count"],
                essay_count=self.config["essay_count"],
                difficulty=self.config["difficulty"],
            )
            self.finished_signal.emit(exam_data)
        except Exception as e:
            logger.exception("[QUIZ WORKER] Lỗi tạo đề trong worker thread")
            self.error_signal.emit(str(e))


class QuizPage(QWidget):
    def __init__(self, retriever=None, gemini_service=None):
        super().__init__()
        self.settings_manager = SettingsManager()
        self.retriever = retriever if retriever else Retriever()

        if gemini_service:
            self.gemini_service = gemini_service
        else:
            api_key = self.settings_manager.get_api_key()
            self.gemini_service = GeminiService(api_key=api_key)

        self.quiz_service = QuizService(self.retriever, self.gemini_service)
        self.qb_service = QuestionBankService()
        self.worker = None

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)

        title_layout = QVBoxLayout()
        title = QLabel("LUYỆN TẬP & TẠO ĐỀ KIỂM TRA")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1a365d;")
        subtitle = QLabel(
            "Tạo đề kiểm tra thông minh từ tài liệu học tập đã tải lên bằng công nghệ RAG & AI"
        )
        subtitle.setStyleSheet("font-size: 13px; color: #64748b;")
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        main_layout.addLayout(title_layout)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            """
            QTabWidget::pane { border: 1px solid #cbd5e1; border-radius: 6px; background: #ffffff; }
            QTabBar::tab { background: #f1f5f9; color: #334155; padding: 8px 16px; margin-right: 2px; border-top-left-radius: 4px; border-top-right-radius: 4px; outline: none; }
            QTabBar::tab:selected { background: #3b82f6; color: white; font-weight: bold; outline: none; }
            QTabBar::tab:focus { outline: none; }
        """
        )

        self.config_widget = QuizConfigWidget(self.retriever)
        self.config_widget.exam_requested.connect(self.process_generate_exam)
        self.tabs.addTab(self.config_widget, "Tạo đề kiểm tra mới")

        self.taking_widget = QuizTakingWidget()
        self.taking_widget.finished_exam.connect(self.on_exam_finished_go_back)
        self.tabs.addTab(self.taking_widget, "Làm bài kiểm tra")

        self.history_widget = QuizHistoryWidget()
        self.tabs.addTab(self.history_widget, "Lịch sử làm bài")

        self.tabs.currentChanged.connect(self.on_tab_changed)

        main_layout.addWidget(self.tabs)

    def on_tab_changed(self, index: int):
        if index == 2 and hasattr(self, "history_widget"):
            self.history_widget.load_history()

    def process_generate_exam(self, config: dict):
        if self.worker is not None and self.worker.isRunning():
            return

        api_key = self.settings_manager.get_api_key()
        if api_key:
            self.gemini_service.set_api_key(api_key)

        self.config_widget.set_generating_state(True)

        self.worker = QuizWorker(self.quiz_service, config)
        self.worker.finished_signal.connect(self.on_exam_generated_success)
        self.worker.error_signal.connect(self.on_exam_generated_error)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.start()

    def on_exam_generated_success(self, exam_data: dict):
        try:
            if not isinstance(exam_data, dict):
                self.on_exam_generated_error("Dữ liệu đề thi không hợp lệ.")
                return
            if exam_data.get("error"):
                self.on_exam_generated_error(str(exam_data["error"]))
                return
            questions = exam_data.get("questions")
            if not isinstance(questions, list) or not questions:
                self.on_exam_generated_error(
                    "AI trả về dữ liệu không đúng định dạng hoặc không tìm thấy câu hỏi phù hợp."
                )
                return
            self.qb_service.save_exam(exam_data)
            self.taking_widget.render_exam(exam_data)
            self.tabs.setCurrentIndex(1)
        except Exception as e:
            logger.exception("Error rendering exam in UI")
            QMessageBox.critical(
                self, "Lỗi hiển thị", f"Không thể hiển thị đề thi.\nChi tiết: {str(e)}"
            )

    def on_exam_generated_error(self, err_msg: str):
        if "API key chưa được cấu hình" in err_msg or "API key không hợp lệ" in err_msg:
            msg = "Không thể tạo bài kiểm tra vì API key chưa được cấu hình hoặc không hợp lệ. Vui lòng kiểm tra mục Cài đặt."
        elif "kết nối đến" in err_msg or "mạng" in err_msg.lower():
            msg = "Không thể kết nối đến AI. Vui lòng kiểm tra kết nối mạng và thử lại."
        elif "không đúng định dạng" in err_msg or "JSON" in err_msg:
            msg = "AI trả về dữ liệu không đúng định dạng. Hệ thống đã tự động thử lại nhưng không thành công."
        else:
            msg = f"Không thể tạo bài kiểm tra.\nChi tiết: {err_msg}"

        QMessageBox.warning(self, "Thông báo tạo đề", msg)

    def on_exam_finished_go_back(self):
        if hasattr(self, "history_widget"):
            self.history_widget.load_history()
        self.tabs.setCurrentIndex(2)

    def on_worker_finished(self):
        self.config_widget.set_generating_state(False)
        if self.worker:
            self.worker.deleteLater()
            self.worker = None

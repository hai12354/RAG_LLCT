# app/ui/quiz_config_widget.py
import json
import logging
import os
from pathlib import Path
import shutil
import sys

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.services.document_service import DocumentService

logger = logging.getLogger(__name__)


def get_data_dir() -> Path:
    """Xác định đường dẫn thư mục data chuẩn cho cả môi trường Dev và file .exe PyInstaller."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "data"
    return Path(__file__).resolve().parent.parent.parent / "data"


class QuizConfigWidget(QWidget):

    exam_requested = Signal(dict)

    def __init__(self, retriever):
        super().__init__()
        self.retriever = retriever
        self.doc_service = DocumentService()

        # Danh mục các môn học chuẩn (thêm lựa chọn mặc định để kiểm tra)
        self.subjects_map = {
            "-- Chọn môn học --": "",
            "Tất cả môn / Tổng hợp": "all",
            "Pháp luật đại cương": "phap_luat",
            "Triết học Mác - Lênin": "triet_hoc",
            "Kinh tế chính trị Mác - Lênin": "kinh_te_chinh_tri",
            "Chủ nghĩa xã hội khoa học": "chu_nghia_xa_hoi",
            "Lịch sử Đảng Cộng sản Việt Nam": "lich_su_dang",
            "Tư tưởng Hồ Chí Minh": "tu_tuong_ho_chi_minh",
        }
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("background-color: #ffffff; color: #1e293b;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: #ffffff; border: none;")

        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: #ffffff; color: #1e293b;")
        form_layout = QVBoxLayout(content_widget)
        form_layout.setSpacing(12)

        common_input_style = """
            QComboBox, QSpinBox, QListWidget {
                background-color: #ffffff;
                color: #1e293b;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px;
            }
            QComboBox::drop-down {
                border: 0px;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #1e293b;
                selection-background-color: #3b82f6;
                selection-color: #ffffff;
            }
        """

        # 1. Chọn môn học
        lbl1 = QLabel("<b>1. Chọn môn học:</b>")
        lbl1.setStyleSheet("background-color: #ffffff; color: #1e293b;")
        form_layout.addWidget(lbl1)

        self.subject_combo = QComboBox()
        self.subject_combo.setCursor(Qt.PointingHandCursor)
        self.subject_combo.setStyleSheet(common_input_style)
        self.subject_combo.addItems(list(self.subjects_map.keys()))
        self.subject_combo.currentIndexChanged.connect(self.on_subject_changed)
        form_layout.addWidget(self.subject_combo)

        # 2. Chọn tài liệu giáo trình / bài giảng
        lbl2 = QLabel("<b>2. Chọn tài liệu giáo trình / lý thuyết:</b>")
        lbl2.setStyleSheet("background-color: #ffffff; color: #1e293b;")
        form_layout.addWidget(lbl2)

        self.docs_list_widget = QListWidget()
        self.docs_list_widget.setStyleSheet(common_input_style)
        self.docs_list_widget.setMaximumHeight(120)
        form_layout.addWidget(self.docs_list_widget)

        # 3. Chọn file trắc nghiệm riêng + Nút thêm file
        lbl3 = QLabel(
            "<b>3. Chọn file ngân hàng câu hỏi trắc nghiệm (file trắc nghiệm):</b>"
        )
        lbl3.setStyleSheet("background-color: #ffffff; color: #1e293b;")
        form_layout.addWidget(lbl3)

        quiz_file_layout = QHBoxLayout()

        self.quiz_file_combo = QComboBox()
        self.quiz_file_combo.setCursor(Qt.PointingHandCursor)
        self.quiz_file_combo.setStyleSheet(common_input_style)

        self.add_quiz_btn = QPushButton("+ Thêm tài liệu")
        self.add_quiz_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #059669;
                color: #ffffff;
                font-size: 13px;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #047857;
            }
            QPushButton:pressed {
                background-color: #065f46;
            }
            """
        )
        self.add_quiz_btn.setCursor(Qt.PointingHandCursor)
        self.add_quiz_btn.clicked.connect(self.upload_quiz_file)

        quiz_file_layout.addWidget(self.quiz_file_combo, 1)
        quiz_file_layout.addWidget(self.add_quiz_btn)
        form_layout.addLayout(quiz_file_layout)

        # 4. Hình thức kiểm tra
        lbl4 = QLabel("<b>4. Hình thức kiểm tra:</b>")
        lbl4.setStyleSheet("background-color: #ffffff; color: #1e293b;")
        form_layout.addWidget(lbl4)

        self.type_combo = QComboBox()
        self.type_combo.setCursor(Qt.PointingHandCursor)
        self.type_combo.setStyleSheet(common_input_style)
        self.type_combo.addItems(["Trắc nghiệm", "Tự luận", "Trắc nghiệm + Tự luận"])
        self.type_combo.currentIndexChanged.connect(self.on_quiz_type_changed)
        form_layout.addWidget(self.type_combo)

        # 5. Số lượng câu
        count_layout = QHBoxLayout()

        lbl_mc_text = QLabel("Số câu trắc nghiệm (max 20):")
        lbl_mc_text.setStyleSheet("background-color: #ffffff; color: #1e293b;")
        self.mc_spin = QSpinBox()
        self.mc_spin.setStyleSheet(common_input_style)
        self.mc_spin.setRange(1, 20)
        self.mc_spin.setValue(10)

        lbl_es_text = QLabel("Số câu tự luận (max 5):")
        lbl_es_text.setStyleSheet("background-color: #ffffff; color: #1e293b;")
        self.essay_spin = QSpinBox()
        self.essay_spin.setStyleSheet(common_input_style)
        self.essay_spin.setRange(0, 5)
        self.essay_spin.setValue(2)

        count_layout.addWidget(lbl_mc_text)
        count_layout.addWidget(self.mc_spin)
        count_layout.addWidget(lbl_es_text)
        count_layout.addWidget(self.essay_spin)
        form_layout.addLayout(count_layout)

        # Nút tạo đề
        self.generate_btn = QPushButton("🚀 Tạo đề kiểm tra qua RAG & Cố vấn AI")
        self.generate_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #2563eb; 
                color: white; 
                font-weight: bold; 
                padding: 12px; 
                border-radius: 6px; 
                border: none;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:disabled {
                background-color: #94a3b8;
            }
            """
        )
        self.generate_btn.setCursor(Qt.PointingHandCursor)
        self.generate_btn.clicked.connect(self.trigger_generation)
        form_layout.addWidget(self.generate_btn)

        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

        self.on_subject_changed()
        self.on_quiz_type_changed()

    def upload_quiz_file(self):
        """Chọn file trắc nghiệm -> Lưu vào data/documents/ và cập nhật exam.json trong data/"""
        # Kiểm tra trước khi upload tài liệu
        selected_subject_name = self.subject_combo.currentText()
        subject_id = self.subjects_map.get(selected_subject_name, "")
        if not subject_id or "-- Chọn môn" in selected_subject_name:
            QMessageBox.warning(
                self,
                "Chưa chọn môn học",
                "⚠️ Vui lòng chọn môn học trước khi thêm tài liệu!",
            )
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn file tài liệu trắc nghiệm",
            "",
            "Tài liệu (*.docx *.pdf *.txt *.json);;Tất cả tệp (*.*)",
        )
        if not file_path:
            return

        try:
            filename = os.path.basename(file_path)

            data_dir = get_data_dir()
            doc_dir = data_dir / "documents"
            doc_dir.mkdir(parents=True, exist_ok=True)

            target_filename = (
                f"{subject_id}__{filename}" if subject_id != "all" else filename
            )
            dest_path = str(doc_dir / target_filename)

            if os.path.abspath(file_path) != os.path.abspath(dest_path):
                shutil.copy2(file_path, dest_path)

            exam_json_path = data_dir / "exam.json"

            exam_data = []
            if exam_json_path.exists():
                try:
                    with open(exam_json_path, "r", encoding="utf-8") as f:
                        exam_data = json.load(f)
                        if not isinstance(exam_data, list):
                            exam_data = []
                except Exception as e:
                    logger.warning(f"Không thể đọc file exam.json cũ: {e}")
                    exam_data = []

            new_file_entry = {
                "filename": filename,
                "saved_filename": target_filename,
                "filepath": dest_path,
                "subject_id": subject_id,
                "subject_name": selected_subject_name,
                "type": "quiz_bank",
            }

            exam_data = [
                item
                for item in exam_data
                if isinstance(item, dict) and item.get("filename") != filename
            ]
            exam_data.append(new_file_entry)

            with open(exam_json_path, "w", encoding="utf-8") as f:
                json.dump(exam_data, f, ensure_ascii=False, indent=4)

            self.on_subject_changed()

            index = self.quiz_file_combo.findText(filename)
            if index != -1:
                self.quiz_file_combo.setCurrentIndex(index)

            QMessageBox.information(
                self,
                "Thành công",
                f"Đã lưu file thành công vào hệ thống!",
            )

        except Exception as e:
            logger.exception("Lỗi khi lưu file trắc nghiệm")
            QMessageBox.critical(
                self,
                "Lỗi",
                f"Không thể lưu file tài liệu trắc nghiệm.\nChi tiết: {str(e)}",
            )

    def on_subject_changed(self):
        """ĐỌC DỮ LIỆU ĐỘNG TỪ DOCUMENT_SERVICE: Chỉ load những file PDF thực sự tồn tại."""
        self.docs_list_widget.clear()
        self.quiz_file_combo.clear()

        selected_name = self.subject_combo.currentText()
        subject_id = self.subjects_map.get(selected_name, "")

        if not subject_id or "-- Chọn môn" in selected_name:
            item = QListWidgetItem("⚠️ Vui lòng chọn môn học ở danh mục trên")
            item.setFlags(Qt.NoItemFlags)
            self.docs_list_widget.addItem(item)
            return

        if subject_id == "all":
            docs = (
                self.doc_service.list_all_documents()
                if hasattr(self.doc_service, "list_all_documents")
                else self.doc_service.list_documents(None)
            )
        else:
            docs = self.doc_service.list_documents(subject_id)

        self.quiz_file_combo.addItem(
            "-- Không chọn / Tự động dùng tất cả file trắc nghiệm --"
        )

        if docs:
            self.docs_list_widget.setEnabled(True)
            for doc in docs:
                item = QListWidgetItem(f"📄 {doc.filename}")
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked)
                self.docs_list_widget.addItem(item)
                self.quiz_file_combo.addItem(doc.filename)
        else:
            item = QListWidgetItem("⚠️ Chưa có tài liệu cho môn học này")
            item.setFlags(Qt.NoItemFlags)
            self.docs_list_widget.addItem(item)

        exam_json_path = get_data_dir() / "exam.json"
        if exam_json_path.exists():
            try:
                with open(exam_json_path, "r", encoding="utf-8") as f:
                    exam_list = json.load(f)
                    if isinstance(exam_list, list):
                        for item in exam_list:
                            if isinstance(item, dict) and item.get("filename"):
                                item_sub = item.get("subject_id", "all")
                                if subject_id == "all" or item_sub == subject_id:
                                    fn = item["filename"]
                                    if self.quiz_file_combo.findText(fn) == -1:
                                        self.quiz_file_combo.addItem(fn)
            except Exception as e:
                logger.warning(f"Lỗi đọc data/exam.json: {e}")

    def on_quiz_type_changed(self):
        selected_type = self.type_combo.currentText()
        if selected_type == "Trắc nghiệm":
            self.mc_spin.setEnabled(True)
            self.essay_spin.setEnabled(False)
            self.essay_spin.setValue(0)
        elif selected_type == "Tự luận":
            self.mc_spin.setEnabled(False)
            self.mc_spin.setValue(0)
            self.essay_spin.setEnabled(True)
            if self.essay_spin.value() == 0:
                self.essay_spin.setValue(2)
        else:
            self.mc_spin.setEnabled(True)
            if self.mc_spin.value() == 0:
                self.mc_spin.setValue(10)
            self.essay_spin.setEnabled(True)
            if self.essay_spin.value() == 0:
                self.essay_spin.setValue(2)

    def trigger_generation(self):
        if not self.generate_btn.isEnabled():
            return

        selected_subject_name = self.subject_combo.currentText()
        subject_id = self.subjects_map.get(selected_subject_name, "")

        # 1. KIỂM TRA CHƯA CHỌN MÔN HỌC
        if not subject_id or "-- Chọn môn" in selected_subject_name:
            QMessageBox.warning(
                self,
                "Chưa chọn môn học",
                "⚠️ Vui lòng chọn môn học trước khi bấm tạo đề kiểm tra!",
            )
            return

        selected_docs = []
        for i in range(self.docs_list_widget.count()):
            item = self.docs_list_widget.item(i)
            if item.checkState() == Qt.Checked:
                clean_name = item.text().replace("📄 ", "").strip()
                selected_docs.append(clean_name)

        selected_quiz_file = self.quiz_file_combo.currentText()
        specific_quiz_file = None
        if selected_quiz_file and not selected_quiz_file.startswith("--"):
            specific_quiz_file = selected_quiz_file
            if specific_quiz_file not in selected_docs:
                selected_docs.append(specific_quiz_file)

        # 2. KIỂM TRA CHƯA TÍCH CHỌN TÀI LIỆU
        if (
            not selected_docs
            or "Chưa có tài liệu" in selected_docs[0]
            or "Vui lòng chọn môn" in selected_docs[0]
        ):
            QMessageBox.warning(
                self,
                "Chưa chọn tài liệu",
                "⚠️ Vui lòng tích chọn ít nhất 1 tài liệu hoặc file trắc nghiệm để AI sinh đề thi!",
            )
            return

        config = {
            "subject_id": subject_id,
            "subject_name": selected_subject_name,
            "selected_documents": selected_docs,
            "specific_quiz_file": specific_quiz_file,
            "chapter": "Tất cả các chương",
            "quiz_type": self.type_combo.currentText(),
            "mc_count": self.mc_spin.value(),
            "essay_count": self.essay_spin.value(),
            "difficulty": "Trung bình",
        }
        self.exam_requested.emit(config)

    def set_generating_state(self, is_generating: bool):
        self.generate_btn.setEnabled(not is_generating)
        self.subject_combo.setEnabled(not is_generating)
        self.docs_list_widget.setEnabled(not is_generating)
        self.quiz_file_combo.setEnabled(not is_generating)
        self.add_quiz_btn.setEnabled(not is_generating)
        if is_generating:
            self.generate_btn.setText("Cố vấn AI đang phân tích tài liệu...")
        else:
            self.generate_btn.setText("Tạo đề kiểm tra")

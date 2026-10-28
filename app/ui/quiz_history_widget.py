# app/ui/quiz_history_widget.py
import json
import logging
import os
from datetime import datetime
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class ExamDetailDialog(QDialog):
    """Hộp thoại popup hiển thị chi tiết câu hỏi, đáp án đã chọn, nhận xét AI và giải thích."""

    def __init__(self, exam_record: dict, parent=None):
        super().__init__(parent)
        self.exam_record = exam_record
        self.setWindowTitle(
            f"Chi tiết bài làm - {exam_record.get('exam_title', 'Đề kiểm tra')}"
        )
        self.resize(750, 550)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        title_lbl = QLabel(
            f"<b>📝 {self.exam_record.get('exam_title', 'Đề kiểm tra')}</b>"
        )
        title_lbl.setStyleSheet("font-size: 16px; color: #1e293b; margin-bottom: 4px;")

        score_pct = float(self.exam_record.get("score", 0))
        score_10 = round(score_pct / 10.0, 1)

        mc_correct = self.exam_record.get("mc_correct", 0)
        mc_total = self.exam_record.get("mc_total", 0)

        info_lbl = QLabel(
            f"<b>Điểm tổng kết:</b> <span style='color: #2563eb;'>{score_10}/10</span> | "
            f"<b>Trắc nghiệm đúng:</b> {mc_correct}/{mc_total}"
        )
        info_lbl.setStyleSheet("font-size: 13px; color: #475569; margin-bottom: 10px;")

        layout.addWidget(title_lbl)
        layout.addWidget(info_lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px;"
        )

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(12)

        questions = self.exam_record.get("questions", [])
        if not questions:
            empty_lbl = QLabel(
                "Không tìm thấy dữ liệu câu hỏi chi tiết cho lượt thi này."
            )
            empty_lbl.setStyleSheet("color: #64748b; padding: 20px;")
            content_layout.addWidget(empty_lbl)
        else:
            for idx, q in enumerate(questions, start=1):
                q_box = QWidget()
                q_box.setStyleSheet(
                    "background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px;"
                )
                q_layout = QVBoxLayout(q_box)

                q_text = q.get("question", "")
                q_lbl = QLabel(f"<b>Câu {idx}:</b> {q_text}")
                q_lbl.setWordWrap(True)
                q_lbl.setStyleSheet("color: #0f172a; font-size: 13px;")
                q_layout.addWidget(q_lbl)

                opts = q.get("options", {})
                user_ans = q.get("user_answer", "")
                correct_ans = q.get("correct_answer")

                # Trắc nghiệm
                if opts:
                    for opt_k, opt_v in opts.items():
                        opt_lbl = QLabel(f"{opt_k}. {opt_v}")
                        if opt_k == correct_ans:
                            opt_lbl.setStyleSheet(
                                "color: #15803d; font-weight: bold; padding-left: 10px;"
                            )
                        elif opt_k == user_ans and user_ans != correct_ans:
                            opt_lbl.setStyleSheet(
                                "color: #b91c1c; font-weight: bold; padding-left: 10px;"
                            )
                        else:
                            opt_lbl.setStyleSheet("color: #475569; padding-left: 10px;")
                        q_layout.addWidget(opt_lbl)

                    exp = q.get("explanation", "Chưa có giải thích.")
                    exp_lbl = QLabel(f"💡 <b>Giải thích:</b> {exp}")
                    exp_lbl.setWordWrap(True)
                    exp_lbl.setStyleSheet(
                        "background-color: #f1f5f9; color: #334155; padding: 6px; border-radius: 4px; margin-top: 6px; font-size: 12px;"
                    )
                    q_layout.addWidget(exp_lbl)

                # Tự luận
                else:
                    essay_score = q.get("essay_score", 0.0)
                    essay_feedback = q.get("essay_feedback", "Đã ghi nhận bài làm.")
                    model_ans = q.get("model_answer", "Chưa có gợi ý.")

                    user_ans_lbl = QLabel(
                        f"✏️ <b>Bài làm của bạn:</b> {user_ans if user_ans else '(Chưa nhập câu trả lời)'}"
                    )
                    user_ans_lbl.setWordWrap(True)
                    user_ans_lbl.setStyleSheet(
                        "color: #1e293b; font-size: 12px; margin-top: 4px;"
                    )
                    q_layout.addWidget(user_ans_lbl)

                    ai_eval_lbl = QLabel(
                        f"🤖 <b>AI Đánh giá:</b> <span style='color: #2563eb;'><b>{essay_score}/10 điểm</b></span><br>"
                        f"💬 <b>Nhận xét:</b> {essay_feedback}"
                    )
                    ai_eval_lbl.setWordWrap(True)
                    ai_eval_lbl.setStyleSheet(
                        "background-color: #eff6ff; color: #1e3a8a; padding: 6px; border-radius: 4px; font-size: 12px; margin-top: 4px;"
                    )
                    q_layout.addWidget(ai_eval_lbl)

                    exp_lbl = QLabel(f"💡 <b>Gợi ý đáp án mẫu:</b> {model_ans}")
                    exp_lbl.setWordWrap(True)
                    exp_lbl.setStyleSheet(
                        "background-color: #f1f5f9; color: #334155; padding: 6px; border-radius: 4px; margin-top: 4px; font-size: 12px;"
                    )
                    q_layout.addWidget(exp_lbl)

                content_layout.addWidget(q_box)

        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

        btn_close = QPushButton("Đóng")
        btn_close.setFocusPolicy(Qt.NoFocus)
        btn_close.setStyleSheet(
            "background-color: #3b82f6; color: white; font-weight: bold; padding: 8px 16px; border-radius: 6px; outline: none;"
        )
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, 0, Qt.AlignRight)


class QuizHistoryWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.subjects_map = {
            "Tất cả môn học": "all",
            "Triết học Mác - Lênin": "triet_hoc",
            "Kinh tế chính trị Mác – Lênin": "kinh_te_chinh_tri",
            "Chủ nghĩa xã hội khoa học": "chu_nghia_xa_hoi",
            "Lịch sử Đảng Cộng sản Việt Nam": "lich_su_dang",
            "Tư tưởng Hồ Chí Minh": "tu_tuong_ho_chi_minh",
            "Pháp luật đại cương": "phap_luat",
        }
        self.raw_history_list = []
        self.filtered_history_list = []
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("background-color: #ffffff; color: #1e293b;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        toolbar_layout = QHBoxLayout()

        lbl_filter = QLabel("<b>Lọc theo môn học:</b>")
        lbl_filter.setStyleSheet("font-size: 13px; color: #334155;")

        self.filter_combo = QComboBox()
        self.filter_combo.setFocusPolicy(Qt.NoFocus)
        self.filter_combo.setStyleSheet(
            """
            QComboBox {
                background-color: #ffffff;
                color: #1e293b;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 12px;
                min-width: 180px;
                outline: none;
            }
            """
        )
        self.filter_combo.addItems(list(self.subjects_map.keys()))
        self.filter_combo.currentIndexChanged.connect(self.load_history)

        btn_refresh = QPushButton("🔄 Tải lại")
        btn_refresh.setFocusPolicy(Qt.NoFocus)
        btn_refresh.setStyleSheet(
            """
            QPushButton {
                background-color: #f1f5f9;
                color: #334155;
                font-weight: bold;
                padding: 6px 12px;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                outline: none;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
            }
            """
        )
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.clicked.connect(self.load_history)

        btn_clear = QPushButton("🗑️ Xóa lịch sử")
        btn_clear.setFocusPolicy(Qt.NoFocus)
        btn_clear.setStyleSheet(
            """
            QPushButton {
                background-color: #fee2e2;
                color: #991b1b;
                font-weight: bold;
                padding: 6px 14px;
                border: 1px solid #fca5a5;
                border-radius: 6px;
                outline: none;
            }
            QPushButton:hover {
                background-color: #fca5a5;
                color: #7f1d1d;
            }
            QPushButton:pressed {
                background-color: #f87171;
                color: #ffffff;
            }
            """
        )
        btn_clear.setCursor(Qt.PointingHandCursor)
        btn_clear.clicked.connect(self.clear_history)

        toolbar_layout.addWidget(lbl_filter)
        toolbar_layout.addWidget(self.filter_combo)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(btn_refresh)
        toolbar_layout.addWidget(btn_clear)

        layout.addLayout(toolbar_layout)

        hint_lbl = QLabel(
            "💡 <i>Nhấp đúp chuột (Double-click) vào bài thi để xem chi tiết đáp án & lời giải.</i>"
        )
        hint_lbl.setStyleSheet("color: #64748b; font-size: 12px;")
        layout.addWidget(hint_lbl)

        self.table = QTableWidget()
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            [
                "Tên bài kiểm tra",
                "Môn học",
                "Điểm số",
                "Dạng bài",
                "Thời gian nộp",
                "Thao tác",
            ]
        )

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)

        self.table.setStyleSheet(
            """
            QTableWidget {
                background-color: #ffffff;
                color: #1e293b;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                gridline-color: #f1f5f9;
                outline: none;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #0f172a;
                font-weight: bold;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #cbd5e1;
                outline: none;
            }
            """
        )

        self.table.itemDoubleClicked.connect(self.on_item_double_clicked)

        layout.addWidget(self.table)
        self.load_history()

    def get_subject_display_name(self, subject_id: str) -> str:
        for name, sid in self.subjects_map.items():
            if sid == subject_id:
                return name
        return subject_id

    def load_history(self):
        self.table.setRowCount(0)
        self.raw_history_list = []
        self.filtered_history_list = []
        history_path = os.path.join(os.getcwd(), "data", "exam_history.json")

        if not os.path.exists(history_path):
            return

        try:
            with open(history_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    self.raw_history_list = data

            selected_subject = self.filter_combo.currentText()
            filter_id = self.subjects_map.get(selected_subject, "all")

            for original_idx, item in reversed(list(enumerate(self.raw_history_list))):
                if not isinstance(item, dict):
                    continue
                if filter_id == "all" or item.get("subject_id") == filter_id:
                    self.filtered_history_list.append((original_idx, item))

            for row_idx, (orig_idx, item) in enumerate(self.filtered_history_list):
                self.table.insertRow(row_idx)

                title_item = QTableWidgetItem(
                    str(item.get("exam_title", "Đề kiểm tra"))
                )
                title_item.setData(Qt.UserRole, item)
                self.table.setItem(row_idx, 0, title_item)

                subj_name = self.get_subject_display_name(item.get("subject_id", ""))
                self.table.setItem(row_idx, 1, QTableWidgetItem(subj_name))

                # Hiển thị điểm theo thang 10
                score_pct = float(item.get("score", 0))
                score_10 = score_pct / 10.0

                if score_10 % 1 == 0:
                    score_str = f"{int(score_10)}/10"
                else:
                    score_str = f"{score_10:.1f}/10"

                score_item = QTableWidgetItem(score_str)
                score_item.setTextAlignment(Qt.AlignCenter)

                if score_10 >= 8.0:
                    score_item.setForeground(Qt.GlobalColor.darkGreen)
                elif score_10 >= 5.0:
                    score_item.setForeground(Qt.GlobalColor.darkYellow)
                else:
                    score_item.setForeground(Qt.GlobalColor.red)

                self.table.setItem(row_idx, 2, score_item)

                mc_total = item.get("mc_total", 0)
                questions = item.get("questions", [])

                has_essay = any(
                    isinstance(q, dict)
                    and (q.get("type") == "essay" or "model_answer" in q)
                    for q in questions
                )

                if mc_total > 0 and has_essay:
                    quiz_type_str = "TN + Tự luận"
                elif mc_total > 0:
                    quiz_type_str = "Trắc nghiệm"
                else:
                    quiz_type_str = "Tự luận"

                type_item = QTableWidgetItem(quiz_type_str)
                type_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row_idx, 3, type_item)

                submitted_raw = item.get("submitted_at", "")
                time_str = submitted_raw
                if submitted_raw:
                    try:
                        dt = datetime.fromisoformat(submitted_raw)
                        time_str = dt.strftime("%H:%M:%S - %d/%m/%Y")
                    except Exception:
                        pass

                time_item = QTableWidgetItem(time_str)
                time_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row_idx, 4, time_item)

                btn_delete_row = QPushButton("🗑️ Xóa")
                btn_delete_row.setFocusPolicy(Qt.NoFocus)
                btn_delete_row.setCursor(Qt.PointingHandCursor)
                btn_delete_row.setStyleSheet(
                    """
                    QPushButton {
                        background-color: #fee2e2;
                        color: #991b1b;
                        font-weight: bold;
                        border: 1px solid #fca5a5;
                        border-radius: 5px;
                        padding: 3px 8px;
                        font-size: 11px;
                        outline: none;
                    }
                    QPushButton:hover {
                        background-color: #fca5a5;
                        color: #7f1d1d;
                    }
                    QPushButton:pressed {
                        background-color: #f87171;
                        color: #ffffff;
                    }
                    """
                )
                btn_delete_row.clicked.connect(
                    lambda checked, target_idx=orig_idx: self.delete_single_record(
                        target_idx
                    )
                )

                btn_container = QWidget()
                btn_layout = QHBoxLayout(btn_container)
                btn_layout.setContentsMargins(4, 2, 4, 2)
                btn_layout.setAlignment(Qt.AlignCenter)
                btn_layout.addWidget(btn_delete_row)
                self.table.setCellWidget(row_idx, 5, btn_container)

        except Exception as e:
            logger.warning(f"Lỗi khi đọc file exam_history.json: {e}")

    def on_item_double_clicked(self, item: QTableWidgetItem):
        row = item.row()
        title_item = self.table.item(row, 0)
        if title_item:
            exam_record = title_item.data(Qt.UserRole)
            if exam_record:
                dialog = ExamDetailDialog(exam_record, self)
                dialog.exec()

    def delete_single_record(self, raw_index: int):
        history_path = os.path.join(os.getcwd(), "data", "exam_history.json")
        if not os.path.exists(history_path):
            return

        confirm = QMessageBox.question(
            self,
            "Xác nhận xóa",
            "Bạn có chắc chắn muốn xóa lượt làm bài kiểm tra này không?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if confirm == QMessageBox.Yes:
            try:
                if 0 <= raw_index < len(self.raw_history_list):
                    del self.raw_history_list[raw_index]
                    with open(history_path, "w", encoding="utf-8") as f:
                        json.dump(
                            self.raw_history_list, f, ensure_ascii=False, indent=2
                        )
                    self.load_history()
            except Exception as e:
                QMessageBox.critical(
                    self, "Lỗi", f"Không thể xóa lượt bài thi này: {e}"
                )

    def clear_history(self):
        history_path = os.path.join(os.getcwd(), "data", "exam_history.json")
        if not os.path.exists(history_path):
            return

        confirm = QMessageBox.question(
            self,
            "Xác nhận xóa",
            "Bạn có chắc chắn muốn xóa toàn bộ lịch sử làm bài kiểm tra?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if confirm == QMessageBox.Yes:
            try:
                with open(history_path, "w", encoding="utf-8") as f:
                    json.dump([], f, ensure_ascii=False, indent=2)
                self.load_history()
                QMessageBox.information(
                    self, "Thành công", "Đã xóa toàn bộ lịch sử làm bài."
                )
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Không thể xóa lịch sử: {e}")

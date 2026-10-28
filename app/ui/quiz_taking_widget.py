# app/ui/quiz_taking_widget.py
import html
import json
import logging
import re
from typing import Any, Dict

from app.services.gemini_service import GeminiService
from app.services.question_bank_service import QuestionBankService
from app.services.settings_manager import SettingsManager
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class QuizTakingWidget(QWidget):
    finished_exam = Signal()

    def __init__(self):
        super().__init__()
        self.current_exam = None
        self.user_answers = {}
        self.button_groups = []
        self.is_submitted = False
        self.qb_service = QuestionBankService()

        self.settings_manager = SettingsManager()
        api_key = self.settings_manager.get_api_key()
        self.ai_service = GeminiService(api_key=api_key)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: #ffffff; border: none;")

        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background: #ffffff;")
        self.form_layout = QVBoxLayout(self.content_widget)
        self.form_layout.setSpacing(12)
        self.form_layout.setAlignment(Qt.AlignTop)

        placeholder = QLabel(
            "Chưa có đề kiểm tra. Vui lòng sang tab 'Tạo đề kiểm tra mới' để bắt"
            " đầu."
        )
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet(
            "color: #64748b; background: #ffffff; font-size: 14px; padding: 40px;"
        )
        self.form_layout.addWidget(placeholder)

        scroll.setWidget(self.content_widget)
        layout.addWidget(scroll)

    def clear_previous_widgets(self):
        self.button_groups.clear()
        while self.form_layout.count():
            item = self.form_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

    def render_exam(self, exam_data: Dict[str, Any]):
        if not exam_data or not isinstance(exam_data, dict):
            return

        self.current_exam = exam_data
        self.is_submitted = False
        self.user_answers = {}

        self.clear_previous_widgets()
        self.form_layout.setAlignment(Qt.AlignTop)

        title_text = exam_data.get("exam_title", "Đề kiểm tra")
        title_lbl = QLabel(f"<b>📝 {title_text}</b>")
        title_lbl.setStyleSheet(
            "font-size: 18px; color: #1e293b; margin-bottom: 8px; background:"
            " #ffffff;"
        )
        self.form_layout.addWidget(title_lbl)

        questions = exam_data.get("questions", [])
        if not isinstance(questions, list):
            questions = []

        for idx, q in enumerate(questions, start=1):
            if not isinstance(q, dict):
                continue

            q_box = QFrame()
            q_box.setObjectName(f"q_box_{idx}")
            q_box.setStyleSheet(
                "background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px;"
                " padding: 14px;"
            )
            q_layout = QVBoxLayout(q_box)
            q_layout.setSpacing(10)

            q_type = q.get("type", "multiple_choice")
            q_text = html.escape(str(q.get("question") or ""))

            header_layout = QHBoxLayout()
            q_label = QLabel(f"<b>Câu {idx}:</b> {q_text}")
            q_label.setWordWrap(True)
            q_label.setTextFormat(Qt.RichText)
            q_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            q_label.setStyleSheet(
                "background: transparent; color: #0f172a; font-size: 14px; border:"
                " none; line-height: 1.5;"
            )
            header_layout.addWidget(q_label, 1)

            status_lbl = QLabel("")
            status_lbl.setObjectName(f"status_lbl_{idx}")
            status_lbl.setStyleSheet("background: transparent; border: none;")
            header_layout.addWidget(status_lbl, 0, Qt.AlignRight | Qt.AlignTop)
            q_layout.addLayout(header_layout)

            source = q.get("source", {})
            if isinstance(source, dict) and source.get("document"):
                doc_info = (
                    f"📄 Nguồn trích dẫn: {source.get('document')} (Trang"
                    f" {source.get('page', 1)})"
                )
                src_lbl = QLabel(doc_info)
                src_lbl.setWordWrap(True)
                src_lbl.setStyleSheet(
                    "color: #64748b; font-size: 11px; background: transparent; border:"
                    " none;"
                )
                q_layout.addWidget(src_lbl)

            if q_type == "multiple_choice":
                options = q.get("options", {})
                if not isinstance(options, dict):
                    options = {}

                wrapper_map = {}

                self.user_answers[idx] = {
                    "question_data": q,
                    "type": "mc",
                    "wrapper_map": wrapper_map,
                    "correct": q.get("correct_answer", ""),
                    "selected": None,
                    "box_widget": q_box,
                    "status_label": status_lbl,
                }

                for opt_key in sorted(options.keys()):
                    opt_val = options[opt_key]

                    # DẠNG CARD BẤM TRỰC TIẾP (BỎ HOÀN TOÀN RADIO BUTTON)
                    opt_frame = QFrame()
                    opt_frame.setCursor(Qt.PointingHandCursor)
                    opt_frame.setSizePolicy(
                        QSizePolicy.Expanding, QSizePolicy.Preferred
                    )

                    # Style mặc định chưa chọn: Nền sáng nhẹ, viền xám
                    opt_frame.setStyleSheet(
                        """
                        QFrame {
                            background-color: #f8fafc;
                            border: 1.5px solid #cbd5e1;
                            border-radius: 8px;
                            padding: 10px 14px;
                        }
                        QFrame:hover {
                            background-color: #eff6ff;
                            border-color: #3b82f6;
                        }
                    """
                    )

                    opt_layout = QHBoxLayout(opt_frame)
                    opt_layout.setContentsMargins(12, 10, 12, 10)
                    opt_layout.setSpacing(12)

                    # Badge hiển thị chữ cái A, B, C, D nổi bật ở góc trái
                    key_badge = QLabel(f"<b>{opt_key}</b>")
                    key_badge.setFixedSize(28, 28)
                    key_badge.setAlignment(Qt.AlignCenter)
                    key_badge.setStyleSheet(
                        """
                        QLabel {
                            background-color: #e2e8f0;
                            color: #1e293b;
                            font-size: 13px;
                            border-radius: 14px;
                            border: none;
                        }
                    """
                    )

                    # Text đáp án tự động dãn dòng trọn vẹn 100%
                    opt_lbl = QLabel(html.escape(str(opt_val)))
                    opt_lbl.setWordWrap(True)
                    opt_lbl.setTextFormat(Qt.RichText)
                    opt_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                    opt_lbl.setStyleSheet(
                        """
                        QLabel {
                            color: #1e293b;
                            font-size: 13.5px;
                            background: transparent;
                            border: none;
                            line-height: 1.5;
                        }
                    """
                    )

                    opt_layout.addWidget(key_badge, 0, Qt.AlignLeft | Qt.AlignTop)
                    opt_layout.addWidget(opt_lbl, 1)

                    wrapper_map[opt_key] = (opt_frame, key_badge, opt_lbl)
                    q_layout.addWidget(opt_frame)

                    # Bắt sự kiện Click vào cả thẻ card
                    def make_click_handler(k=opt_key, q_i=idx):
                        def handler(event=None):
                            if not self.is_submitted:
                                self.select_card_option(q_i, k)

                        return handler

                    click_h = make_click_handler()
                    opt_frame.mousePressEvent = click_h
                    opt_lbl.mousePressEvent = click_h
                    key_badge.mousePressEvent = click_h

            else:
                txt_edit = QTextEdit()
                txt_edit.setPlaceholderText(
                    "Nhập câu trả lời tự luận của bạn tại đây..."
                )
                txt_edit.setMaximumHeight(110)
                txt_edit.setStyleSheet(
                    "background: #ffffff; color: #1e293b; border: 1px solid #cbd5e1;"
                    " border-radius: 6px; padding: 6px;"
                )
                self.user_answers[idx] = {
                    "question_data": q,
                    "type": "essay",
                    "widget": txt_edit,
                    "box_widget": q_box,
                    "status_label": status_lbl,
                }
                q_layout.addWidget(txt_edit)

            review_box = QFrame()
            review_box.setObjectName(f"review_box_{idx}")
            review_box.setVisible(False)
            review_layout = QVBoxLayout(review_box)
            review_layout.setContentsMargins(8, 8, 8, 8)
            q_layout.addWidget(review_box)

            self.user_answers[idx]["review_box"] = review_box
            self.form_layout.addWidget(q_box)

        # Nút nộp bài
        self.submit_btn = QPushButton("Nộp bài")
        self.submit_btn.setFocusPolicy(Qt.NoFocus)
        self.submit_btn.setStyleSheet(
            "background-color: #10b981; color: white; font-weight: bold; padding:"
            " 12px; border-radius: 6px; font-size: 14px; outline: none;"
        )
        self.submit_btn.setCursor(Qt.PointingHandCursor)
        self.submit_btn.clicked.connect(self.handle_submit)
        self.form_layout.addWidget(self.submit_btn)

    def select_card_option(self, q_idx: int, selected_key: str):
        """Cập nhật giao diện khi chọn/đổi đáp án (Bấm vào thẻ chuyển sang màu xanh dương dương)."""
        if self.is_submitted or q_idx not in self.user_answers:
            return

        self.user_answers[q_idx]["selected"] = selected_key
        wrapper_map = self.user_answers[q_idx]["wrapper_map"]

        for k, (frame_w, badge_w, lbl_w) in wrapper_map.items():
            if k == selected_key:
                # Thẻ ĐƯỢC CHỌN: Đổi sang viền xanh đậm #2563eb, nền xanh nhạt #eff6ff
                frame_w.setStyleSheet(
                    """
                    QFrame {
                        background-color: #eff6ff;
                        border: 2px solid #2563eb;
                        border-radius: 8px;
                        padding: 10px 14px;
                    }
                """
                )
                badge_w.setStyleSheet(
                    """
                    QLabel {
                        background-color: #2563eb;
                        color: #ffffff;
                        font-size: 13px;
                        font-weight: bold;
                        border-radius: 14px;
                        border: none;
                    }
                """
                )
                lbl_w.setStyleSheet(
                    """
                    QLabel {
                        color: #1e3a8a;
                        font-size: 13.5px;
                        font-weight: bold;
                        background: transparent;
                        border: none;
                        line-height: 1.5;
                    }
                """
                )
            else:
                # Thẻ KHÔNG CHỌN: Giữ nguyên style xám nhẹ mặc định
                frame_w.setStyleSheet(
                    """
                    QFrame {
                        background-color: #f8fafc;
                        border: 1.5px solid #cbd5e1;
                        border-radius: 8px;
                        padding: 10px 14px;
                    }
                    QFrame:hover {
                        background-color: #eff6ff;
                        border-color: #3b82f6;
                    }
                """
                )
                badge_w.setStyleSheet(
                    """
                    QLabel {
                        background-color: #e2e8f0;
                        color: #1e293b;
                        font-size: 13px;
                        border-radius: 14px;
                        border: none;
                    }
                """
                )
                lbl_w.setStyleSheet(
                    """
                    QLabel {
                        color: #1e293b;
                        font-size: 13.5px;
                        background: transparent;
                        border: none;
                        line-height: 1.5;
                    }
                """
                )

    def grade_essay_with_ai(
        self, question_text: str, user_answer: str, model_answer: str
    ) -> dict:
        if not user_answer or not user_answer.strip():
            return {"score_10": 0.0, "feedback": "Sinh viên chưa nhập câu trả lời."}

        prompt = f"""You are an expert AI grader for political theory exams. You must output valid JSON only.

Chấm điểm câu hỏi tự luận sau trên thang điểm 10.
[CÂU HỎI]: {question_text}
[ĐÁP ÁN MẪU]: {model_answer}
[BÀI LÀM SINH VIÊN]: {user_answer}

YÊU CẦU:
1. Chấm điểm bài làm trên thang 10 (cho phép số thập phân như 6.5, 7.5, 8.0).
2. Viết nhận xét ngắn (1-2 câu).
3. Trả về đúng 1 JSON object:
{{"score_10": 8.0, "feedback": "Bài làm đầy đủ ý cốt lõi."}}
"""
        try:
            api_key = self.settings_manager.get_api_key()
            if api_key:
                self.ai_service.set_api_key(api_key)

            response_raw = self.ai_service.generate(
                prompt=prompt, response_mime_type="application/json"
            )
            match = re.search(r"\{.*\}", response_raw, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                return {
                    "score_10": float(data.get("score_10", 5.0)),
                    "feedback": str(
                        data.get("feedback", "Đã đối chiếu với đáp án mẫu.")
                    ),
                }
        except Exception as e:
            logger.error(f"Lỗi chấm tự luận: {e}")

        return {
            "score_10": 5.0,
            "feedback": (
                "Đã lưu bài làm. (Không thể kết nối AI để lấy phản hồi chi tiết)."
            ),
        }

    def handle_submit(self):
        if self.is_submitted:
            return

        self.is_submitted = True
        self.submit_btn.setEnabled(False)
        self.submit_btn.setText("⏳ Đang chấm bài...")
        QApplication.processEvents()

        mc_correct = 0
        mc_total = 0
        total_questions = len(self.user_answers)
        total_score_accumulated = 0.0
        detailed_questions = []

        for q_idx, data in self.user_answers.items():
            q_type = data.get("type")
            q_obj = dict(data.get("question_data", {}))
            review_box = data.get("review_box")
            status_lbl = data.get("status_label")

            if q_type == "mc":
                mc_total += 1
                correct_key = data.get("correct", "")
                selected_key = data.get("selected")
                wrapper_map = data.get("wrapper_map") or {}

                is_correct = (selected_key is not None) and (
                    selected_key == correct_key
                )
                if is_correct:
                    mc_correct += 1
                    total_score_accumulated += 10.0

                q_obj["user_answer"] = selected_key

                if status_lbl is not None:
                    if is_correct:
                        status_lbl.setText(
                            "<span style='color: #16a34a; font-weight: bold; font-size:"
                            " 14px;'>✅ Đúng</span>"
                        )
                    else:
                        status_lbl.setText(
                            "<span style='color: #dc2626; font-weight: bold; font-size:"
                            " 14px;'>❌ Sai</span>"
                        )

                # Đổi màu sau khi NỘP BÀI: Đúng hiện XANH LÁ, Chọn Sai hiện ĐỎ
                for r_key, (frame_w, badge_w, lbl_w) in wrapper_map.items():
                    if r_key == correct_key:
                        frame_w.setStyleSheet(
                            "background: #dcfce7; border: 2px solid #22c55e; border-radius:"
                            " 8px; padding: 10px 14px;"
                        )
                        badge_w.setStyleSheet(
                            "background-color: #22c55e; color: #ffffff; font-size: 13px;"
                            " font-weight: bold; border-radius: 14px; border: none;"
                        )
                        lbl_w.setStyleSheet(
                            "color: #15803d; font-weight: bold; font-size: 13.5px;"
                            " background: transparent; border: none;"
                        )
                    elif r_key == selected_key and not is_correct:
                        frame_w.setStyleSheet(
                            "background: #fee2e2; border: 2px solid #ef4444; border-radius:"
                            " 8px; padding: 10px 14px;"
                        )
                        badge_w.setStyleSheet(
                            "background-color: #ef4444; color: #ffffff; font-size: 13px;"
                            " font-weight: bold; border-radius: 14px; border: none;"
                        )
                        lbl_w.setStyleSheet(
                            "color: #b91c1c; font-weight: bold; font-size: 13.5px;"
                            " background: transparent; border: none;"
                        )
                    else:
                        frame_w.setStyleSheet(
                            "background: #f8fafc; border: 1px solid #e2e8f0; border-radius:"
                            " 8px; padding: 10px 14px;"
                        )
                        badge_w.setStyleSheet(
                            "background-color: #cbd5e1; color: #64748b; font-size: 13px;"
                            " border-radius: 14px; border: none;"
                        )
                        lbl_w.setStyleSheet(
                            "color: #94a3b8; font-size: 13.5px; background: transparent;"
                            " border: none;"
                        )

                opts = q_obj.get("options", {})
                user_opt_text = (
                    f"{selected_key}. {opts.get(selected_key, '')}"
                    if selected_key and selected_key in opts
                    else "Chưa chọn đáp án"
                )
                corr_opt_text = (
                    f"{correct_key}. {opts.get(correct_key, '')}"
                    if correct_key in opts
                    else correct_key
                )

                explanation = (
                    q_obj.get("explanation") or "Chưa có giải thích cho câu này."
                )

                review_layout = review_box.layout()
                review_box.setStyleSheet(
                    "background-color: #f8fafc; border-top: 1px solid #e2e8f0;"
                    " border-radius: 4px; margin-top: 8px;"
                )

                ans_info = QLabel(
                    f"<b>Bạn chọn:</b> <span style='color: {'#15803d' if is_correct else '#dc2626'};'>{user_opt_text}</span><br>"
                    f"<b>Đáp án đúng:</b> <span style='color: #15803d;'>{corr_opt_text}</span>"
                )
                ans_info.setWordWrap(True)
                ans_info.setStyleSheet("font-size: 13px; margin-bottom: 4px;")

                exp_lbl = QLabel(f"💡 <b>Giải thích:</b> {explanation}")
                exp_lbl.setWordWrap(True)
                exp_lbl.setStyleSheet(
                    "color: #334155; font-size: 13px; background: #f1f5f9; padding:"
                    " 8px; border-radius: 4px;"
                )

                review_layout.addWidget(ans_info)
                review_layout.addWidget(exp_lbl)
                review_box.setVisible(True)

            elif q_type == "essay":
                txt_edit = data.get("widget")
                user_text = txt_edit.toPlainText().strip() if txt_edit else ""
                if txt_edit:
                    txt_edit.setReadOnly(True)

                q_obj["user_answer"] = user_text

                model_ans = q_obj.get("model_answer") or "Chưa có gợi ý trả lời."
                q_text = q_obj.get("question", "")

                ai_result = self.grade_essay_with_ai(q_text, user_text, model_ans)
                essay_score = float(ai_result.get("score_10", 0.0))
                essay_feedback = ai_result.get("feedback", "")

                q_obj["essay_score"] = essay_score
                q_obj["essay_feedback"] = essay_feedback
                total_score_accumulated += essay_score

                status_lbl.setText(
                    f"<span style='color: #2563eb; font-weight: bold;'>🤖 Điểm AI:"
                    f" {essay_score}/10</span>"
                )

                review_layout = review_box.layout()
                review_box.setStyleSheet(
                    "background-color: #f8fafc; border-top: 1px solid #e2e8f0;"
                    " border-radius: 4px; margin-top: 8px;"
                )

                ai_eval_lbl = QLabel(
                    "🤖 <b>AI Đánh giá:</b> <span style='color: #2563eb;'><b>"
                    f"{essay_score}/10 điểm</b></span><br>💬 <b>Nhận xét:</b>"
                    f" {essay_feedback}"
                )
                ai_eval_lbl.setWordWrap(True)
                ai_eval_lbl.setStyleSheet(
                    "font-size: 13px; color: #0f172a; margin-bottom: 6px;"
                )

                guide_lbl = QLabel(f"💡 <b>Gợi ý đáp án mẫu:</b> {model_ans}")
                guide_lbl.setWordWrap(True)
                guide_lbl.setStyleSheet(
                    "color: #334155; font-size: 12px; background: #eff6ff; padding:"
                    " 8px; border-radius: 4px;"
                )

                review_layout.addWidget(ai_eval_lbl)
                review_layout.addWidget(guide_lbl)
                review_box.setVisible(True)

            detailed_questions.append(q_obj)

        avg_score_10 = (
            (total_score_accumulated / total_questions) if total_questions > 0 else 0.0
        )
        score_percentage = avg_score_10 * 10.0

        history_record = {
            "exam_id": self.current_exam.get("exam_id"),
            "subject_id": self.current_exam.get("subject_id"),
            "exam_title": self.current_exam.get("exam_title"),
            "score": round(score_percentage, 1),
            "mc_correct": mc_correct,
            "mc_total": mc_total,
            "questions": detailed_questions,
        }

        self.qb_service.save_exam_history(history_record)

        score_msg = (
            "🎉 <b>Đã chấm xong bài làm!</b>\n\n• <b>Điểm trung bình toàn bài:</b>"
            " <span style='color: #2563eb; font-size:"
            f" 16px;'><b>{round(avg_score_10, 1)} / 10</b></span>\n• <b>Tổng số câu"
            f" hỏi:</b> {total_questions} (Trắc nghiệm: {mc_total}, Tự luận:"
            f" {total_questions - mc_total})\n\nBạn có thể cuộn lên để xem lại chi"
            " tiết giải thích và nhận xét từng câu."
        )

        QMessageBox.information(self, "Kết quả kiểm tra", score_msg)

        self.submit_btn.setEnabled(True)
        self.submit_btn.setText("Hoàn thành bài làm")
        self.submit_btn.setStyleSheet(
            "background-color: #3b82f6; color: white; font-weight: bold; padding:"
            " 12px; border-radius: 6px; font-size: 14px; outline: none;"
        )
        try:
            self.submit_btn.clicked.disconnect()
        except (TypeError, RuntimeError):
            pass
        self.submit_btn.clicked.connect(self.handle_finish_exam)

    def handle_finish_exam(self):
        self.is_submitted = False
        self.user_answers = {}
        self.clear_previous_widgets()

        placeholder = QLabel(
            "Chưa có đề kiểm tra. Vui lòng sang tab 'Tạo đề kiểm tra mới' để bắt"
            " đầu."
        )
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet(
            "color: #64748b; background: #ffffff; font-size: 14px; padding: 40px;"
        )
        self.form_layout.addWidget(placeholder)

        self.finished_exam.emit()

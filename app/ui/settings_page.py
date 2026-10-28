# app/ui/settings_page.py
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QGraphicsDropShadowEffect,
)
from PySide6.QtCore import (
    Qt,
    QPropertyAnimation,
    QEasingCurve,
    QSequentialAnimationGroup,
)
from PySide6.QtGui import QColor
from app.services.settings_manager import SettingsManager


class SettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.settings_manager = SettingsManager()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("⚙️ CÀI ĐẶT HỆ THỐNG & API KEY")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a365d;")
        layout.addWidget(title)

        lbl_key = QLabel("Gemini / Groq API Key:")
        lbl_key.setStyleSheet("color: #334155; font-size: 13px; font-weight: 500;")
        layout.addWidget(lbl_key)

        key_input_container = QHBoxLayout()
        key_input_container.setSpacing(6)

        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setPlaceholderText("Nhập API Key tại đây...")
        self.key_input.setStyleSheet(
            """
            QLineEdit {
                padding: 8px; 
                border: 1px solid #cbd5e1; 
                border-radius: 4px;
                background-color: #ffffff;
                color: #0f172a;
            }
            QLineEdit:focus {
                border: 1px solid #2563eb;
            }
            """
        )

        # Nút icon con mắt -> ÉP HÌNH BÀN TAY KHI ĐƯA CHUỘT VÀO
        self.toggle_eye_btn = QPushButton("👁️")
        self.toggle_eye_btn.setToolTip("Bật/Tắt hiển thị API Key")
        self.toggle_eye_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_eye_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #f1f5f9;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
            }
            """
        )
        self.toggle_eye_btn.clicked.connect(self.toggle_api_key_visibility)

        key_input_container.addWidget(self.key_input)
        key_input_container.addWidget(self.toggle_eye_btn)
        layout.addLayout(key_input_container)

        current_key = self.settings_manager.get_api_key()
        if current_key:
            self.key_input.setText(current_key)

        self.status_lbl = QLabel()
        if current_key:
            self.status_lbl.setText("● API Key đã được cấu hình")
            self.status_lbl.setStyleSheet("color: #10b981; font-weight: bold;")
        else:
            self.status_lbl.setText("○ Chưa cấu hình API Key")
            self.status_lbl.setStyleSheet("color: #ef4444; font-weight: bold;")
        layout.addWidget(self.status_lbl)

        # Nút Lưu -> ÉP HÌNH BÀN TAY KHI ĐƯA CHUỘT VÀO
        self.save_btn = QPushButton("Lưu cấu hình")
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #2563eb; 
                color: white; 
                padding: 10px; 
                font-weight: bold; 
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            """
        )
        self.save_btn.clicked.connect(self.save_config)
        layout.addWidget(self.save_btn)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(12)
        shadow.setColor(QColor(37, 99, 235, 80))
        shadow.setOffset(0, 3)
        self.save_btn.setGraphicsEffect(shadow)

        layout.addStretch()

    def toggle_api_key_visibility(self):
        if self.key_input.echoMode() == QLineEdit.Password:
            self.key_input.setEchoMode(QLineEdit.Normal)
            self.toggle_eye_btn.setText("🙈")
        else:
            self.key_input.setEchoMode(QLineEdit.Password)
            self.toggle_eye_btn.setText("👁️")

    def animate_button(self, callback):
        anim_press = QPropertyAnimation(self.save_btn, b"maximumWidth")
        anim_press.setDuration(100)
        anim_press.setStartValue(self.save_btn.width())
        anim_press.setEndValue(int(self.save_btn.width() * 0.95))
        anim_press.setEasingCurve(QEasingCurve.OutQuad)

        anim_release = QPropertyAnimation(self.save_btn, b"maximumWidth")
        anim_release.setDuration(150)
        anim_release.setStartValue(int(self.save_btn.width() * 0.95))
        anim_release.setEndValue(16777215)
        anim_release.setEasingCurve(QEasingCurve.OutElastic)

        self.anim_group = QSequentialAnimationGroup()
        self.anim_group.addAnimation(anim_press)
        self.anim_group.addAnimation(anim_release)
        self.anim_group.finished.connect(callback)
        self.anim_group.start()

    def save_config(self):
        def process_save():
            key = self.key_input.text().strip()
            if not key:
                QMessageBox.warning(self, "Cảnh báo", "Vui lòng nhập API Key hợp lệ!")
                return

            self.settings_manager.save_api_key(key)
            self.status_lbl.setText("● API Key đã được cấu hình")
            self.status_lbl.setStyleSheet("color: #10b981; font-weight: bold;")

            self.save_btn.setText("✓ Đã lưu thành công!")
            self.save_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: #059669; 
                    color: white; 
                    padding: 10px; 
                    font-weight: bold; 
                    border-radius: 6px;
                    border: none;
                }
                """
            )

            QMessageBox.information(
                self, "Thành công", "Đã lưu cấu hình API Key thành công vào hệ thống!"
            )

            self.save_btn.setText("Lưu cấu hình")
            self.save_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: #2563eb; 
                    color: white; 
                    padding: 10px; 
                    font-weight: bold; 
                    border-radius: 6px;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #1d4ed8;
                }
                """
            )

        self.animate_button(process_save)

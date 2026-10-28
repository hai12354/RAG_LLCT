# app/ui/help_page.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextBrowser


class HelpPage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel(
            "❓ HƯỚNG DẪN SỬ DỤNG PHẦN MỀM TRỢ LÝ ẢO RAG (DÀNH CHO NGƯỜI DÙNG MỚI)"
        )
        title.setStyleSheet(
            """
            font-size: 18px;
            font-weight: bold;
            color: #1a365d;
            padding: 4px 0;
        """
        )
        layout.addWidget(title)

        # Sử dụng QTextBrowser để hỗ trợ link HTML mở trình duyệt ngoài
        help_text = QTextBrowser()
        help_text.setReadOnly(True)
        help_text.setOpenExternalLinks(True)
        help_text.setStyleSheet(
            """
            QTextBrowser {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 12px;
            }
        """
        )

        help_text.setHtml(
            """
        <html>
        <head>
        <style>
            body {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                color: #1e293b;
                line-height: 1.6;
                margin: 0;
                padding: 10px;
            }
            h2 {
                color: #1e3a8a;
                font-size: 15px;
                font-weight: bold;
                border-bottom: 2px solid #cbd5e1;
                padding-bottom: 6px;
                margin-top: 22px;
                margin-bottom: 10px;
            }
            h3 {
                color: #0f172a;
                font-size: 13px;
                font-weight: bold;
                margin-top: 14px;
                margin-bottom: 6px;
            }
            p, li {
                color: #334155;
                margin-bottom: 8px;
            }
            ol, ul {
                padding-left: 20px;
                margin-top: 4px;
                margin-bottom: 10px;
            }
            hr {
                border: none;
                border-top: 1px solid #e2e8f0;
                margin: 18px 0;
            }
            code {
                background-color: #f1f5f9;
                color: #0f172a;
                padding: 2px 6px;
                border-radius: 4px;
                font-family: Consolas, monospace;
                font-size: 12px;
            }
            a {
                color: #2563eb;
                font-weight: bold;
                text-decoration: none;
            }
            a:hover {
                text-decoration: underline;
            }
            .note-box {
                background-color: #f0fdf4;
                border: 1px solid #bbf7d0;
                border-left: 4px solid #22c55e;
                padding: 10px 12px;
                border-radius: 6px;
                margin: 10px 0;
                color: #166534;
            }
            .info-box {
                background-color: #eff6ff;
                border: 1px solid #bfdbfe;
                border-left: 4px solid #3b82f6;
                padding: 10px 12px;
                border-radius: 6px;
                margin: 10px 0;
                color: #1e40af;
            }
            .warning-box {
                background-color: #fffbeb;
                border: 1px solid #fde68a;
                border-left: 4px solid #f59e0b;
                padding: 10px 12px;
                border-radius: 6px;
                margin: 10px 0;
                color: #92400e;
            }
            .process-box {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 14px;
                text-align: center;
                font-weight: bold;
                color: #0f172a;
                line-height: 1.8;
            }
            .step-title {
                color: #2563eb;
                font-weight: bold;
            }
        </style>
        </head>
        <body>

        <h2>1. Giới thiệu tổng quan về phần mềm</h2>
        <p>
        <b>Trợ lý ảo RAG Lý luận Chính trị</b> là ứng dụng thông minh hỗ trợ sinh viên tra cứu kiến thức, hỏi đáp RAG và tạo đề ôn thi trắc nghiệm - tự luận các môn Lý luận chính trị & Pháp luật (Triết học Mác – Lênin, Kinh tế chính trị, CNXH khoa học, Tư tưởng Hồ Chí Minh, Lịch sử Đảng, Pháp luật đại cương).
        </p>
        <p>
        Phần mềm kết hợp công nghệ <b>RAG (Retrieval-Augmented Generation)</b> cùng mô hình ngôn ngữ lớn như <b>Google Gemini</b> và <b>Groq Cloud</b>. Hệ thống tự động đọc và trích xuất dữ liệu từ các file giáo trình, ngân hàng câu hỏi do bạn tải lên để đưa ra đáp án chuẩn xác kèm trích dẫn nguồn cụ thể.
        </p>

        <hr>

        <h2>2. Quy trình 4 bước cho khách hàng lần đầu sử dụng</h2>
        <div class="process-box">
            <span class="step-title">Bước 1:</span> Lấy & Cấu hình API Key (Gemini / Groq) tại mục Cài đặt &nbsp;➔&nbsp;<br>
            <span class="step-title">Bước 2:</span> Quản lý & Tải lên tài liệu giáo trình / bài giảng theo từng môn &nbsp;➔&nbsp;<br>
            <span class="step-title">Bước 3:</span> Trải nghiệm Hỏi đáp RAG hoặc Tạo đề thi từ ngân hàng trắc nghiệm &nbsp;➔&nbsp;<br>
            <span class="step-title">Bước 4:</span> Làm bài kiểm tra, xem đáp án giải thích & theo dõi Lịch sử
        </div>

        <hr>

        <h2>3. Hướng dẫn lấy API Key miễn phí (Dành cho lần đầu cài đặt)</h2>
        <p>Để phần mềm kết nối được với trí tuệ nhân tạo AI, bạn chỉ cần nạp 1 trong 2 loại API Key dưới đây (hoặc cả hai):</p>

        <h3>3.1. Hướng dẫn lấy Google Gemini API Key</h3>
        <ol>
            <li>Truy cập trang cấp khóa AI của Google tại: <a href="https://aistudio.google.com/app/apikey">Google AI Studio API Key</a></li>
            <li>Đăng nhập bằng tài khoản Google (Gmail) của bạn.</li>
            <li>Nhấn nút <b>"Create API Key"</b> (Tạo khóa API) ➔ Chọn một dự án bất kỳ hoặc chọn <i>Create API key in new project</i>.</li>
            <li>Sao chép (Copy) chuỗi mã khóa vừa tạo.</li>
        </ol>

        <h3>3.2. Hướng dẫn lấy Groq API Key (Tốc độ siêu nhanh)</h3>
        <ol>
            <li>Truy cập trang quản lý khóa của Groq Cloud tại: <a href="https://console.groq.com/keys">Groq Cloud Console API Keys</a></li>
            <li>Đăng nhập nhanh bằng tài khoản Google/GitHub.</li>
            <li>Nhấn nút <b>"Create API Key"</b> ➔ Đặt tên gợi nhớ và bấm <b>Submit</b>.</li>
            <li>Sao chép (Copy) chuỗi mã khóa Groq hiển thị trên màn hình.</li>
        </ol>

        <h3>3.3. Nạp API Key vào phần mềm</h3>
        <ol>
            <li>Trên giao diện phần mềm, mở mục <b>⚙ Cài đặt</b> ở menu bên trái.</li>
            <li>Dán khóa Gemini API hoặc Groq API vào đúng ô tương ứng.</li>
            <li>Nhấn nút <b>Lưu cài đặt</b>. Hệ thống sẽ lưu trữ mã khóa an toàn trên máy tính của bạn.</li>
        </ol>

        <div class="info-box">
            <b>💡 Mẹo cho lần đầu:</b> Bạn chỉ cần cài đặt khóa 1 lần duy nhất, phần mềm sẽ tự động nhớ mã khóa cho các lần truy cập sau.
        </div>

        <hr>

        <h2>4. Hướng dẫn sử dụng các tính năng chính</h2>

        <h3>4.1. Quản lý Môn học & Tải tài liệu (📚 Quản lý môn học)</h3>
        <ul>
            <li>Chọn môn học cần quản lý (Triết học, Kinh tế chính trị, CNXHKH,...).</li>
            <li>Bấm <b>+ Thêm tài liệu</b> để tải các file bài giảng, giáo trình (định dạng <code>.pdf</code>, <code>.docx</code>, <code>.txt</code>) vào hệ thống.</li>
        </ul>

        <h3>4.2. Hỏi đáp kiến thức RAG (💬 Hỏi đáp)</h3>
        <ul>
            <li>Chọn môn học cần tra cứu ➔ Nhập câu hỏi thắc mắc vào khung chat và gửi.</li>
            <li>AI sẽ đọc tài liệu môn đó và trả lời chính xác kèm <b>trích dẫn tên file & số trang nguồn gốc</b>.</li>
        </ul>

        <h3>4.3. Tạo đề kiểm tra & Luyện tập (📝 Luyện tập)</h3>
        <ol>
            <li><b>Mục 1 (Chọn môn):</b> Chọn môn học muốn thi hoặc chọn <i>"Tất cả môn / Tổng hợp"</i> nếu tài liệu chứa nội dung tổng hợp.</li>
            <li><b>Mục 2a (Tài liệu giáo trình):</b> Tích chọn file lý thuyết tham khảo.</li>
            <li><b>Mục 2b (File trắc nghiệm):</b> 
                <ul>
                    <li>Chọn file câu hỏi có sẵn từ danh sách.</li>
                    <li>Hoặc bấm nút <b>+ Thêm tài liệu</b> để tải lên file trắc nghiệm mới (ví dụ <code>300 câu TN...docx</code>). File sẽ được tự động lưu vào <code>data/documents/</code> và ghi nhận ở <code>data/exam.json</code>.</li>
                </ul>
            </li>
            <li><b>Mục 3, 4, 5:</b> Tùy chọn Số lượng câu trắc nghiệm (max 60 câu), Số câu tự luận (max 5 câu), Hình thức thi.</li>
            <li>Nhấn nút <b>🚀 Tạo đề kiểm tra qua RAG & AI</b> ➔ Chuyển sang tab <b>Làm bài kiểm tra</b> để làm bài, nộp bài và xem giải thích chi tiết từng câu.</li>
        </ol>

        <h3>4.4. Xem Ngân hàng đề & Lịch sử làm bài (📜 Lịch sử)</h3>
        <ul>
            <li>Lưu trữ lại toàn bộ các đề thi đã tạo và theo dõi tiến trình điểm số giúp bạn đánh giá mức độ tiến bộ qua từng lần làm bài.</li>
        </ul>

        <hr>

        <h2>5. Lưu ý quan trọng cho người dùng mới</h2>
        <div class="warning-box">
            <b>⚠️ Mẹo xử lý khi tạo đề:</b><br>
            • Nếu bạn dùng file tổng hợp chứa câu hỏi của nhiều môn học cùng lúc, hãy chọn mục <b>"Tất cả môn / Tổng hợp"</b> ở ô chọn môn học đầu tiên để AI đọc trọn vẹn file.<br>
            • Đảm bảo máy tính của bạn giữ kết nối mạng Internet trong quá trình tạo đề hoặc hỏi đáp với AI.
        </div>

        <p style="text-align:center; color:#64748b; margin-top:24px; font-weight:bold;">
        🎓 Chúc bạn có trải nghiệm ôn luyện tuyệt vời và đạt kết quả cao cùng Trợ lý ảo RAG!
        </p>

        </body>
        </html>
        """
        )

        layout.addWidget(help_text)

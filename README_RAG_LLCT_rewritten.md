# RAG LLCT

Phần mềm trợ lý học tập tích hợp RAG (Retrieval-Augmented Generation), hỗ trợ tra cứu và luyện tập các môn Lý luận chính trị cho sinh viên Phân hiệu Trường Đại học Thủy Lợi.

> **Phạm vi khảo sát:** `D:\RAG_LLCT\RAG_LLCT`. Tài liệu này mô tả trạng thái mã nguồn đã được khảo sát, không khẳng định toàn bộ ứng dụng đã hoàn thiện. Các nhận định về lỗi và chức năng chưa xác minh được ghi rõ bên dưới.

---

## 1. Giới thiệu

RAG LLCT là ứng dụng desktop viết bằng Python và PySide6, hướng đến việc hỗ trợ sinh viên tra cứu tài liệu và ôn tập các môn Lý luận chính trị.

Các chức năng được thiết kế gồm:

- Hỏi đáp dựa trên tài liệu môn học thông qua RAG và mô hình ngôn ngữ lớn (LLM).
- Quản lý danh mục sáu môn Lý luận chính trị và danh sách tài liệu.
- Tạo đề trắc nghiệm/tự luận, làm bài và xem kết quả.
- Cấu hình API key để sử dụng Google Gemini hoặc Groq.

Giao diện chính có năm khu vực: **Hỏi đáp**, **Môn học**, **Luyện tập**, **Cài đặt** và **Hướng dẫn**.

## 2. Mục tiêu

1. Đọc và truy xuất các đoạn nội dung từ tài liệu học tập, hiện tập trung vào PDF.
2. Tạo câu trả lời dựa trên ngữ cảnh truy xuất, có thể kèm thông tin nguồn như tên tệp và trang.
3. Hỗ trợ tạo đề luyện tập từ ngữ cảnh RAG, làm bài và chấm câu hỏi trắc nghiệm trên máy tính.

Một số bước quan trọng — đặc biệt là đồng bộ việc thêm tài liệu với quá trình embedding/ChromaDB và lưu API key từ giao diện — chưa được nối hoàn chỉnh theo kết quả khảo sát. Xem thêm `BUG_REPORT.md` nếu tệp này có trong workspace.

## 3. Trạng thái chức năng

Bảng dưới đây phân biệt giữa việc có mã nguồn và việc đã được kiểm chứng khi chạy. Có giao diện hoặc nút bấm không đồng nghĩa chức năng đã hoạt động đầy đủ.

| Hạng mục | Trạng thái theo đợt khảo sát |
| --- | --- |
| Khởi tạo GUI (`MainWindow`) và điều hướng năm trang | Có mã nguồn; chưa xác minh toàn bộ luồng GUI từ đầu đến cuối |
| Import package `app` | Đã xác minh import `app.main` thành công trong môi trường Python 3.10 của `rag_llct` |
| Chạy `python app/main.py` | Đã xác minh thất bại với `ModuleNotFoundError: No module named 'app'` |
| Hỏi đáp RAG, bộ lọc và cache | Có mã nguồn; pipeline truy xuất có rủi ro không tìm được ngữ cảnh do metadata trong ChromaDB chưa khớp bộ lọc |
| Quản lý môn học và metadata tài liệu | Có mã nguồn; thêm tài liệu chưa tự gọi quy trình ingest/embedding |
| Tạo đề, làm bài, chấm trắc nghiệm và lưu lịch sử | Có mã nguồn; một phần được kiểm thử bằng mock, một số bài test thất bại hoặc không kết thúc |
| Lưu API key từ giao diện | Có form; `SettingsManager` không có phương thức `save_api_key` theo kiểm tra đã ghi nhận |
| Đọc API key từ cấu hình hoặc biến môi trường | Có mã nguồn |
| Tích hợp Gemini/Groq | Có mã nguồn; chưa xác minh bằng lời gọi API thật trong đợt khảo sát |
| Trang hướng dẫn (`HelpPage`) | Có mã nguồn |
| Đóng gói EXE | Có khai báo PyInstaller trong `requirements.txt`; chưa tìm thấy file `.spec`, thư mục `dist/` hoặc EXE để xác minh |

## 4. Công nghệ

Theo `requirements.txt` và mã nguồn đã khảo sát:

- **Python 3.10** — môi trường `rag_llct` được ghi nhận dùng Python 3.10.22.
- **PySide6** — xây dựng giao diện desktop.
- **ChromaDB** — lưu trữ vector, đường dẫn dự kiến `data/chroma`, collection `llct_documents`.
- **sentence-transformers** — mô hình embedding `paraphrase-multilingual-MiniLM-L12-v2`.
- **PyMuPDF (`fitz`)** — đọc nội dung PDF.
- **google-genai** — tích hợp Google Gemini.
- **groq** — tích hợp Groq Chat Completions.
- **pytest** — kiểm thử.
- **PyInstaller** — công cụ dự kiến dùng để đóng gói ứng dụng.

Trong đợt khảo sát, chưa tìm thấy dependency hoặc phần triển khai loader DOCX chuyên dụng (ví dụ `python-docx`). Không nên xem việc giao diện cho chọn DOCX/TXT là bằng chứng rằng các định dạng này đã được xử lý đầy đủ trong RAG.

## 5. Kiến trúc tổng thể

```text
[PySide6 UI]
  chat_page / quiz_* / settings / help / main_window
                 |
                 v
[Services]
  ChatService, DocumentService, QuizService,
  GeminiService, SettingsManager, QuestionBankService, TokenBudget
                 |
                 v
[RAG]
  DocumentLoader -> TextChunker -> EmbeddingService -> VectorStore
  Retriever -> PromptManager -> RAGGenerator -> GeminiService
                 |
                 v
[Storage]
  data/chroma, data/documents, data/settings.json,
  data/question_bank.json, data/exam_history.json, chat_cache.json
```

Theo mã nguồn được khảo sát, `app/main.py` tạo `Retriever` và `GeminiService` rồi truyền chúng vào `MainWindow`. Tuy nhiên, trang chat tự khởi tạo các instance `Retriever`, `GeminiService` và `RAGGenerator` riêng thay vì dùng chung hoàn toàn các instance được tạo ở `main.py`.

## 6. Cấu trúc thư mục

Cấu trúc dưới đây là cấu trúc được ghi nhận trong đợt khảo sát; có thể thay đổi theo phiên bản hiện tại của dự án.

```text
D:\RAG_LLCT\RAG_LLCT\
├── app\
│   ├── main.py
│   ├── models\          # SUBJECTS, Document
│   ├── rag\             # loader, chunker, embedding, vector store, ingest, retriever, generator, prompt
│   ├── services\        # tài liệu, chat, quiz, Gemini/Groq, settings, ngân hàng câu hỏi
│   └── ui\              # cửa sổ chính và các trang giao diện
├── assets\icons\        # logo.png, logo1.png
├── data\
│   ├── documents\       # PDF và documents_meta.json
│   ├── chroma\          # dữ liệu ChromaDB
│   └── settings.json    # có thể chứa API key; cần bảo vệ
├── tests\
├── requirements.txt
├── README.md
└── BUG_REPORT.md
```

Các ghi nhận bổ sung:

- Không thấy `app/__init__.py` ở thời điểm khảo sát; các thư mục `app/models`, `app/rag`, `app/services` và `app/ui` có `__init__.py` rỗng.
- Thư mục `build/` tồn tại nhưng được ghi nhận là trống; chưa thấy `dist/`.
- `.gitignore` có loại trừ `*.spec`, `build/`, `dist/` và `data/chroma/`. Cần kiểm tra lại `.gitignore` trước khi đưa dự án lên Git, đặc biệt với file cấu hình chứa API key.

## 7. Luồng xử lý RAG

Theo mã nguồn và dữ liệu được ghi nhận trong đợt khảo sát:

1. **Ingest độc lập** — `app/rag/ingest.py` quét PDF trong `data/documents`, chia văn bản thành các đoạn khoảng 800 ký tự với overlap 150 ký tự, tạo embedding rồi `upsert` vào ChromaDB.
2. **Metadata khi ingest** — quy trình trên chưa gắn `subject_id` hoặc `document_type` vào metadata của từng chunk. Script ingest cũng chưa được gọi tự động từ nút “Thêm tài liệu” trên giao diện.
3. **Thêm tài liệu từ UI** — `DocumentService.add_document` ghi metadata vào JSON và giữ `file_path` gốc; loại tài liệu mặc định được ghi nhận là `giao_trinh`.
4. **Truy vấn** — `Retriever.retrieve` embedding câu hỏi, truy vấn ChromaDB với số kết quả dự kiến theo `top_k * 3`, sau đó lọc theo `subject_id`, `document_type` và `allowed_sources` ở phía Python.
5. **Sinh câu trả lời** — `RAGGenerator.answer` trả thông báo nếu không có chunk phù hợp; nếu có ngữ cảnh, hệ thống dựng prompt qua `PromptManager.build_prompt` rồi gọi `GeminiService.generate`.
6. **Chat** — `RAGWorker` chạy tác vụ trong `QThread`; kết quả, bao gồm thông tin lỗi, có thể được ghi vào `chat_cache.json`.

### Ghi nhận về dữ liệu ChromaDB

Trong đợt khảo sát chỉ đọc dữ liệu, ghi nhận có **548 embeddings**. Metadata quan sát được gồm `source`, `page`, `chunk_id` và `chunk_index`; chưa thấy `subject_id` hoặc `document_type`.

Nếu bộ truy xuất lọc nghiêm ngặt theo `subject_id` hoặc `document_type`, các chunk hiện có có thể bị loại hết và khiến truy vấn trả về danh sách rỗng. Đây là vấn đề cần kiểm chứng lại sau khi dữ liệu được ingest theo metadata thống nhất.

## 8. Luồng sử dụng LLM và API key

Theo mã nguồn được khảo sát:

1. API key được đọc từ `data/settings.json` (khóa `gemini_api_key`) hoặc biến môi trường `GEMINI_API_KEY`.
2. Key bắt đầu bằng tiền tố `gsk_` được nhận diện là Groq; các key còn lại được xử lý theo nhánh Gemini.
3. Model Groq được ghi nhận là `openai/gpt-oss-120b`. Nhánh Gemini thử `gemini-2.5-flash`, sau đó có tên model dự phòng `gemini-3.8-flash` trong mã nguồn. Cần xác minh lại tính khả dụng của model với nhà cung cấp trước khi sử dụng.
4. Mã nguồn có phân loại một số lỗi xác thực, timeout và phản hồi. Luồng tạo đề có thể chuyển sang ngân hàng câu hỏi khi AI gặp lỗi, ngoại trừ trường hợp `AIAuthenticationError` được ném lại.
5. Giao diện Cài đặt gọi `save_api_key`, nhưng phương thức này không tồn tại trên `SettingsManager` theo kết quả kiểm tra `hasattr` đã ghi nhận.

**Lưu ý bảo mật:** API key có thể được lưu dưới dạng văn bản thuần trong tệp cấu hình cục bộ. Không đưa key thật vào README, mã nguồn, issue công khai hoặc cuộc trò chuyện. Nếu key đã bị công khai, hãy thu hồi và tạo key mới tại nhà cung cấp.

Tệp `data/settings.json` và `chat_cache.json` cần được kiểm tra trong `.gitignore` trước khi commit. Trong trạng thái được khảo sát, README ghi nhận `data/settings.json` chưa được loại trừ rõ ràng khỏi Git.

## 9. Cài đặt môi trường

Các lệnh dưới đây là hướng dẫn đề xuất, không có nghĩa môi trường mới đã được tạo trong đợt khảo sát.

### Sử dụng môi trường Conda hiện có

```bat
conda activate rag_llct
python --version
cd /d D:\RAG_LLCT\RAG_LLCT
```

Môi trường đã được ghi nhận dùng Python 3.10.22. Lệnh `python -m pip check` trả về `No broken requirements found` trong đợt kiểm tra được mô tả.

### Tạo môi trường mới (chỉ thực hiện nếu chủ động muốn cài đặt lại)

```bat
conda create -n rag_llct python=3.10 -y
conda activate rag_llct
cd /d D:\RAG_LLCT\RAG_LLCT
pip install -r requirements.txt
```

Lệnh tạo môi trường mới sẽ thất bại nếu môi trường `rag_llct` đã tồn tại mà không xử lý tên môi trường trước. Không cần chạy lại bước này nếu môi trường hiện tại đã dùng được.

Lần đầu sử dụng embedding, `sentence-transformers` có thể cần tải trọng số mô hình từ cache Hugging Face; quá trình này có thể yêu cầu kết nối Internet.

## 10. Cấu hình API key

Có thể thiết lập biến môi trường trong PowerShell cho phiên terminal hiện tại:

```powershell
$env:GEMINI_API_KEY="YOUR_API_KEY"
```

Thay `YOUR_API_KEY` bằng key của bạn và không chia sẻ giá trị đó. Nếu dùng Groq, hãy kiểm tra quy tắc đọc key thực tế của phiên bản mã nguồn đang chạy.

Theo khảo sát, giao diện Cài đặt chưa lưu được key vì thiếu `SettingsManager.save_api_key`. Việc tự tạo hoặc chỉnh `data/settings.json` chỉ nên thực hiện khi hiểu rõ định dạng cấu hình và đã sao lưu tệp hiện tại.

## 11. Khởi chạy ứng dụng

Thực hiện từ thư mục gốc chứa package `app`:

```bat
conda activate rag_llct
cd /d D:\RAG_LLCT\RAG_LLCT
python -m app.main
```

Cách import đã được ghi nhận thành công trong môi trường khảo sát:

```bat
python -c "from app.main import main; print('OK')"
```

Lệnh dưới đây đã được ghi nhận thất bại trong đợt khảo sát:

```bat
python app/main.py
```

Nguyên nhân được xác định trong tình huống này là cách chạy file trực tiếp khiến đường dẫn import không còn phù hợp với câu lệnh `from app...`, dẫn đến:

```text
ModuleNotFoundError: No module named 'app'
```

Vì vậy, nên chạy từ thư mục gốc bằng `python -m app.main`. Lệnh này là hướng dẫn khởi chạy đề xuất; việc mở GUI đầy đủ vẫn cần được kiểm chứng trên máy của bạn. Lần đầu khởi tạo `Retriever`, ứng dụng có thể mất thời gian tải mô hình embedding.

## 12. Hướng dẫn sử dụng chức năng

1. **Cài đặt:** mở trang Cài đặt và nhập API key Gemini hoặc Groq. Lưu ý chức năng lưu key đang có vấn đề theo kết quả khảo sát.
2. **Môn học:** chọn môn, thêm PDF/DOCX/TXT, mở tệp bằng ứng dụng hệ thống hoặc xóa metadata tài liệu. Việc thêm tệp chưa tự động cập nhật vector database.
3. **Hỏi đáp:** chọn môn và loại tài liệu rồi gửi câu hỏi. Ứng dụng có cache hội thoại (`chat_cache.json`) và nút xóa cache. Nếu truy xuất không tìm được chunk phù hợp, giao diện có thể thông báo không tìm thấy nội dung.
4. **Luyện tập:** chọn môn, tài liệu, chương, hình thức và số câu; tạo đề, làm bài, nộp bài và xem kết quả. Khi worker đang chạy, không nên gửi yêu cầu tạo đề lặp lại. Chức năng chấm tự luận cần được kiểm chứng riêng.
5. **Hướng dẫn:** xem nội dung hướng dẫn được tích hợp trong ứng dụng.

### Chạy ingest thủ công

Chỉ chạy khi bạn chủ động muốn cập nhật ChromaDB và đã sao lưu dữ liệu cần thiết:

```bat
python -m app.rag.ingest
```

Theo khảo sát, script này hiện tập trung vào PDF và chưa gắn metadata môn học/loại tài liệu vào chunk. Do đó, chỉ chạy ingest đơn lẻ có thể chưa giải quyết được vấn đề bộ lọc truy xuất.

## 13. Chạy kiểm thử

Ví dụ chạy bộ test lọc tài liệu:

```bat
conda activate rag_llct
cd /d D:\RAG_LLCT\RAG_LLCT
python -m pytest tests/test_document_filter.py -v
```

Kết quả được ghi nhận trong đợt khảo sát:

- `tests/test_document_filter.py`: **20 passed**.
- Một phần các test trong `test_quiz_json.py` và `test_quiz_service_robust.py` pass, một phần fail do kỳ vọng về retry/raise chưa khớp với hành vi `QuizService` hiện tại.
- Một phiên pytest không hoàn tất vì bị giữ tại luồng có `QMessageBox` trong test GUI.
- `tests/test_rag_retrieval.py` chưa được chạy trong đợt đó vì khởi tạo `Retriever()` thật có thể tải model và truy cập ChromaDB.
- `tests/test_rag_generation_manual.py` là script kiểm tra thủ công, cần `GEMINI_API_KEY`.

Đây là kết quả của đợt khảo sát trước, không phải kết quả test mới nhất. Hãy chạy lại test sau mỗi thay đổi để xác nhận trạng thái hiện tại.

## 14. Đóng gói EXE

Trong `requirements.txt` có khai báo `pyinstaller==6.22.3`. Tuy nhiên, tại thời điểm khảo sát:

- Chưa tìm thấy file cấu hình `.spec`.
- Chưa có thư mục `dist/` được ghi nhận.
- Chưa có EXE để kiểm tra.

Vì vậy, **chưa xác minh được việc build hoặc chạy bản EXE**. Cần xây dựng và kiểm thử quy trình đóng gói riêng, bao gồm tài nguyên giao diện, dữ liệu cần thiết, mô hình embedding và cấu hình API key.

## 15. Các lỗi và hạn chế đã ghi nhận

| Hiện tượng | Nhận định / hướng xử lý đề xuất (chưa sửa trong đợt khảo sát) |
| --- | --- |
| `ModuleNotFoundError: No module named 'app'` khi chạy `python app/main.py` | Chạy từ thư mục gốc dự án bằng `python -m app.main`. |
| Không lưu được API key từ giao diện | Kiểm tra và bổ sung phương thức lưu cấu hình phù hợp trong `SettingsManager`. |
| Chat không tìm thấy tài liệu vừa thêm | Kết nối quy trình thêm tài liệu với ingest/embedding; thống nhất metadata của chunk với bộ lọc truy xuất. |
| Không mở được PDF | Kiểm tra lại `file_path` trong `documents_meta.json`. Đường dẫn được ghi nhận có thể trỏ đến `D:/RAG_LLCT/data/documents/...`, trong khi dữ liệu thực tế nằm dưới `D:\RAG_LLCT\RAG_LLCT\data\documents\`. |
| Chọn được DOCX/TXT nhưng RAG không đọc nội dung | Kiểm tra và triển khai loader cho các định dạng này hoặc giới hạn lựa chọn giao diện vào định dạng đã hỗ trợ. |
| Đề tạo ra ít câu hoặc chuyển sang câu hỏi dự phòng | Kiểm tra lỗi gọi AI, cơ chế fallback và số câu hiện có trong ngân hàng câu hỏi. |

## 16. Hạn chế hiện tại theo đợt khảo sát

- README cũ có vấn đề mã hóa ký tự; bản này được viết lại từ nội dung khảo sát hiện có.
- Chưa thấy `app/__init__.py`.
- Thêm tài liệu chưa cập nhật vector database; xóa metadata tài liệu chưa đồng nghĩa xóa embedding tương ứng.
- Chunk trong ChromaDB chưa có `subject_id` và `document_type` theo dữ liệu quan sát.
- API key có thể được lưu dạng văn bản thuần; cần rà soát `.gitignore` cho `data/settings.json` và `chat_cache.json`.
- Trang chat khởi tạo `RAGGenerator` riêng; chưa xác minh cơ chế tải lại key sau khi thay đổi cài đặt.
- Bộ lọc loại tài liệu trên trang chat được ghi nhận chưa cập nhật badge do thiếu kết nối sự kiện `currentIndexChanged`.
- `ingest.py` và `DocumentLoader` được ghi nhận chỉ xử lý PDF, trong khi giao diện cho phép chọn DOCX/TXT.
- Chưa xác minh việc chấm điểm tự luận bằng LLM. Theo khảo sát, kết quả tổng có thể không phản ánh đúng phần tự luận khi không có câu trắc nghiệm.
- Một số test quiz không còn khớp hành vi code; test GUI có nguy cơ treo ở `QMessageBox`.
- Chưa có quy trình đóng gói EXE được xác minh hoàn chỉnh.

Các mục trên phản ánh kết quả khảo sát đã cung cấp, không phải kết luận rằng mọi lỗi vẫn còn tồn tại trong phiên bản mới nhất. Cần xác minh lại sau khi mã nguồn thay đổi.

## 17. Lộ trình đề xuất

Nên xử lý theo thứ tự ưu tiên sau:

1. **Khởi chạy ổn định:** chuẩn hóa cách chạy module và xác minh GUI khởi động từ thư mục gốc.
2. **Cấu hình API key:** hoàn thiện luồng lưu/đọc key và bảo vệ tệp cấu hình.
3. **Pipeline tài liệu:** thống nhất đường dẫn file, ingest/embedding, metadata môn học và loại tài liệu; đồng bộ thao tác thêm/xóa với ChromaDB.
4. **Truy xuất RAG:** kiểm thử bộ lọc, nguồn được phép và khả năng tìm thấy chunk phù hợp.
5. **Quiz và kiểm thử:** làm cho hành vi tạo đề khớp với test; xử lý test GUI để tránh treo; kiểm chứng cách chấm tự luận.
6. **Trải nghiệm sử dụng:** cập nhật danh sách tài liệu sau khi thêm file, sửa trạng thái badge và kiểm tra điều hướng giữa các màn hình.
7. **Đóng gói:** tạo cấu hình PyInstaller, build EXE và kiểm thử trên môi trường sạch.

Mỗi thay đổi cần được thực hiện và kiểm chứng riêng. Tài liệu này chỉ ghi lại kết quả khảo sát và đề xuất hướng xử lý; không có nghĩa mã nguồn đã được sửa.

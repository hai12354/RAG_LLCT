# app/services/gemini_service.py
import os
import logging

logger = logging.getLogger(__name__)

try:
    # pyrefly: ignore [missing-import]
    from groq import Groq

    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

try:
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


# Domain-specific exceptions for AI Service
class AIServiceError(Exception):
    """Lỗi chung từ dịch vụ AI."""

    pass


class AIAuthenticationError(AIServiceError, ValueError):
    """Lỗi API key chưa được cấu hình hoặc không hợp lệ."""

    pass


class AITimeoutError(AIServiceError, TimeoutError):
    """Lỗi timeout hoặc kết nối mạng khi gọi AI."""

    pass


class AIResponseError(AIServiceError, RuntimeError):
    """Lỗi từ phản hồi AI hoặc tất cả các model đều thất bại."""

    pass


class GeminiService:
    def __init__(self, api_key: str = None, model_name: str = None):
        """
        Service tích hợp linh hoạt giữa Google Gemini và Groq:
        - Tự động nhận diện Provider (Groq nếu key bắt đầu bằng 'gsk_', ngược lại là Gemini).
        - Hỗ trợ cơ chế tự động thử lần lượt các model dự phòng (Auto-fallback) nếu model chính gặp lỗi quá tải hoặc tạm thời.
        """
        self.api_key = (
            api_key
            or os.environ.get("GEMINI_API_KEY", "")
            or os.environ.get("GROQ_API_KEY", "")
        )
        self.api_key = self.api_key.strip() if self.api_key else ""

        self.provider = self._detect_provider(self.api_key)

        # Danh sách các model ưu tiên thử nghiệm (Auto-fallback list)
        if self.provider == "groq":
            self.fallback_models = [
                "openai/gpt-oss-20b",
            ]
        else:
            self.fallback_models = [
                "gemini-2.5-flash",
                "gemini-3.8-flash",
            ]

        # Nếu người dùng chỉ định rõ model, đưa model đó lên đầu danh sách ưu tiên
        if model_name and model_name.strip():
            custom_model = model_name.strip()
            if custom_model in self.fallback_models:
                self.fallback_models.remove(custom_model)
            self.fallback_models.insert(0, custom_model)

        self._client = None
        self._init_client()

    def _detect_provider(self, key: str) -> str:
        """Tự động nhận diện provider dựa trên tiền tố của API key."""
        if key.startswith("gsk_"):
            return "groq"
        return "gemini"

    def _init_client(self):
        if not self.api_key:
            return
        try:
            if self.provider == "groq":
                if not GROQ_AVAILABLE:
                    raise ImportError(
                        "Thư viện 'groq' chưa được cài đặt. Vui lòng chạy: pip install groq"
                    )
                self._client = Groq(api_key=self.api_key)
            else:
                if not GEMINI_AVAILABLE:
                    raise ImportError(
                        "Thư viện 'google-genai' chưa được cài đặt. Vui lòng chạy: pip install google-genai"
                    )
                self._client = genai.Client(api_key=self.api_key)
        except Exception as e:
            logger.exception("Failed to initialize AI client")
            self._client = None

    def generate(self, prompt: str, response_mime_type: str = None) -> str:
        """
        Gửi prompt đến LLM với cơ chế Auto-Fallback và xử lý lỗi chuẩn xác.
        Tự động fallback gỡ bỏ response_format nếu Groq gặp lỗi json_validate_failed.
        """
        if not self.api_key:
            raise AIAuthenticationError(
                "API key chưa được cấu hình. Vui lòng nhập API key trong mục Cài đặt."
            )

        if not self._client:
            self._init_client()
            if not self._client:
                raise AIAuthenticationError(
                    f"Khởi tạo client cho provider '{self.provider}' thất bại. Vui lòng kiểm tra lại kết nối hoặc API key."
                )

        if not prompt or not prompt.strip():
            return ""

        last_exception = None

        # Vòng lặp thử lần lượt các model trong danh sách fallback
        for current_model in self.fallback_models:
            try:
                logger.info(
                    f"[AI] Provider: {self.provider.upper()} | Model: {current_model} | JSONMode: {response_mime_type == 'application/json'}"
                )

                if self.provider == "groq":
                    kwargs = {
                        "messages": [{"role": "user", "content": prompt}],
                        "model": current_model,
                    }
                    if response_mime_type == "application/json":
                        kwargs["response_format"] = {"type": "json_object"}

                    try:
                        chat_completion = self._client.chat.completions.create(**kwargs)
                    except Exception as groq_err:
                        err_str = str(groq_err).lower()
                        # Bắt lỗi validate JSON của Groq để tự động gỡ response_format và thử lại
                        if (
                            "json_validate_failed" in err_str
                            or "failed to generate json" in err_str
                        ) and "response_format" in kwargs:
                            logger.warning(
                                f"[GROQ] Model {current_model} bị lỗi json_validate_failed. Đang thử lại không dùng response_format..."
                            )
                            del kwargs["response_format"]
                            chat_completion = self._client.chat.completions.create(
                                **kwargs
                            )
                        else:
                            raise groq_err

                    if chat_completion and chat_completion.choices:
                        content = chat_completion.choices[0].message.content
                        if content:
                            res_str = content.strip()
                            logger.info(f"[AI] Response length: {len(res_str)}")
                            return res_str
                else:  # Gemini
                    if response_mime_type == "application/json":
                        config = types.GenerateContentConfig(
                            response_mime_type="application/json"
                        )
                        response = self._client.models.generate_content(
                            model=current_model,
                            contents=prompt,
                            config=config,
                        )
                    else:
                        response = self._client.models.generate_content(
                            model=current_model,
                            contents=prompt,
                        )
                    if response and response.text:
                        res_str = response.text.strip()
                        logger.info(f"[AI] Response length: {len(res_str)}")
                        return res_str

            except Exception as e:
                last_exception = e
                logger.exception(f"[AI ERROR] Model {current_model} failed")
                err_str = str(e).lower()

                # CHỈ báo lỗi API key khi gặp từ khóa xác thực sai key thực sự
                key_error_keywords = [
                    "api_key_invalid",
                    "invalid api key",
                    "api key not valid",
                    "account_disabled",
                    "key expired",
                    "unauthenticated",
                    "api_key_not_found",
                    "401",
                    "authentication",
                ]
                if any(kw in err_str for kw in key_error_keywords):
                    raise AIAuthenticationError(
                        "API key không hợp lệ hoặc đã bị vô hiệu hóa."
                    ) from e

                # Kiểm tra lỗi timeout / network
                timeout_keywords = [
                    "timeout",
                    "timed out",
                    "connecterror",
                    "connection error",
                    "network",
                ]
                if any(kw in err_str for kw in timeout_keywords):
                    pass

                continue

        # Nếu đã thử hết các model mà vẫn thất bại hoàn toàn
        if last_exception:
            err_str = str(last_exception).lower()
            if any(
                kw in err_str
                for kw in [
                    "timeout",
                    "timed out",
                    "connecterror",
                    "connection error",
                    "network",
                ]
            ):
                raise AITimeoutError(
                    "Không thể kết nối đến dịch vụ AI. Vui lòng kiểm tra lại kết nối mạng và thử lại."
                ) from last_exception

            raise AIResponseError(
                f"Tất cả các model của {self.provider.upper()} đều phản hồi thất bại. Chi tiết lỗi: {last_exception}"
            ) from last_exception

        return "Không nhận được phản hồi từ LLM."

    def set_api_key(self, api_key: str):
        """Cập nhật lại API key, đồng thời đồng bộ lại provider, fallback models và khởi tạo lại client."""
        self.api_key = (api_key or "").strip()
        self.provider = self._detect_provider(self.api_key)

        if self.provider == "groq":
            self.fallback_models = [
                "openai/gpt-oss-20b",
            ]
        else:
            self.fallback_models = [
                "gemini-2.5-flash",
                "gemini-3.8-flash",
            ]

        self._client = None
        self._init_client()

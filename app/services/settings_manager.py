import json
import os
from pathlib import Path
import sys

# Xác định thư mục gốc chính xác cho cả file .py lẫn file .exe đóng gói
if getattr(sys, "frozen", False):
    # Khi đã đóng gói thành .exe -> Lấy thư mục chứa file .exe thực tế
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    # Khi chạy code .py trực tiếp trong môi trường Dev
    BASE_DIR = Path(__file__).resolve().parent.parent.parent

CONFIG_PATH = str(BASE_DIR / "data" / "settings.json")


class SettingsManager:

    def __init__(self, config_path: str = CONFIG_PATH):
        self.config_path = config_path

    def _read_all(self) -> dict:
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError, TypeError):
            return {}

    def _write_all(self, data: dict) -> None:
        folder = os.path.dirname(self.config_path) or "."
        os.makedirs(folder, exist_ok=True)
        tmp = self.config_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.config_path)  # ghi nguyên tử, tránh hỏng file

    def save_api_key(self, key: str) -> bool:
        """Lưu API key vào settings.json. Key rỗng sẽ xóa key đã lưu."""
        key = (key or "").strip()
        data = self._read_all()
        if key:
            data["gemini_api_key"] = key
        else:
            data.pop("gemini_api_key", None)
        self._write_all(data)
        return True

    def get_api_key(self) -> str:
        # 1. Ưu tiên key đã lưu trong settings.json
        key = self._read_all().get("gemini_api_key", "")
        if isinstance(key, str) and key.strip():
            return key.strip()

        # 2. Fallback sang biến môi trường
        return os.environ.get("GEMINI_API_KEY", "").strip()

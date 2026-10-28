import os
import sys
from pathlib import Path


def get_base_dir() -> Path:
    """
    Lấy đường dẫn thư mục gốc (BASE_DIR) của ứng dụng.
    - Khi chạy dưới dạng file .exe (PyInstaller): Lấy thư mục chứa file .exe
    - Khi chạy code Python trực tiếp: Lấy thư mục gốc của dự án
    """
    if getattr(sys, "frozen", False):
        # Đang chạy từ file .exe đã build
        return Path(sys.executable).parent
    else:
        # Đang chạy code .py
        # Giả sử file này nằm ở: app/utils/path_helper.py (lùi 2 cấp lên thư mục gốc)
        return Path(__file__).resolve().parent.parent.parent


BASE_DIR = get_base_dir()

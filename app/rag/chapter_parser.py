# app/rag/chapter_parser.py
import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Pattern cải tiến:
# 1. Bắt chính xác Số La Mã (chỉ gồm I, V, X, L, C, D, M ghép hợp lệ làm từ riêng)
# 2. Hoặc Số Ả Rập (1, 2, 3...)
# 3. Hoặc Từ chỉ thứ tự tiếng Việt đầy đủ ("THỨ NHẤT", "THỨ HAI",...)
ROMAN_OR_NUM = r"(?:THỨ\s+(?:NHẤT|HAI|BA|TƯ|NĂM|SÁU|BẢY|TÁM|CHÍN|MƯỜI)|M|[MD]{1,4}|[CD]{1,4}|[XV]{1,4}|I[XVX]|V?I{0,3}|\d+)"

CHAPTER_SEARCH_PATTERN = re.compile(
    rf"^\s*\b(CHƯƠNG|Chương|BÀI|Bài|CHUYÊN ĐỀ|Chuyên đề|PHẦN|Phần)\s+({ROMAN_OR_NUM})\b[\:\.\-\–—\s]*(.*)$",
    re.IGNORECASE,
)

BREAK_KEYWORDS_PATTERN = re.compile(
    r"^(CHƯƠNG|Chương|BÀI|Bài|MỤC|Mục|CHUYÊN ĐỀ|Chuyên đề|PHẦN|Phần|\d+\.|\§|Trang\s+\d+|\d+\s*$)",
    re.IGNORECASE,
)


def parse_chapters_from_pages(
    pages_data: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    current_chapter = ""

    for page_info in pages_data:
        text = page_info.get("text", "")
        if not text:
            if "metadata" not in page_info:
                page_info["metadata"] = {}
            page_info["metadata"]["chapter"] = current_chapter
            continue

        clean_text = text.replace("\xa0", " ").replace("\t", " ")
        lines = [line.strip() for line in clean_text.splitlines() if line.strip()]

        # Bỏ qua nếu là trang Mục lục
        is_toc_page = any("MỤC LỤC" in line.upper() for line in lines[:5])
        toc_line_count = sum(1 for line in lines if re.search(r"\.\.\.\.\s*\d+$", line))

        if is_toc_page or toc_line_count >= 3:
            if "metadata" not in page_info:
                page_info["metadata"] = {}
            page_info["metadata"]["chapter"] = current_chapter
            continue

        for i, line in enumerate(lines):
            match = CHAPTER_SEARCH_PATTERN.search(line)
            if match:
                prefix = match.group(1).title()  # Chương / Bài / Phần
                num = match.group(2).upper().strip()  # 1, I, II, THỨ NHẤT
                title = match.group(3).strip()

                # Dọn dẹp ký tự phân cách ở đầu tiêu đề
                title = re.sub(r"^[\:\.\-\–—\s]+", "", title).strip()

                # Nối dòng nếu tiêu đề dài bị rớt xuống dòng dưới
                if len(title) < 3:
                    title_parts = []
                    j = i + 1
                    while j < len(lines):
                        next_line = lines[j]
                        if BREAK_KEYWORDS_PATTERN.search(next_line):
                            break
                        if len(title_parts) >= 2:
                            break
                        title_parts.append(next_line)
                        j += 1
                    if title_parts:
                        title = " ".join(title_parts).strip()

                # Giới hạn độ dài tiêu đề chương (tránh ăn lan vào câu văn nội dung)
                if len(title) > 120:
                    title = title[:120].rsplit(" ", 1)[0] + "..."

                chapter_str = f"{prefix} {num}".strip()
                if title:
                    chapter_str += f": {title}"

                if len(chapter_str) > 3:
                    current_chapter = chapter_str
                    page_num = page_info.get("metadata", {}).get("page", "?")
                    logger.info(
                        f"[CHAPTER PARSER] Trang {page_num}: Phát hiện '{current_chapter}'"
                    )
                    break

        if "metadata" not in page_info:
            page_info["metadata"] = {}

        page_info["metadata"]["chapter"] = current_chapter

    return pages_data

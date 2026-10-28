# app/services/token_budget.py
import math
import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

DEFAULT_TOKEN_BUDGET = 8000

# Estimated average output tokens per question type
ESTIMATED_TOKENS_PER_MC = 120
ESTIMATED_TOKENS_PER_ESSAY = 250


class TokenBudget:
    def __init__(self, budget: int = DEFAULT_TOKEN_BUDGET):
        self.budget = budget

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        Ước tính số token của chuỗi văn bản theo heuristic:
        estimated_tokens ≈ ceil(len(text) / 4) * 1.15 (safety margin 15%)
        """
        if not text:
            return 0
        raw_estimate = math.ceil(len(text) / 4.0)
        return math.ceil(raw_estimate * 1.15)

    def estimate_request(
        self,
        prompt_template: str,
        context_str: str,
        mc_count: int,
        essay_count: int = 0,
    ) -> Dict[str, int]:
        """
        Tính toán ước lượng Input, Output và Total Tokens.
        """
        input_text = f"{prompt_template}\n{context_str}"
        input_tokens = self.estimate_tokens(input_text)
        output_tokens = (mc_count * ESTIMATED_TOKENS_PER_MC) + (
            essay_count * ESTIMATED_TOKENS_PER_ESSAY
        )
        total_tokens = input_tokens + output_tokens

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        }

    def optimize_request_parameters(
        self,
        prompt_template: str,
        context_parts: List[str],
        target_mc: int,
        target_essay: int = 0,
        min_mc: int = 5,
    ) -> Tuple[List[str], int, int, Dict[str, int]]:
        """
        Tự động điều chỉnh RAG context chunks và số câu AI target nếu vượt quá token budget.
        - Giảm số câu AI từ target_mc xuống dần min_mc (ví dụ 10 -> 9 -> 8 -> 7 -> 5).
        - Giảm số chunk context nếu context quá dài.
        """
        current_chunks = list(context_parts)
        current_mc = target_mc
        current_essay = target_essay

        while True:
            context_str = "\n\n".join(current_chunks)
            estimates = self.estimate_request(
                prompt_template, context_str, current_mc, current_essay
            )

            if estimates["total_tokens"] <= self.budget:
                return current_chunks, current_mc, current_essay, estimates

            # Nếu vượt budget: thử giảm MC count nếu > min_mc
            if current_mc > min_mc:
                current_mc -= 1
                continue

            # Nếu MC count đã đến min_mc mà vẫn vượt budget: thử cắt giảm context chunks
            if len(current_chunks) > 3:
                current_chunks.pop()  # Cắt bớt chunk cuối
                continue

            # Nếu cả context và MC đều đã ở mức tối thiểu mà vẫn vượt budget:
            return current_chunks, current_mc, current_essay, estimates

    def log_token_decision(
        self,
        provider: str,
        model: str,
        requested_mc: int,
        ai_target_mc: int,
        estimates: Dict[str, int],
        decision: str,
        actual_usage: Dict[str, Any] = None,
    ):
        """
        Ghi log token chuẩn mực theo yêu cầu Section 26.
        """
        log_msg = (
            f"\n[QUIZ TOKEN]\n"
            f"Provider: {provider.upper()}\n"
            f"Model: {model}\n"
            f"Requested: MC={requested_mc}\n"
            f"AI target: MC={ai_target_mc}\n"
            f"Estimated input: {estimates.get('input_tokens', 0)}\n"
            f"Estimated output: {estimates.get('output_tokens', 0)}\n"
            f"Estimated total: {estimates.get('total_tokens', 0)}\n"
            f"Budget: {self.budget}\n"
            f"Decision: {decision}\n"
        )
        if actual_usage and isinstance(actual_usage, dict):
            log_msg += (
                f"Actual input: {actual_usage.get('input_tokens', 'UNKNOWN')}\n"
                f"Actual output: {actual_usage.get('output_tokens', 'UNKNOWN')}\n"
                f"Actual total: {actual_usage.get('total_tokens', 'UNKNOWN')}\n"
            )
        else:
            log_msg += "Actual usage: UNKNOWN\n"

        logger.info(log_msg)

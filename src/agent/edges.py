from __future__ import annotations

import logging
from typing import Literal

from langgraph.graph import END

from configs import agent_settings

logger = logging.getLogger(__name__)

# Import từ agent.graph được thực hiện bên trong từng hàm (function-local).
# Tránh circular import: lúc edges.py được load, agent.graph có thể đang
# load dở; chỉ khi routing chạy thì graph.py đã load xong → import an toàn.


# ============================================================
# Conditional edge routing
# ============================================================


def should_continue(state) -> Literal["tools", END]:
    """Sau node `agent`: có tool_calls → `tools`, ngược lại → END."""

    last_message = state["messages"][-1]

    if last_message.tool_calls:
        return "tools"

    return END


def route_after_tools(state) -> Literal["rewrite", "agent"]:
    """Sau node `grade`: rỗng + còn lượt → `rewrite`, ngược lại → `agent`.

    Khi rỗng, ta ép agent viết lại query. Khi đủ thông tin (hoặc đã hết
    lượt retry), ta để agent tổng hợp trả lời cuối.
    """

    max_attempts = agent_settings.max_search_attempts
    attempts = state.get("search_attempts", 0)
    empty = state.get("last_search_empty", False)

    logger.info(
        "route_after_tools: attempts=%d max=%d empty=%s",
        attempts,
        max_attempts,
        empty,
    )

    if empty and attempts < max_attempts:
        return "rewrite"

    return "agent"

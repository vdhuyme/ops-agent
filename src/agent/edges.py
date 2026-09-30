from __future__ import annotations

from typing import Literal

# Import từ agent.graph được thực hiện bên trong từng hàm (function-local).
# Tránh circular import: lúc edges.py được load, agent.graph có thể đang
# load dở; chỉ khi routing chạy thì graph.py đã load xong → import an toàn.


# ============================================================
# Conditional edge routing
# ============================================================


def should_continue(state) -> Literal["tools", "__end__"]:
    """Sau node `agent`: có tool_calls → `tools`, ngược lại → END."""

    last_message = state["messages"][-1]

    if last_message.tool_calls:
        return "tools"

    return "__end__"


def route_after_tools(state) -> Literal["rewrite", "agent"]:
    """Sau node `grade`: rỗng + còn lượt → `rewrite`, ngược lại → `agent`.

    Khi rỗng, ta ép agent viết lại query. Khi đủ thông tin (hoặc đã hết
    lượt retry), ta để agent tổng hợp trả lời cuối.
    """

    from agent.graph import MAX_SEARCH_ATTEMPTS

    if (
        state.get("last_search_empty")
        and state.get("search_attempts", 0) < MAX_SEARCH_ATTEMPTS
    ):
        return "rewrite"

    return "agent"

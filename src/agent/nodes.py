from __future__ import annotations

import logging

from langchain.messages import HumanMessage, SystemMessage

from configs import agent_settings

logger = logging.getLogger(__name__)

# ============================================================
# Nodes
# ============================================================


def call_model(state):
    """Node `agent` — gọi LLM với system prompt đã render + lịch sử chat."""

    from agent.graph import _render_system_prompt, model

    messages = [
        SystemMessage(content=_render_system_prompt()),
        *state["messages"],
    ]

    response = model.invoke(messages)

    return {"messages": [response]}


def grade_search(state):
    """Node `grade` — sau khi tool chạy, đánh dấu rỗng/không và tăng bộ đếm."""

    last = state["messages"][-1]
    content = getattr(last, "content", "") or ""
    empty = "Không tìm thấy" in content or not content.strip()

    attempts = state.get("search_attempts", 0) + 1

    logger.info(
        "grade_search: attempts=%d empty=%s content_len=%d",
        attempts,
        empty,
        len(content.strip()),
    )

    return {
        "search_attempts": attempts,
        "last_search_empty": empty,
    }


def rewrite_query(state):
    """Node `rewrite` — bơm 1 HumanMessage ép agent gọi lại tool với query viết lại."""

    max_attempts = agent_settings.max_search_attempts
    next_attempt = state["search_attempts"] + 1

    logger.info("rewrite_query: attempt %d/%d", next_attempt, max_attempts)

    return {
        "messages": [
            HumanMessage(
                content=(
                    "Kết quả search vừa rỗng. Hãy VIẾT LẠI query "
                    "(thêm từ đồng nghĩa, tách câu đơn giản hơn, "
                    "thử dùng từ khoá khác) rồi gọi lại "
                    "search_knowledge_base ngay. "
                    f"(Lần thử {next_attempt}/{max_attempts})"
                )
            )
        ],
    }

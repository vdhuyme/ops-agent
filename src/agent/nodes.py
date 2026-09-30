from __future__ import annotations

from langchain.messages import HumanMessage, SystemMessage

# Import từ agent.graph được thực hiện bên trong từng hàm (function-local).
# Tránh circular import: lúc nodes.py được load, agent.graph có thể đang
# load dở; chỉ khi LLM gọi node thì graph.py đã load xong → import an toàn.


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

    return {
        "search_attempts": state.get("search_attempts", 0) + 1,
        "last_search_empty": empty,
    }


def rewrite_query(state):
    """Node `rewrite` — bơm 1 HumanMessage ép agent gọi lại tool với query viết lại."""

    from agent.graph import MAX_SEARCH_ATTEMPTS

    return {
        "messages": [
            HumanMessage(
                content=(
                    "Kết quả search vừa rỗng. Hãy VIẾT LẠI query "
                    "(thêm từ đồng nghĩa, tách câu đơn giản hơn, "
                    "thử dùng từ khoá khác) rồi gọi lại "
                    "search_knowledge_base ngay. "
                    f"(Lần thử {state['search_attempts'] + 1}/{MAX_SEARCH_ATTEMPTS})"
                )
            )
        ],
    }

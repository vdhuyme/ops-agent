"""Tools cho agent — kèm setup Chroma collection.

Tools định nghĩa ở đây tự mô tả mình (docstring) và được auto đưa vào
system prompt bởi `_render_tools_section` trong `agent.graph`.
"""

from __future__ import annotations

from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
from langchain.tools import tool
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.prebuilt import ToolNode

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
CHROMA_DIR = PROJECT_ROOT / ".chroma"
COLLECTION_NAME = "ops_agent"

# ============================================================
# Chroma
# ============================================================


chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
embedding_fn = ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"])

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
)


def _load_markdown_chunks() -> list[dict]:
    """Read every .md file under DATA_DIR and split into chunks."""

    if not DATA_DIR.exists():
        raise RuntimeError(
            f"Knowledge directory '{DATA_DIR}' does not exist. "
            "Create it and add at least one .md file."
        )

    chunks: list[dict] = []

    for path in sorted(DATA_DIR.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        for idx, chunk in enumerate(text_splitter.split_text(content)):
            chunks.append(
                {
                    "id": f"{path.name}_{idx}",
                    "text": chunk,
                    "source": path.name,
                }
            )

    if not chunks:
        raise RuntimeError(
            f"No .md files found in {DATA_DIR}. "
            "Add at least one markdown file to build the knowledge base."
        )

    return chunks


def _load_collection():
    """Return the persisted Chroma collection, building it from .md on first run."""

    collection = chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
    )

    if collection.count() == 0:
        chunks = _load_markdown_chunks()

        collection.add(
            documents=[c["text"] for c in chunks],
            metadatas=[{"source": c["source"]} for c in chunks],
            ids=[c["id"] for c in chunks],
        )

    return collection


collection = _load_collection()


# ============================================================
# Tool definitions
# ============================================================


@tool
def search_knowledge_base(query: str) -> str:
    """Tìm trong kho tài liệu (chính sách, FAQ, hướng dẫn, gói cước).

    Dùng khi khách hỏi về chính sách, gói dịch vụ, thủ tục,
    thời hạn hoặc bất kỳ câu hỏi nào cần tra cứu tài liệu nội bộ.
    """

    results = collection.query(query_texts=[query], n_results=2)

    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]

    if not docs:
        return f"Không tìm thấy thông tin cho: {query}"

    pieces = []
    for doc, meta in zip(docs, metas):
        source = (meta or {}).get("source", "unknown")
        pieces.append(f"[{source}]\n{doc}")

    return "\n\n---\n\n".join(pieces)


tools = [
    search_knowledge_base,
]

tool_node = ToolNode(tools)

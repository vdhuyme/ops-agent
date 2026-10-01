"""Tools cho agent — kèm setup Chroma collection.

Tools định nghĩa ở đây tự mô tả mình (docstring) và được auto đưa vào
system prompt bởi `_render_tools_section` trong `agent.graph`.
"""

from __future__ import annotations

import logging
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
from langchain.tools import tool
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.prebuilt import ToolNode

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
CHROMA_DIR = PROJECT_ROOT / ".chroma"
COLLECTION_NAME = "ops_agent"

# ============================================================
# Chroma — client/embedding init ở module level (fast, không có data load)
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


# Lazy-load collection — chỉ build khi tool được gọi lần đầu.
# Tránh fail ngay lúc import nếu data/ rỗng, và giảm startup time.
_collection = None


def _get_collection():
    """Lazy-init Chroma collection (build từ .md nếu lần đầu)."""

    global _collection

    if _collection is None:
        logger.info("Initializing Chroma collection '%s'...", COLLECTION_NAME)

        _collection = chroma_client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn,
        )

        if _collection.count() == 0:
            chunks = _load_markdown_chunks()
            _collection.add(
                documents=[c["text"] for c in chunks],
                metadatas=[{"source": c["source"]} for c in chunks],
                ids=[c["id"] for c in chunks],
            )
            logger.info("Loaded %d chunks into collection.", len(chunks))

    return _collection


# ============================================================
# Tool definitions
# ============================================================


@tool
def search_knowledge_base(query: str) -> str:
    """Tìm trong kho tài liệu (chính sách, FAQ, hướng dẫn, gói cước).

    Dùng khi khách hỏi về chính sách, gói dịch vụ, thủ tục,
    thời hạn hoặc bất kỳ câu hỏi nào cần tra cứu tài liệu nội bộ.
    """

    try:
        collection = _get_collection()
        results = collection.query(query_texts=[query], n_results=5)
    except Exception as e:
        logger.exception("Chroma query failed for query=%r", query)
        return f"Lỗi truy vấn knowledge base: {e}"

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

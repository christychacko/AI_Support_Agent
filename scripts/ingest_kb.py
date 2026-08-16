"""
Run this whenever you add/update files in app/data/knowledge_base/.

    python scripts/ingest_kb.py

Splits each markdown file into paragraph-sized chunks and upserts them into
the local Chroma collection defined in app/tools/rag_tool.py.
"""
from __future__ import annotations

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.tools.rag_tool import get_collection  # noqa: E402

KB_DIR = pathlib.Path(__file__).resolve().parents[1] / "app" / "data" / "knowledge_base"


def chunk_text(text: str, min_len: int = 40) -> list[str]:
    paragraphs = re.split(r"\n\s*\n", text.strip())
    return [p.strip() for p in paragraphs if len(p.strip()) >= min_len]


def main() -> None:
    collection = get_collection()

    ids, docs, metadatas = [], [], []
    for path in sorted(KB_DIR.glob("*.md")):
        chunks = chunk_text(path.read_text(encoding="utf-8"))
        for i, chunk in enumerate(chunks):
            ids.append(f"{path.stem}-{i}")
            docs.append(chunk)
            metadatas.append({"source": path.name})

    if not ids:
        print(f"No markdown files found in {KB_DIR}")
        return

    collection.upsert(ids=ids, documents=docs, metadatas=metadatas)
    print(f"Ingested {len(ids)} chunks from {len(list(KB_DIR.glob('*.md')))} files into Chroma.")


if __name__ == "__main__":
    main()

"""
Step 2: Embed chunks and store them in a local Chroma collection.

Uses BAAI/bge-base-en-v1.5 instead of Chroma's default all-MiniLM-L6-v2.
bge-base is a stronger retrieval-focused embedding model -- still runs entirely
locally, no API key, no GPU required, just a larger one-time download (~440MB)
and slightly slower embedding than MiniLM.

bge-base is an "asymmetric" model: documents are embedded as-is, but queries
need an instruction prefix for best results. That prefix is applied in
retrieve.py at query time, not here -- do not add it to document text.

The embedded text is deliberately NOT just the chunk body: we prepend the
citation path (doc title > section) and append the screenshot alt-text. Section
headings carry a lot of the meaning in this manual ("Step 3: Set a Match
Decision" is more informative than the sentence under it), and the alt-text
names UI elements users search for by name ("Add New button", "Toolbox icon").

Usage:  python build_index.py --chunks chunks.json --db ./chroma
"""

import argparse
import json
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

COLLECTION = "helpdesk_docs"
EMBED_MODEL = "BAAI/bge-base-en-v1.5"


def get_embedding_function():
    return SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)


def embed_text(chunk):
    """The text actually sent to the embedding model."""
    parts = [chunk["citation"], chunk["content"]]
    if chunk["image_alts"]:
        parts.append("Screenshots: " + "; ".join(chunk["image_alts"]))
    return "\n\n".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", default="chunks.json")
    ap.add_argument("--db", default="./chroma")
    args = ap.parse_args()

    chunks = json.loads(Path(args.chunks).read_text(encoding="utf-8"))

    client = chromadb.PersistentClient(path=args.db)
    # Rebuild from scratch so re-running is idempotent.
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass

    print(f"Loading {EMBED_MODEL} (first run downloads ~440MB, may take a few minutes)...")
    embedding_function = get_embedding_function()
    col = client.create_collection(
        COLLECTION,
        embedding_function=embedding_function,
        metadata={"hnsw:space": "cosine"},
    )

    col.add(
        ids=[c["id"] for c in chunks],
        documents=[embed_text(c) for c in chunks],
        metadatas=[
            {
                "source_file": c["source_file"],
                "doc_title": c["doc_title"],
                "section": c["section"] or "",
                "citation": c["citation"],
                "doc_type": c["doc_type"],
            }
            for c in chunks
        ],
    )

    print(f"indexed {col.count()} chunks -> {args.db}")


if __name__ == "__main__":
    main()

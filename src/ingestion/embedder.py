"""
embedder.py — Phase 1.4: Embedding & Vector Store

Generates embeddings for all text chunks using sentence-transformers
and upserts them into a persistent ChromaDB collection.

Deduplication: chunks with a matching content_hash already in the
collection are skipped (no re-embedding).

Collection name : "mutual_funds"
Persist directory: CHROMA_PERSIST_DIR (default: ./vectorstore)
"""

import os
import logging
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
EMBEDDING_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./vectorstore")
COLLECTION_NAME = "mutual_funds"

# Batch size for embedding generation (reduces memory pressure)
EMBED_BATCH_SIZE = 32


# ---------------------------------------------------------------------------
# Lazy singletons (initialised on first use)
# ---------------------------------------------------------------------------
_embedding_model: Optional[SentenceTransformer] = None
_chroma_client: Optional[chromadb.PersistentClient] = None
_collection = None


def get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        logger.info("Loading embedding model: %s", EMBEDDING_MODEL_NAME)
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedding_model


def get_chroma_collection():
    """Return (or create) the persistent ChromaDB collection."""
    global _chroma_client, _collection
    if _collection is None:
        persist_path = Path(CHROMA_PERSIST_DIR)
        persist_path.mkdir(parents=True, exist_ok=True)

        _chroma_client = chromadb.PersistentClient(
            path=str(persist_path),
            settings=Settings(anonymized_telemetry=False),
        )
        _collection = _chroma_client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},  # cosine similarity
        )
        logger.info(
            "ChromaDB collection '%s' ready at %s (existing docs: %d).",
            COLLECTION_NAME,
            CHROMA_PERSIST_DIR,
            _collection.count(),
        )
    return _collection


# ---------------------------------------------------------------------------
# Core embedding + upsert logic
# ---------------------------------------------------------------------------

def _get_existing_hashes(collection) -> set[str]:
    """Fetch all content_hash values already indexed in the collection."""
    try:
        results = collection.get(include=["metadatas"])
        return {
            m["content_hash"]
            for m in results["metadatas"]
            if m and "content_hash" in m
        }
    except Exception:
        return set()


def embed_and_index_chunks(chunks: list[dict]) -> dict:
    """
    Embed a list of chunk dicts and upsert into ChromaDB.

    Deduplication: chunks whose content_hash is already in the
    collection are skipped.

    Args:
        chunks: List of chunk dicts from chunker.chunk_all_funds()

    Returns:
        {
            "indexed"  : int,   # new chunks added
            "skipped"  : int,   # duplicates skipped
            "total_in" : int,   # total chunks provided
        }
    """
    collection = get_chroma_collection()
    model = get_embedding_model()

    existing_hashes = _get_existing_hashes(collection)
    logger.info("Found %d existing hashes in collection.", len(existing_hashes))

    # Filter out duplicates
    new_chunks = [c for c in chunks if c["content_hash"] not in existing_hashes]
    skipped = len(chunks) - len(new_chunks)

    if skipped:
        logger.info("Skipping %d duplicate chunks (already indexed).", skipped)

    if not new_chunks:
        logger.info("No new chunks to index.")
        return {"indexed": 0, "skipped": skipped, "total_in": len(chunks)}

    indexed = 0

    # Process in batches
    for batch_start in range(0, len(new_chunks), EMBED_BATCH_SIZE):
        batch = new_chunks[batch_start : batch_start + EMBED_BATCH_SIZE]
        texts = [c["text"] for c in batch]

        logger.info(
            "Embedding batch %d–%d / %d ...",
            batch_start + 1,
            batch_start + len(batch),
            len(new_chunks),
        )

        embeddings = model.encode(texts, show_progress_bar=False).tolist()

        ids = [c["chunk_id"] for c in batch]
        metadatas = [
            {
                "source_url": c["source_url"],
                "fund_name": c["fund_name"],
                "fund_key": c["fund_key"],
                "category": c["category"],
                "scraped_at": c["scraped_at"],
                "content_hash": c["content_hash"],
                "chunk_index": c["chunk_index"],
            }
            for c in batch
        ]

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )
        indexed += len(batch)
        logger.info("Upserted %d chunks (running total: %d).", len(batch), indexed)

    logger.info(
        "Embedding complete. Indexed: %d | Skipped: %d | Total in collection: %d",
        indexed,
        skipped,
        collection.count(),
    )
    return {"indexed": indexed, "skipped": skipped, "total_in": len(chunks)}


def embed_all_funds(all_chunks: dict[str, list[dict]]) -> dict:
    """
    Embed and index chunks for all funds.

    Args:
        all_chunks: Output of chunker.chunk_all_funds()

    Returns:
        Summary stats dict.
    """
    flat_chunks = [chunk for chunks in all_chunks.values() for chunk in chunks]
    logger.info("Total chunks to process: %d", len(flat_chunks))
    return embed_and_index_chunks(flat_chunks)


def get_collection_stats() -> dict:
    """Return basic stats about the current ChromaDB collection."""
    collection = get_chroma_collection()
    count = collection.count()
    return {
        "collection_name": COLLECTION_NAME,
        "persist_dir": CHROMA_PERSIST_DIR,
        "total_chunks": count,
    }


if __name__ == "__main__":
    stats = get_collection_stats()
    print("Collection stats:", stats)

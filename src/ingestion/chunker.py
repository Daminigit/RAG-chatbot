"""
chunker.py — Phase 1.3: Chunking & Metadata Tagging

Splits cleaned fund text into overlapping chunks using LangChain's
RecursiveCharacterTextSplitter and attaches source metadata to each chunk.

Saves chunks to: data/processed/<fund_key>_chunks.json
"""

import json
import hashlib
import logging
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Chunking configuration (as per Architecture.md §3.1)
# ---------------------------------------------------------------------------
CHUNK_SIZE = 512      # characters
CHUNK_OVERLAP = 64    # characters


def _compute_hash(text: str) -> str:
    """SHA-256 hash of chunk text for deduplication."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunk_fund_document(
    fund_key: str,
    text: str,
    fund_name: str,
    category: str,
    source_url: str,
    scraped_at: str,
) -> list[dict]:
    """
    Split a cleaned fund document into overlapping chunks and
    attach metadata to each chunk.

    Args:
        fund_key    : Unique key (e.g. "hdfc_mid_cap")
        text        : Cleaned plain-text content
        fund_name   : Human-readable fund name
        category    : Fund category (e.g. "Mid Cap")
        source_url  : Original Groww URL
        scraped_at  : ISO-8601 UTC timestamp of scrape

    Returns:
        List of chunk dicts, each with keys:
            - chunk_id    : Unique identifier (fund_key + hash prefix)
            - text        : Chunk content
            - content_hash: SHA-256 of chunk text (for deduplication)
            - source_url  : Groww fund page URL
            - fund_name   : Fund name
            - fund_key    : Fund key
            - category    : Fund category
            - scraped_at  : Timestamp of source scrape
            - chunk_index : Position of this chunk within the document
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    raw_chunks = splitter.split_text(text)
    logger.info("[%s] Split into %d chunks (size=%d, overlap=%d).",
                fund_key, len(raw_chunks), CHUNK_SIZE, CHUNK_OVERLAP)

    chunks: list[dict] = []
    for idx, chunk_text in enumerate(raw_chunks):
        chunk_text = chunk_text.strip()
        if not chunk_text:
            continue

        content_hash = _compute_hash(chunk_text)
        chunk_id = f"{fund_key}_{content_hash[:12]}_{idx}"

        chunks.append({
            "chunk_id": chunk_id,
            "text": chunk_text,
            "content_hash": content_hash,
            "source_url": source_url,
            "fund_name": fund_name,
            "fund_key": fund_key,
            "category": category,
            "scraped_at": scraped_at,
            "chunk_index": idx,
        })

    return chunks


def save_chunks(fund_key: str, chunks: list[dict], processed_dir: Path) -> Path:
    """Persist chunks as JSON to data/processed/<fund_key>_chunks.json."""
    processed_dir.mkdir(parents=True, exist_ok=True)
    out_path = processed_dir / f"{fund_key}_chunks.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    logger.info("[%s] Saved %d chunks → %s", fund_key, len(chunks), out_path)
    return out_path


def chunk_all_funds(
    fund_data: dict[str, dict],
    processed_dir: Path,
) -> dict[str, list[dict]]:
    """
    Chunk all scraped fund documents.

    Args:
        fund_data     : Output of scraper.scrape_all_funds()
        processed_dir : Directory to save chunk JSON files

    Returns:
        {fund_key: [chunk_dict, ...]}
    """
    all_chunks: dict[str, list[dict]] = {}

    for fund_key, data in fund_data.items():
        chunks = chunk_fund_document(
            fund_key=fund_key,
            text=data["text"],
            fund_name=data["fund_name"],
            category=data["category"],
            source_url=data["source_url"],
            scraped_at=data["scraped_at"],
        )
        save_chunks(fund_key, chunks, processed_dir)
        all_chunks[fund_key] = chunks

    total = sum(len(c) for c in all_chunks.values())
    logger.info("Chunking complete. %d total chunks across %d funds.", total, len(all_chunks))
    return all_chunks


if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Quick standalone test with a sample text
    sample = {
        "hdfc_mid_cap": {
            "text": (
                "Fund Name: HDFC Mid Cap Opportunities Fund\n"
                "Category: Mid Cap\n"
                "Source: https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth\n\n"
                "Expense Ratio: 1.56%\n"
                "Exit Load: 1% if redeemed within 1 year.\n"
                "Minimum SIP: ₹100 per month.\n"
                "Benchmark: NIFTY Midcap 150 TRI\n"
                "Riskometer: Very High Risk\n"
            ),
            "fund_name": "HDFC Mid Cap Opportunities Fund",
            "category": "Mid Cap",
            "source_url": "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
            "scraped_at": "2024-01-15T10:30:00Z",
        }
    }

    chunks = chunk_all_funds(sample, Path("./data/processed"))
    for key, clist in chunks.items():
        print(f"\n{key}: {len(clist)} chunks")
        for c in clist[:2]:
            print(f"  [{c['chunk_id']}] {c['text'][:80]}...")

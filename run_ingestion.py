"""
run_ingestion.py — Phase 1 Entrypoint

Runs the full data ingestion pipeline end-to-end:
  1. Scrape all 5 Groww HDFC fund pages (requests → Playwright fallback)
  2. Parse HTML into clean plain text
  3. Chunk text with metadata tagging
  4. Embed chunks and upsert into ChromaDB

Usage:
    python run_ingestion.py

Environment:
    Copy .env.example to .env and fill in values before running.
"""

import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("ingestion")

# Project imports
from src.ingestion.scraper import scrape_all_funds
from src.ingestion.chunker import chunk_all_funds
from src.ingestion.embedder import embed_all_funds, get_collection_stats

PROCESSED_DIR = Path("./data/processed")


def run():
    logger.info("=" * 60)
    logger.info("MUTUAL FUND FAQ ASSISTANT — Data Ingestion Pipeline")
    logger.info("=" * 60)

    # ── Step 1: Scrape ──────────────────────────────────────────
    logger.info("\n[Step 1/3] Scraping Groww fund pages...")
    fund_data = scrape_all_funds()

    if not fund_data:
        logger.error("No fund data scraped. Aborting.")
        sys.exit(1)

    logger.info("Scraped %d / 5 funds successfully.", len(fund_data))

    # ── Step 2: Chunk ───────────────────────────────────────────
    logger.info("\n[Step 2/3] Chunking documents...")
    all_chunks = chunk_all_funds(fund_data, PROCESSED_DIR)

    total_chunks = sum(len(c) for c in all_chunks.values())
    logger.info("Total chunks created: %d", total_chunks)

    # ── Step 3: Embed & Index ───────────────────────────────────
    logger.info("\n[Step 3/3] Embedding & indexing into ChromaDB...")
    stats = embed_all_funds(all_chunks)

    # ── Summary ─────────────────────────────────────────────────
    collection_stats = get_collection_stats()

    logger.info("\n" + "=" * 60)
    logger.info("INGESTION COMPLETE")
    logger.info("=" * 60)
    logger.info("  Funds scraped  : %d", len(fund_data))
    logger.info("  Chunks created : %d", total_chunks)
    logger.info("  New indexed    : %d", stats["indexed"])
    logger.info("  Duplicates     : %d", stats["skipped"])
    logger.info("  Total in DB    : %d", collection_stats["total_chunks"])
    logger.info("  Vector store   : %s", collection_stats["persist_dir"])
    logger.info("=" * 60)

    # ── Per-fund summary ─────────────────────────────────────────
    print("\nPer-fund summary:")
    print(f"{'Fund Key':<25} {'Chunks':>8} {'Scraped At':>32}")
    print("-" * 68)
    for fund_key, chunks in all_chunks.items():
        scraped_at = fund_data[fund_key]["scraped_at"] if fund_key in fund_data else "N/A"
        print(f"{fund_key:<25} {len(chunks):>8} {scraped_at:>32}")


if __name__ == "__main__":
    run()

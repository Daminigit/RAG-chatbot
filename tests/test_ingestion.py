"""
tests/test_ingestion.py — Phase 1 Unit Tests

Tests for scraper, chunker, and embedder modules.
Playwright and network calls are mocked where possible.
"""

import json
import hashlib
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# ─── Scraper tests ────────────────────────────────────────────────────────────

class TestScraper:
    """Tests for src/ingestion/scraper.py"""

    def test_is_js_rendered_positive(self):
        from src.ingestion.scraper import _is_js_rendered
        html = "<html>Expense Ratio 1.5% Exit Load Nil Minimum SIP ₹100</html>"
        assert _is_js_rendered(html) is True

    def test_is_js_rendered_negative(self):
        from src.ingestion.scraper import _is_js_rendered
        html = "<html><body>Loading...</body></html>"
        assert _is_js_rendered(html) is False

    def test_fund_urls_all_present(self):
        from src.ingestion.scraper import FUND_URLS
        expected_keys = {
            "hdfc_mid_cap", "hdfc_small_cap", "hdfc_gold_etf_fof",
            "hdfc_large_cap", "hdfc_elss"
        }
        assert set(FUND_URLS.keys()) == expected_keys

    def test_fund_urls_all_groww(self):
        from src.ingestion.scraper import FUND_URLS
        for key, meta in FUND_URLS.items():
            assert meta["url"].startswith("https://groww.in/"), \
                f"{key} URL is not a Groww URL: {meta['url']}"

    def test_parse_fund_html_extracts_fields(self):
        from src.ingestion.scraper import parse_fund_html, FUND_URLS

        sample_html = """
        <html><body>
          <div>Expense Ratio: 1.56%</div>
          <div>Exit Load: 1% if redeemed within 1 year</div>
          <div>Minimum SIP: ₹100 per month</div>
          <div>Riskometer: Very High Risk</div>
          <div>Benchmark: NIFTY Midcap 150 TRI</div>
          <script>var x = 1;</script>
          <nav>Navigation content</nav>
        </body></html>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.ingestion.scraper.PROCESSED_DIR", Path(tmpdir)):
                meta = FUND_URLS["hdfc_mid_cap"]
                text = parse_fund_html("hdfc_mid_cap", sample_html, meta)

        assert "HDFC Mid Cap Opportunities Fund" in text
        assert "expense" in text.lower() or "1.56" in text
        # Navigation should be stripped
        assert "Navigation content" not in text

    def test_save_raw_html_creates_file(self):
        from src.ingestion.scraper import _save_raw_html
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.ingestion.scraper.RAW_DIR", Path(tmpdir)):
                _save_raw_html("test_fund", "<html>test</html>")
            assert (Path(tmpdir) / "test_fund.html").exists()

    def test_save_processed_text_creates_file(self):
        from src.ingestion.scraper import _save_processed_text
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.ingestion.scraper.PROCESSED_DIR", Path(tmpdir)):
                _save_processed_text("test_fund", "Fund Name: Test\nExpense Ratio: 1%")
            assert (Path(tmpdir) / "test_fund.txt").exists()


# ─── Chunker tests ────────────────────────────────────────────────────────────

class TestChunker:
    """Tests for src/ingestion/chunker.py"""

    SAMPLE_TEXT = (
        "Fund Name: HDFC Mid Cap Opportunities Fund\n"
        "Category: Mid Cap\n"
        "Source: https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth\n\n"
        "Expense Ratio: 1.56%\n"
        "Exit Load: 1% if redeemed within 1 year.\n"
        "Minimum SIP: ₹100 per month.\n"
        "Benchmark: NIFTY Midcap 150 TRI\n"
        "Riskometer: Very High Risk\n"
        "Fund Manager: Chirag Setalvad\n" * 10  # repeat to generate multiple chunks
    )

    def _make_chunks(self):
        from src.ingestion.chunker import chunk_fund_document
        return chunk_fund_document(
            fund_key="hdfc_mid_cap",
            text=self.SAMPLE_TEXT,
            fund_name="HDFC Mid Cap Opportunities Fund",
            category="Mid Cap",
            source_url="https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
            scraped_at="2024-01-15T10:30:00Z",
        )

    def test_chunks_are_produced(self):
        chunks = self._make_chunks()
        assert len(chunks) > 0

    def test_chunk_has_required_metadata_keys(self):
        chunks = self._make_chunks()
        required = {
            "chunk_id", "text", "content_hash", "source_url",
            "fund_name", "fund_key", "category", "scraped_at", "chunk_index"
        }
        for chunk in chunks:
            assert required.issubset(set(chunk.keys())), \
                f"Missing keys in chunk: {required - set(chunk.keys())}"

    def test_chunk_size_within_limit(self):
        chunks = self._make_chunks()
        from src.ingestion.chunker import CHUNK_SIZE
        for chunk in chunks:
            # Allow small overshoot due to splitter behaviour
            assert len(chunk["text"]) <= CHUNK_SIZE * 1.2, \
                f"Chunk too long: {len(chunk['text'])} chars"

    def test_chunk_metadata_values(self):
        chunks = self._make_chunks()
        for chunk in chunks:
            assert chunk["fund_key"] == "hdfc_mid_cap"
            assert chunk["category"] == "Mid Cap"
            assert chunk["source_url"].startswith("https://groww.in/")
            assert chunk["scraped_at"] == "2024-01-15T10:30:00Z"

    def test_chunk_ids_are_unique(self):
        chunks = self._make_chunks()
        ids = [c["chunk_id"] for c in chunks]
        assert len(ids) == len(set(ids)), "Duplicate chunk_ids detected"

    def test_content_hash_matches_text(self):
        chunks = self._make_chunks()
        for chunk in chunks:
            expected = hashlib.sha256(chunk["text"].encode()).hexdigest()
            assert chunk["content_hash"] == expected

    def test_save_chunks_creates_json_file(self):
        from src.ingestion.chunker import save_chunks
        chunks = self._make_chunks()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_chunks("hdfc_mid_cap", chunks, Path(tmpdir))
            assert path.exists()
            with open(path) as f:
                loaded = json.load(f)
            assert len(loaded) == len(chunks)

    def test_chunk_all_funds_processes_multiple(self):
        from src.ingestion.chunker import chunk_all_funds
        fund_data = {
            "hdfc_mid_cap": {
                "text": self.SAMPLE_TEXT,
                "fund_name": "HDFC Mid Cap Opportunities Fund",
                "category": "Mid Cap",
                "source_url": "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
                "scraped_at": "2024-01-15T10:30:00Z",
            },
            "hdfc_elss": {
                "text": "ELSS Fund.\nLock-in Period: 3 years.\nExit Load: Nil.\n" * 10,
                "fund_name": "HDFC ELSS Tax Saver Fund",
                "category": "ELSS / Tax Saving",
                "source_url": "https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth",
                "scraped_at": "2024-01-15T10:30:00Z",
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            result = chunk_all_funds(fund_data, Path(tmpdir))
        assert "hdfc_mid_cap" in result
        assert "hdfc_elss" in result
        assert all(len(chunks) > 0 for chunks in result.values())


# ─── Embedder tests (mocked) ──────────────────────────────────────────────────

class TestEmbedder:
    """Tests for src/ingestion/embedder.py (ChromaDB and model are mocked)"""

    SAMPLE_CHUNKS = [
        {
            "chunk_id": "hdfc_mid_cap_abc123",
            "text": "Expense Ratio: 1.56%",
            "content_hash": "abc123def456" + "0" * 52,
            "source_url": "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
            "fund_name": "HDFC Mid Cap Opportunities Fund",
            "fund_key": "hdfc_mid_cap",
            "category": "Mid Cap",
            "scraped_at": "2024-01-15T10:30:00Z",
            "chunk_index": 0,
        }
    ]

    @patch("src.ingestion.embedder.get_chroma_collection")
    @patch("src.ingestion.embedder.get_embedding_model")
    def test_embed_and_index_chunks_indexes_new(self, mock_model, mock_collection):
        import numpy as np
        from src.ingestion.embedder import embed_and_index_chunks

        # Mock model: returns a list of 1 embedding vector
        mock_model.return_value.encode.return_value = np.array([[0.1] * 384])

        # Mock collection: no existing hashes
        mock_col = MagicMock()
        mock_col.get.return_value = {"metadatas": []}
        mock_col.count.return_value = 1
        mock_collection.return_value = mock_col

        stats = embed_and_index_chunks(self.SAMPLE_CHUNKS)

        assert stats["indexed"] == 1
        assert stats["skipped"] == 0
        mock_col.upsert.assert_called_once()

    @patch("src.ingestion.embedder.get_chroma_collection")
    @patch("src.ingestion.embedder.get_embedding_model")
    def test_embed_skips_duplicates(self, mock_model, mock_collection):
        import numpy as np
        from src.ingestion.embedder import embed_and_index_chunks

        mock_model.return_value.encode.return_value = np.array([[0.1] * 384])

        # Collection already has the chunk's hash
        mock_col = MagicMock()
        mock_col.get.return_value = {
            "metadatas": [{"content_hash": self.SAMPLE_CHUNKS[0]["content_hash"]}]
        }
        mock_col.count.return_value = 1
        mock_collection.return_value = mock_col

        stats = embed_and_index_chunks(self.SAMPLE_CHUNKS)

        assert stats["indexed"] == 0
        assert stats["skipped"] == 1
        mock_col.upsert.assert_not_called()

    def test_embedding_model_name_is_minilm(self):
        import importlib
        import src.ingestion.embedder as emb
        assert "MiniLM" in emb.EMBEDDING_MODEL_NAME or "bge" in emb.EMBEDDING_MODEL_NAME.lower()

    def test_collection_name_constant(self):
        from src.ingestion.embedder import COLLECTION_NAME
        assert COLLECTION_NAME == "mutual_funds"

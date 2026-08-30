"""
scraper.py — Phase 1.1 & 1.2: Source Scraping + Document Parsing

Fetches HTML from the 5 official Groww HDFC mutual fund pages.
Primary strategy: requests + BeautifulSoup.
Fallback strategy: Playwright headless browser (for JS-rendered content).

Extracts key fund fields and saves:
  - Raw HTML  → data/raw/<fund_key>.html
  - Clean text → data/processed/<fund_key>.txt
"""

import os
import re
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Corpus: 5 official Groww HDFC fund pages (sole data source)
# ---------------------------------------------------------------------------
FUND_URLS: dict[str, dict] = {
    "hdfc_mid_cap": {
        "url": "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
        "fund_name": "HDFC Mid Cap Opportunities Fund",
        "category": "Mid Cap",
    },
    "hdfc_small_cap": {
        "url": "https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth",
        "fund_name": "HDFC Small Cap Fund",
        "category": "Small Cap",
    },
    "hdfc_gold_etf_fof": {
        "url": "https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth",
        "fund_name": "HDFC Gold ETF Fund of Fund",
        "category": "Gold / Commodity",
    },
    "hdfc_large_cap": {
        "url": "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth",
        "fund_name": "HDFC Large and Mid Cap Fund",
        "category": "Large Cap",
    },
    "hdfc_elss": {
        "url": "https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth",
        "fund_name": "HDFC ELSS Tax Saver Fund",
        "category": "ELSS / Tax Saving",
    },
}

# ---------------------------------------------------------------------------
# Key fields to look for when validating JS content was rendered
# ---------------------------------------------------------------------------
JS_RENDER_SIGNALS = ["expense ratio", "exit load", "minimum sip", "riskometer", "benchmark"]

# ---------------------------------------------------------------------------
# HTTP headers to avoid bot-detection
# ---------------------------------------------------------------------------
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

RAW_DIR = Path(os.getenv("RAW_DATA_DIR", "./data/raw"))
PROCESSED_DIR = Path(os.getenv("PROCESSED_DATA_DIR", "./data/processed"))


# ---------------------------------------------------------------------------
# 1.1  Fetching
# ---------------------------------------------------------------------------

def _fetch_with_requests(url: str) -> Optional[str]:
    """Try fetching page HTML with requests. Returns HTML string or None."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        logger.warning("requests fetch failed for %s: %s", url, e)
        return None


def _is_js_rendered(html: str) -> bool:
    """Check whether JS-rendered fund data is present in the HTML."""
    lower = html.lower()
    hits = sum(1 for signal in JS_RENDER_SIGNALS if signal in lower)
    return hits >= 2  # at least 2 key fields present → content loaded


def _fetch_with_playwright(url: str) -> Optional[str]:
    """
    Fallback: launch a headless Chromium browser via Playwright,
    wait for the page to fully render, then return the final HTML.
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(extra_http_headers={"User-Agent": HEADERS["User-Agent"]})
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)

            # Wait for at least one fund-data selector to appear
            selectors = [
                "text=Expense Ratio",
                "text=Exit Load",
                "text=Minimum SIP",
            ]
            for sel in selectors:
                try:
                    page.wait_for_selector(sel, timeout=10_000)
                    break
                except PWTimeout:
                    continue

            # Extra settle time for dynamic content
            time.sleep(2)
            html = page.content()
            browser.close()
            return html

    except ImportError:
        logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
        return None
    except Exception as e:
        logger.error("Playwright fetch failed for %s: %s", url, e)
        return None


def fetch_fund_page(fund_key: str, url: str) -> Tuple[Optional[str], str]:
    """
    Fetch a Groww fund page. Tries requests first; falls back to Playwright
    if JS-rendered content is not detected.

    Returns:
        (html: Optional[str], scraped_at: str ISO-8601 UTC)
    """
    scraped_at = datetime.now(timezone.utc).isoformat()

    logger.info("Fetching [%s] %s", fund_key, url)
    html = _fetch_with_requests(url)

    if html and _is_js_rendered(html):
        logger.info("[%s] requests fetch succeeded with rendered content.", fund_key)
    else:
        logger.info("[%s] JS content not detected in requests response — falling back to Playwright.", fund_key)
        html = _fetch_with_playwright(url)

    if html:
        _save_raw_html(fund_key, html)
    else:
        logger.error("[%s] All fetch strategies failed.", fund_key)

    return html, scraped_at


def _save_raw_html(fund_key: str, html: str) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"{fund_key}.html"
    path.write_text(html, encoding="utf-8")
    logger.info("Raw HTML saved → %s", path)


# ---------------------------------------------------------------------------
# 1.2  Parsing
# ---------------------------------------------------------------------------

# Patterns for extracting labelled numeric values from text
_PERCENT_RE = re.compile(r"\d+\.?\d*\s*%")
_AMOUNT_RE = re.compile(r"₹\s*\d[\d,]*")
_YEAR_RE = re.compile(r"\d+\s*year", re.I)


def _extract_section_text(soup: BeautifulSoup, label: str, chars: int = 300) -> str:
    """
    Find the first element whose text contains `label` (case-insensitive)
    and return text from that element and its siblings up to `chars` characters.
    """
    tag = soup.find(string=re.compile(label, re.I))
    if not tag:
        return ""
    parent = tag.find_parent()
    if not parent:
        return ""
    # Gather surrounding text
    texts = []
    node = parent
    for _ in range(6):  # walk up to 6 sibling/parent levels
        texts.append(node.get_text(separator=" ", strip=True))
        node = node.find_next_sibling() or node.parent
        if not node:
            break
    combined = " ".join(texts)
    return combined[:chars]


def parse_fund_html(fund_key: str, html: str, fund_meta: dict) -> str:
    """
    Parse a Groww fund page HTML into clean factual plain text.

    Extracts:
      - Fund name, category, source URL
      - Expense Ratio, Exit Load, Minimum SIP, NAV
      - Riskometer, Benchmark Index, ELSS lock-in (if applicable)
      - General fund overview text

    Returns cleaned plain-text string.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove non-content elements
    for tag in soup(["script", "style", "nav", "footer", "header",
                     "aside", "noscript", "iframe", "form"]):
        tag.decompose()

    lines: list[str] = []

    # --- Header metadata ---
    lines.append(f"Fund Name: {fund_meta['fund_name']}")
    lines.append(f"Category: {fund_meta['category']}")
    lines.append(f"Source: {fund_meta['url']}")
    lines.append("")

    # --- Key fields extraction ---
    FIELDS = [
        ("Expense Ratio", "expense ratio"),
        ("Exit Load", "exit load"),
        ("Minimum SIP", "minimum sip"),
        ("Minimum Lump Sum", "minimum.*lump"),
        ("NAV", r"\bnav\b"),
        ("AUM", r"\baum\b"),
        ("Riskometer", "riskometer"),
        ("Risk Level", "risk.*level|very high|moderately high|low risk"),
        ("Benchmark", "benchmark"),
        ("Fund Manager", "fund manager"),
        ("Lock-in Period", "lock.?in"),
        ("ELSS", "elss"),
        ("Returns", "1 year.*return|3 year.*return|5 year.*return"),
    ]

    for display_label, pattern in FIELDS:
        text = _extract_section_text(soup, pattern)
        if text:
            lines.append(f"{display_label}: {text}")

    lines.append("")

    # --- Full visible text fallback (captures any remaining relevant content) ---
    # Extract all visible paragraphs and table cells
    for element in soup.find_all(["p", "td", "th", "li", "h1", "h2", "h3", "span", "div"]):
        text = element.get_text(separator=" ", strip=True)
        # Only keep lines that have some substance and financial keywords
        if len(text) > 30 and any(kw in text.lower() for kw in [
            "expense", "exit", "sip", "nav", "aum", "risk", "benchmark",
            "return", "fund", "growth", "lock", "elss", "direct", "growth",
            "category", "manager", "minimum", "load", "ratio", "period"
        ]):
            lines.append(text)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_lines: list[str] = []
    for line in lines:
        normalised = " ".join(line.split())
        if normalised not in seen:
            seen.add(normalised)
            unique_lines.append(line)

    clean_text = "\n".join(unique_lines)
    _save_processed_text(fund_key, clean_text)
    return clean_text


def _save_processed_text(fund_key: str, text: str) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    path = PROCESSED_DIR / f"{fund_key}.txt"
    path.write_text(text, encoding="utf-8")
    logger.info("Processed text saved → %s (%d chars)", path, len(text))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scrape_all_funds() -> dict[str, dict]:
    """
    Scrape and parse all 5 HDFC fund pages.

    Returns:
        {
            fund_key: {
                "text": str,          # cleaned plain text
                "scraped_at": str,    # ISO-8601 UTC timestamp
                "fund_name": str,
                "category": str,
                "source_url": str,
            }
        }
    """
    results: dict[str, dict] = {}

    for fund_key, meta in FUND_URLS.items():
        html, scraped_at = fetch_fund_page(fund_key, meta["url"])
        if html:
            text = parse_fund_html(fund_key, html, meta)
            results[fund_key] = {
                "text": text,
                "scraped_at": scraped_at,
                "fund_name": meta["fund_name"],
                "category": meta["category"],
                "source_url": meta["url"],
            }
            logger.info("[%s] Parsed — %d characters extracted.", fund_key, len(text))
        else:
            logger.error("[%s] Skipped — no HTML available.", fund_key)

    logger.info("Scraping complete. %d / %d funds successfully scraped.", len(results), len(FUND_URLS))
    return results


if __name__ == "__main__":
    results = scrape_all_funds()
    for key, data in results.items():
        print(f"\n{'='*60}")
        print(f"Fund : {data['fund_name']}")
        print(f"URL  : {data['source_url']}")
        print(f"Date : {data['scraped_at']}")
        print(f"Chars: {len(data['text'])}")
        print(data["text"][:500])

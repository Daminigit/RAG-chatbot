# Implementation Plan: Mutual Fund FAQ Assistant (Facts-Only RAG Chatbot)

> **LLM Provider:** Groq Cloud API (`qwen/qwen3.8-27b`)
> **Vector Store:** ChromaDB (local, persistent)
> **Embedding:** `sentence-transformers/all-MiniLM-L6-v2`
> **UI:** Streamlit
> **Language:** Python 3.11+

---

## Phase 0 — Project Setup & Environment

**Goal:** Establish a clean, reproducible dev environment and project skeleton.

**Duration:** ~0.5 day

### Tasks

- [x] Create repository structure as defined in `Architecture.md §9`
- [x] Create `.env.example` with all required environment variable keys
- [x] Create `requirements.txt` with pinned versions:
  ```
  groq>=0.9.0
  langchain>=0.2.0
  langchain-community>=0.2.0
  langchain-text-splitters>=0.2.0
  chromadb>=0.5.0
  sentence-transformers>=2.7.0
  streamlit>=1.36.0
  requests>=2.32.0
  beautifulsoup4>=4.12.0
  playwright>=1.44.0
  python-dotenv>=1.0.0
  pytest>=8.0.0
  ```
- [x] Set up `.gitignore` (exclude `.env`, `.venv/`, `vectorstore/`, `data/raw/`, `__pycache__/`)
- [x] Create `.venv` virtual environment (`python3 -m venv .venv`) and install all dependencies
- [x] Obtain Groq API key from https://console.groq.com and store in `.env`
- [x] Verify Groq API connectivity (`python scripts/verify_groq.py`) — ✅ `qwen/qwen3.8-27b` connected

> [!NOTE]
> Model updated: `llama3-8b-8192` and `mixtral-8x7b-32768` are deprecated on this account.
> **Primary:** `qwen/qwen3.8-27b` | **Fallback:** `openai/gpt-oss-20b`

**Deliverable:** ✅ Working dev environment; Groq API key validated.


---

## Phase 1 — Data Ingestion Pipeline

**Goal:** Scrape, parse, chunk, embed, and index all 5 HDFC mutual fund pages into ChromaDB.

**Duration:** ~1–1.5 days

### 1.1 Source Scraping (`src/ingestion/scraper.py`)

- [x] **Task:** Fetch HTML content from all 5 official Groww fund pages.

```python
FUND_URLS = {
    "hdfc_mid_cap": "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
    "hdfc_small_cap": "https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth",
    "hdfc_gold_etf_fof": "https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth",
    "hdfc_large_cap": "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth",
    "hdfc_elss": "https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth",
}
```

- Use `requests` with a proper `User-Agent` header
- If JS-rendered content is missing (check for key fields like "Expense Ratio"), fall back to `Playwright` headless browser
- Save raw HTML to `data/raw/<fund_key>.html`
- Record `scraped_at` timestamp per fund (ISO-8601 UTC)

**Implementation note:** Groww pages load fund data via JavaScript. For reliable scraping, use `playwright` with `page.wait_for_selector('[data-testid="expense-ratio"]')` or equivalent before extracting.

### 1.2 Document Parsing (`src/ingestion/scraper.py`)

- [x] Parse HTML with `BeautifulSoup4`; extract fund-specific sections (Expense Ratio, Exit Load, SIP details, Riskometer, Benchmark, NAV, Lock-in period)
- Strip boilerplate (nav bars, footers, ads) using CSS selector targeting
- Output: Clean plain-text per document saved to `data/processed/<fund_key>.txt`

### 1.3 Chunking & Metadata Tagging (`src/ingestion/chunker.py`)

- [x] **Data-driven strategy** — based on analysis of actual `data/processed/` content:

| Fund | Raw Chars | Raw Lines | Key Fields Found |
|---|---|---|---|
| HDFC Mid Cap | 19,251 | 1,116 | 11 / 11 |
| HDFC Small Cap | 19,839 | 1,141 | 11 / 11 |
| HDFC Gold ETF FoF | 16,225 | 799 | 11 / 11 |
| HDFC Large Cap | 17,794 | 988 | 11 / 11 |
| HDFC ELSS | 18,484 | 1,051 | 11 / 11 |

**Chunking strategy benchmarked (all 5 funds):**

| Strategy | Chunks/fund | Avg len | Min len | Verdict |
|---|---|---|---|---|
| `size=256, overlap=32` | 75–90 | 230 | 36 | ❌ Too small — single lines, no context |
| `size=512, overlap=64` *(original)* | 38–50 | 478 | 270 | ⚠️ Acceptable but noisy boilerplate chunks |
| `size=512, overlap=128` | 41–52 | 491 | 141 | ⚠️ Better continuity but still too many chunks |
| **`size=800, overlap=100`** *(selected)* | **23–29** | **766** | **486** | **✅ Best — dense, meaningful, no orphan chunks** |
| `size=1024, overlap=128` | 19–23 | 972 | 302 | ⚠️ Too large — dilutes specificity of retrieval |

**Selected configuration:**

```python
RecursiveCharacterTextSplitter(
    chunk_size=800,       # balances context richness vs. retrieval precision
    chunk_overlap=100,    # ~12.5% overlap ensures fact continuity across boundaries
    separators=["\n\n", "\n", ". ", " ", ""],
)
```

**Rationale:**
- Groww pages are 16K–20K characters of HTML-extracted text with many short navigation lines — larger chunks (800) help absorb noisy lines without losing semantic integrity
- `overlap=100` (~12.5%) ensures key facts split across boundaries (e.g. "Exit Load: 1%\nif redeemed within 1 year") stay co-located in at least one chunk
- Min chunk length of 486 chars at `size=800` eliminates orphan/stub chunks that hurt retrieval precision
- Produces **23–29 high-quality chunks per fund** (115–145 total), a manageable index size for ChromaDB cosine search

**Metadata attached to every chunk:**
```python
{
    "source_url": "https://groww.in/mutual-funds/...",
    "fund_name": "HDFC Mid Cap Opportunities Fund",
    "fund_key": "hdfc_mid_cap",
    "category": "Mid Cap",
    "scraped_at": "2024-01-15T10:30:00Z",
    "chunk_index": 0,       # position within document
    "content_hash": "sha256...",  # for deduplication
}
```
- Save chunks as `data/processed/<fund_key>_chunks.json`

### 1.4 Embedding & Vector Store (`src/ingestion/embedder.py`)

- [x] Load embedding model: `sentence-transformers/all-MiniLM-L6-v2`
- Initialise ChromaDB with `persist_directory=./vectorstore`, `collection_name="mutual_funds"`
- For each chunk: generate embedding, upsert to ChromaDB with metadata
- Add deduplication: skip chunks with matching `source_url` + content hash if already indexed

**Deliverable:** ✅ `src/ingestion/scraper.py`, `chunker.py`, `embedder.py` implemented. `run_ingestion.py` entrypoint created. 19/19 unit tests passing.

---

## Phase 2 — Query Processing Layer

**Goal:** Implement PII scrubbing, intent classification, and refusal handling.

**Duration:** ~0.5 day

### 2.1 PII Scrubber (`src/validation/pii_scrubber.py`)

Implement regex-based detection and redaction for:

| PII Type | Regex Pattern |
|---|---|
| PAN Number | `[A-Z]{5}[0-9]{4}[A-Z]` |
| Aadhaar | `[2-9]{1}[0-9]{11}` |
| Phone | `(\+91)?[6-9]\d{9}` |
| Email | `[\w\.-]+@[\w\.-]+\.\w+` |
| OTP | `\b[0-9]{4,8}\b` (contextual) |

- `scrub_pii(text: str) -> str` — replaces all matches with `[REDACTED]`
- Apply both to **incoming query** and **outgoing response**

### 2.2 Intent Classifier (`src/query/intent_classifier.py`)

- Rule-based primary classifier using keyword lists:
  - `ADVISORY_KEYWORDS`: `["should i invest", "which fund is better", "recommend", "best fund", "should i buy", "which is good", "should i sell", "future return", "will it grow"]`
  - `FACTUAL_KEYWORDS`: `["expense ratio", "exit load", "minimum sip", "lock-in", "benchmark", "riskometer", "nav", "elss", "aum", "fund manager", "category", "returns factsheet"]`
- `classify_intent(query: str) -> Literal["FACTUAL", "ADVISORY", "UNKNOWN"]`
- Unknown queries default to `FACTUAL` (LLM will gracefully say "not found")

### 2.3 Refusal Handler (`src/query/refusal_handler.py`)

- `get_refusal_response(query: str) -> dict` returns:
  ```python
  {
      "answer": "I'm sorry, this assistant provides facts-only information about mutual fund schemes and cannot offer investment advice or recommendations.",
      "citation": "https://www.amfiindia.com/investor-corner/knowledge-center",
      "footer": "Facts-only. No investment advice. | Last updated from sources: N/A"
  }
  ```

**Deliverable:** PII scrubber, intent classifier, and refusal handler with unit tests.

---

## Phase 3 — Retrieval Layer

**Goal:** Implement semantic retrieval with MMR re-ranking.

**Duration:** ~0.5 day

### 3.1 Query Intent & Metadata Pre-filtering (`src/retrieval/retriever.py`)

- **Data Insight:** 30% of chunks contain navigation boilerplate, and portfolio data spans up to 17 chunks per fund. 
- Implement a lightweight regex/keyword extractor to identify if the query targets a specific fund (e.g., "mid cap", "small cap", "elss").
- If a specific fund is detected, create a metadata filter: `{"fund_key": "hdfc_mid_cap"}`. This eliminates 80% of cross-fund noise before semantic search even begins.

### 3.2 Vector Retriever with MMR (`src/retrieval/retriever.py`)

- Load ChromaDB collection (`mutual_funds`).
- `retrieve(query: str, filter_dict: dict = None) -> List[Document]`
  - Embed query using the ingestion embedding model.
  - **Fetch large (`fetch_k=20`)**: Cast a wide net to ensure we bypass boilerplate and capture scattered facts (like portfolio sectors).
  - **Maximal Marginal Relevance (MMR)**: Select the top-5 diverse chunks from the 20 candidates.
    - `lambda_mult` = 0.5 (balances exact semantic match with diversity).
  - Return: list of 5 `(chunk_text, metadata)` tuples.

### 3.3 Context Builder (`src/retrieval/context_builder.py`)

- Concatenate the 5 chunks into a single context string, grouped by source:
  ```
  [Source: HDFC Mid Cap Fund | https://groww.in/...]
  <chunk text>
  
  [Source: HDFC Mid Cap Fund | https://groww.in/...]
  <chunk text>
  ```
- Return: `context: str`, `primary_source_url: str` (from highest-ranked chunk), `scraped_at: str`

**Deliverable:** End-to-end retrieval returning top-5 diverse chunks, with optional fund metadata pre-filtering.

---

## Phase 4 — Generation Layer (Groq LLM)

**Goal:** Integrate Groq API for facts-only answer generation.

**Duration:** ~0.5 day

### 4.1 Groq Client (`src/generation/groq_client.py`)

```python
from groq import Groq
import os

_client = Groq(api_key=os.environ["GROQ_API_KEY"])

def call_groq(system_prompt: str, context: str, question: str) -> str:
    try:
        response = _client.chat.completions.create(
            model=os.environ.get("GROQ_MODEL", "qwen/qwen3.8-27b"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}
            ],
            max_tokens=256,
            temperature=0.0,
            top_p=1.0,
        )
        return response.choices[0].message.content
    except Exception as e:
        # Fallback to mixtral
        response = _client.chat.completions.create(
            model=os.environ.get("GROQ_FALLBACK_MODEL", "openai/gpt-oss-20b"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}
            ],
            max_tokens=256,
            temperature=0.0,
        )
        return response.choices[0].message.content
```

### 4.2 Prompt Builder (`src/generation/prompt_builder.py`)

- `build_system_prompt() -> str` — returns the static system prompt from Architecture §3.4
- `build_user_message(context: str, question: str) -> str` — formats context + question

**Deliverable:** Groq client with retry/fallback; prompt builder; integration test passing.

---

## Phase 5 — Response Validation Layer

**Goal:** Enforce all output constraints post-generation.

**Duration:** ~0.5 day

### 5.1 Response Validator (`src/validation/response_validator.py`)

Implement `validate_response(raw: str, source_url: str, scraped_at: str) -> dict`:

1. **Sentence Limiter** — Split on `.`, `!`, `?`; truncate to first 3 non-empty sentences.
2. **Source Injector** — If no URL in `raw`, append `source_url`.
3. **Advisory Phrase Checker** — Scan for: `["i recommend", "you should", "i suggest", "best choice", "better option"]`; if found, replace entire answer with safe refusal.
4. **PII Scrubber** — Re-run `scrub_pii()` on the final answer text.
5. **Footer Appender** — Append: `"\n\n---\nLast updated from sources: {scraped_at}"`.

Return:
```python
{
    "answer": "...",          # Validated ≤3-sentence answer
    "citation": "...",        # Exactly 1 source URL
    "footer": "Last updated from sources: 2024-01-15"
}
```

**Deliverable:** Validator passing all constraint tests; 100% test coverage for edge cases.

---

## Phase 6 — End-to-End Pipeline Integration

**Goal:** Wire all layers into a single `answer_query()` function.

**Duration:** ~0.5 day

### Pipeline Orchestrator (`src/pipeline.py`)

```python
def answer_query(user_query: str) -> dict:
    # Step 1: PII scrub
    clean_query = scrub_pii(user_query)
    
    # Step 2: Intent classification
    intent = classify_intent(clean_query)
    if intent == "ADVISORY":
        return get_refusal_response(clean_query)
    
    # Step 3: Retrieval
    chunks = retrieve(clean_query, k=5)
    reranked = mmr_rerank(chunks, k=3)
    context, source_url, scraped_at = build_context(reranked)
    
    # Step 4: Generation (Groq)
    system_prompt = build_system_prompt()
    raw_answer = call_groq(system_prompt, context, clean_query)
    
    # Step 5: Validation
    result = validate_response(raw_answer, source_url, scraped_at)
    return result
```

- Integration test: run 10 golden factual queries end-to-end; assert all constraints pass.

**Deliverable:** `answer_query()` orchestrator; passing integration tests.

---

## Phase 7 — User Interface (Streamlit)

**Goal:** Build the minimal, compliant UI.

**Duration:** ~0.5–1 day

### Streamlit App (`src/app.py`)

**UI Components:**

1. **Page config:**
   ```python
   st.set_page_config(
       page_title="Mutual Fund FAQ Assistant",
       page_icon="📊",
       layout="centered"
   )
   ```

2. **Welcome section:**
   - Title: "📊 Mutual Fund FAQ Assistant"
   - Subtitle: "Facts-only answers about HDFC mutual fund schemes."
   - Disclaimer badge: "⚠️ Facts-only. No investment advice."

3. **Example question buttons (3 clickable chips):**
   - "What is the expense ratio of HDFC Mid Cap Fund?"
   - "What is the ELSS lock-in period?"
   - "What is the exit load for HDFC Small Cap Fund?"

4. **Chat input:** `st.chat_input("Ask a factual question about mutual funds...")`

5. **Response display:**
   - Answer text
   - Citation link: `[View Source](<url>)`
   - Footer: `Last updated from sources: <date>`

6. **Session state:** Maintain chat history for the current session (not persisted).

**Deliverable:** Working Streamlit app; all 3 example questions return valid responses.

---

## Phase 8 — Testing & Quality Assurance

**Goal:** Validate all layers, constraints, and edge cases.

**Duration:** ~1 day

### 8.1 Unit Tests (`tests/`)

| Test File | Scope |
|---|---|
| `test_ingestion.py` | Scraping, parsing, chunking, embedding |
| `test_retrieval.py` | Vector search, MMR re-rank, context builder |
| `test_generation.py` | Groq client (mocked), prompt builder |
| `test_validation.py` | Sentence limiter, source injector, PII scrubber, advisory checker |
| `test_pipeline.py` | End-to-end golden test set (10 factual + 5 advisory queries) |

### 8.2 Golden Test Set (Manual + Automated)

**Factual Queries (must return answer ≤ 3 sentences, 1 citation, footer):**
1. What is the expense ratio of HDFC Mid Cap Fund?
2. What is the minimum SIP amount for HDFC Small Cap Fund?
3. What is the exit load for HDFC ELSS Tax Saver Fund?
4. What is the ELSS lock-in period?
5. What benchmark index does HDFC Large Cap Fund track?
6. What is the riskometer classification of HDFC Gold ETF FoF?
7. How do I download a capital gains statement?
8. What is the AUM of HDFC Mid Cap Fund?
9. Who manages the HDFC Small Cap Fund?
10. What is the fund category of HDFC Gold ETF FoF?

**Advisory Queries (must return refusal, no LLM call):**
1. Should I invest in HDFC Mid Cap Fund?
2. Which HDFC fund is better for me?
3. Recommend a fund for tax saving.
4. Will HDFC Mid Cap Fund give good returns?
5. Is ELSS better than FD?

### 8.3 Constraint Checklist

- [ ] All factual responses ≤ 3 sentences
- [ ] All factual responses include exactly 1 citation URL
- [ ] All factual responses include footer with `scraped_at` date
- [ ] All advisory queries return refusal without LLM call
- [ ] Refusal responses include AMFI/SEBI educational link
- [ ] No PII present in any output
- [ ] Groq fallback model activates on primary model failure

**Deliverable:** All tests passing; constraint checklist 100% compliant.

---

## Phase 9 — Documentation & README

**Goal:** Complete all project documentation.

**Duration:** ~0.5 day

### README.md Contents

- Project overview and disclaimer
- Setup instructions (clone → pip install → `.env` → run ingestion → run app)
- Selected AMC and schemes table
- Architecture overview (link to `docs/Architecture.md`)
- Known limitations
- "Facts-only. No investment advice." disclaimer snippet

**Deliverable:** Complete README; all docs/ files in place.

---

## Summary Timeline

| Phase | Description | Duration |
|---|---|---|
| Phase 0 | Project setup & environment | 0.5 day |
| Phase 1 | Data ingestion pipeline | 1–1.5 days |
| Phase 2 | Query processing layer | 0.5 day |
| Phase 3 | Retrieval layer | 0.5 day |
| Phase 4 | Generation layer (Groq) | 0.5 day |
| Phase 5 | Response validation layer | 0.5 day |
| Phase 6 | End-to-end pipeline integration | 0.5 day |
| Phase 7 | Streamlit UI | 0.5–1 day |
| Phase 8 | Testing & QA | 1 day |
| Phase 9 | Documentation | 0.5 day |
| **Total** | | **~6–7 days** |

---

## Dependencies & Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Groww pages are JS-rendered | High | Use Playwright headless browser as primary scraper |
| AMC PDF factsheet layout changes | Medium | Log parse errors; alert and manual review |
| Groq API rate limit (free tier) | Medium | Implement exponential backoff; fallback to mixtral |
| ChromaDB version incompatibility | Low | Pin versions in `requirements.txt` |
| Model hallucinates despite constraints | Low | temperature=0.0 + post-gen advisory checker |

# Edge Cases: Mutual Fund FAQ Assistant

This document catalogues all known edge cases across every layer of the RAG pipeline, along with expected system behaviour and mitigation strategies.

---

## 1. Query Layer Edge Cases

### 1.1 Advisory Query Disguised as Factual

| # | Example | Risk | Expected Behaviour |
|---|---|---|---|
| EC-Q-01 | "What is the best expense ratio?" | "Best" implies comparison/recommendation | Classifier must detect "best" → `ADVISORY` refusal |
| EC-Q-02 | "Which fund has the lowest exit load?" | Comparative query for decision-making | Detect comparatives ("lowest", "highest", "which") → `ADVISORY` refusal |
| EC-Q-03 | "Is HDFC Mid Cap a good fund?" | Opinion request | Detect "good", "bad", "worth it" → `ADVISORY` refusal |
| EC-Q-04 | "Tell me the expense ratio so I can decide which fund to buy" | Factual framing, advisory intent | Detect "decide", "which to buy" in same query → `ADVISORY` |
| EC-Q-05 | "What returns can I expect from HDFC ELSS?" | Future return speculation | Detect "expect", "future", "will I get" → `ADVISORY` refusal |

**Mitigation:** Expand `ADVISORY_KEYWORDS` to include comparative adjectives, future-tense return queries, and decision verbs. Apply phrase-level matching, not just single-word.

---

### 1.2 PII-Embedded Queries

| # | Example | Risk | Expected Behaviour |
|---|---|---|---|
| EC-Q-06 | "My PAN is ABCDE1234F, what is the expense ratio?" | PAN leakage to LLM | Scrub PAN → `ABCDE1234F` replaced with `[REDACTED]` before processing |
| EC-Q-07 | "OTP is 482910, how do I download my statement?" | OTP leakage | Scrub numeric OTP pattern → `[REDACTED]` |
| EC-Q-08 | "My email is user@example.com — what is the exit load?" | Email leakage | Scrub email → `[REDACTED]` |
| EC-Q-09 | "Account 1234567890 — what is the lock-in for ELSS?" | Account number leakage | Detect and scrub 10-digit account number → `[REDACTED]` |

**Mitigation:** PII scrubber runs on raw query before any downstream processing. Scrubbed query is what gets embedded and sent to Groq.

---

### 1.3 Empty / Gibberish / Non-English Queries

| # | Example | Risk | Expected Behaviour |
|---|---|---|---|
| EC-Q-10 | `""` (empty string) | Crash or empty embed | Validate query length > 3 chars; return "Please enter a question." |
| EC-Q-11 | `"asdfjkl qwerty"` | Retrieval returns irrelevant chunks | LLM will respond "I could not find this information in the official sources." |
| EC-Q-12 | `"मुझे HDFC फंड के बारे में बताएं"` (Hindi) | Non-English query | Return English-only notice: "This assistant currently supports English queries only." |
| EC-Q-13 | `"!!!! @@@ ###"` | Special characters only | Length/character filter; return "Please enter a valid question." |
| EC-Q-14 | Very long query (> 1000 chars) | Token overflow to Groq | Truncate query to 500 characters before embedding; log warning |

---

### 1.4 Ambiguous Fund References

| # | Example | Risk | Expected Behaviour |
|---|---|---|---|
| EC-Q-15 | "What is the expense ratio of the mid cap fund?" | No AMC specified; could be any mid cap | Retrieve from corpus; response will mention HDFC specifically from context |
| EC-Q-16 | "What is the exit load of the ELSS fund?" | Could refer to non-HDFC ELSS funds | Retriever will return HDFC ELSS chunks (only fund in corpus); answer clearly states "HDFC ELSS Tax Saver Fund" |
| EC-Q-17 | "Tell me about the gold fund" | Ambiguous — Gold ETF FoF is niche | Retriever returns HDFC Gold ETF FoF chunks; LLM will answer from context |
| EC-Q-18 | "What is the expense ratio of Axis Mid Cap?" | Fund not in corpus | Retriever finds no matching chunks; LLM returns "not found in official sources" |

---

## 2. Retrieval Layer Edge Cases

### 2.1 No Relevant Chunks Found

| # | Scenario | Risk | Expected Behaviour |
|---|---|---|---|
| EC-R-01 | Query about a fund not in corpus (e.g., SBI Bluechip) | Retriever returns unrelated chunks from score threshold | Implement minimum similarity score threshold (e.g., cosine ≥ 0.4); if none pass, return "not found" without calling Groq |
| EC-R-02 | Query about a very specific detail not scraped (e.g., exact NAV on a date) | Hallucination risk | LLM instructed to say "not found" when context is insufficient |
| EC-R-03 | Empty vectorstore (ingestion not yet run) | ChromaDB query crashes | Catch `CollectionError`; return "Data not yet loaded. Please run the ingestion pipeline." |

### 2.2 Stale / Outdated Data

| # | Scenario | Risk | Expected Behaviour |
|---|---|---|---|
| EC-R-04 | Expense ratio changed after last scrape | Wrong fact returned | Footer displays `scraped_at` date so user knows data currency; prominently warn if data > 30 days old |
| EC-R-05 | Fund merged or discontinued | Outdated chunks in store | Ingestion refresh will upsert new content; old chunks replaced by deduplication logic |

### 2.3 Chunk Overlap / Fragmentation

| # | Scenario | Risk | Expected Behaviour |
|---|---|---|---|
| EC-R-06 | Key fact (expense ratio) split across chunk boundary | Retriever gets incomplete fact | Chunk overlap (64 tokens) ensures most facts are fully contained; MMR re-ranking diversifies to catch both halves |
| EC-R-07 | Multiple chunks from same section retrieved (MMR failure) | Redundant context | MMR diversity parameter (λ=0.5) prevents this; test validated |

---

## 3. Generation Layer Edge Cases (Groq LLM)

### 3.1 Model Compliance Failures

| # | Scenario | Risk | Expected Behaviour |
|---|---|---|---|
| EC-G-01 | Model ignores 3-sentence limit and generates a paragraph | Too much text | Post-gen sentence counter truncates to 3 sentences |
| EC-G-02 | Model makes up a source URL not in context | Hallucinated citation | Post-gen source injector replaces model-generated URL with `source_url` from chunk metadata |
| EC-G-03 | Model generates investment advice despite system prompt | Compliance violation | Post-gen advisory phrase checker detects and replaces with refusal |
| EC-G-04 | Model generates a response in bullet points instead of sentences | Format violation | Sentence counter normalises bullet points to sentences; strips markdown |
| EC-G-05 | Model outputs "I don't know" without official source language | Acceptable but needs standard phrasing | Map any "I don't know" variant to: "I could not find this information in the official sources." |

### 3.2 API / Network Failures

| # | Scenario | Risk | Expected Behaviour |
|---|---|---|---|
| EC-G-06 | Groq API returns HTTP 429 (rate limit) | Request fails | Exponential backoff: retry 3× with 1s, 2s, 4s delays; if still failing, return user-friendly error message |
| EC-G-07 | Groq API returns HTTP 500 (server error) | Request fails | Auto-switch to fallback model `mixtral-8x7b-32768`; log the incident |
| EC-G-08 | Network timeout (> 10s) | App hangs | Set `timeout=10` on Groq client; catch `httpx.TimeoutException`; return "Service temporarily unavailable." |
| EC-G-09 | Groq API key invalid or expired | Auth error | Catch `AuthenticationError`; return "Configuration error. Please contact support." |
| EC-G-10 | Groq token limit exceeded (context too long) | Truncation or error | Limit context to 2000 characters before sending; trim oldest chunks first |

### 3.3 Model Hallucination Scenarios

| # | Scenario | Risk | Expected Behaviour |
|---|---|---|---|
| EC-G-11 | Model states a specific NAV or return % not in context | False financial data | temperature=0.0 + system prompt hard-constraint: "use ONLY provided context"; post-gen numerical fact checker (flag if number not in context) |
| EC-G-12 | Model compares two funds even when only one is queried | Advisory drift | Advisory phrase checker + sentence limiter reduce scope |
| EC-G-13 | Model introduces fictional fund names | Corpus mismatch | Context grounding at temperature=0.0 prevents this in most cases; response validator cross-checks fund names against known corpus |

---

## 4. Response Validation Edge Cases

| # | Scenario | Risk | Expected Behaviour |
|---|---|---|---|
| EC-V-01 | Response contains exactly 3 long compound sentences | Valid but hard to read | Accept; do not split compound sentences; count only terminal punctuation |
| EC-V-02 | Response has no terminal punctuation (no period) | Sentence counter fails | Fall back to character limit (≤ 500 chars); add trailing period |
| EC-V-03 | Source URL in response is a Groww URL vs. AMC URL | Both are official | Accept Groww URLs as they are official product pages in the corpus |
| EC-V-04 | `scraped_at` metadata missing from chunk | Footer cannot be populated | Default to "Date unavailable"; log missing metadata |
| EC-V-05 | Response is empty string from Groq | Empty output | Return standard "not found" message |
| EC-V-06 | Response contains markdown bold/italic (e.g., `**1.5%**`) | Formatting in factual text | Strip markdown before displaying in Streamlit (use `re.sub(r'\*+', '', text)`) |

---

## 5. UI Layer Edge Cases

| # | Scenario | Risk | Expected Behaviour |
|---|---|---|---|
| EC-U-01 | User clicks example question button multiple times | Duplicate requests | Debounce or disable button while request is in-flight |
| EC-U-02 | User submits query while previous response is loading | Race condition | Queue requests; show spinner; process sequentially |
| EC-U-03 | User pastes a very long query (> 2000 chars) | Token overflow | UI enforces `maxlength` on input; display "Query too long" error |
| EC-U-04 | Citation URL is broken / 404 | Bad user experience | No link validation at response time (would add latency); note in disclaimer that links are from ingestion time |
| EC-U-05 | Mobile/small screen rendering of long responses | Layout overflow | Streamlit's responsive layout handles this; test on 375px viewport |

---

## 6. Data Ingestion Edge Cases

| # | Scenario | Risk | Expected Behaviour |
|---|---|---|---|
| EC-I-01 | Groww page returns 403 Forbidden | Scraping blocked | Rotate User-Agent; add retry with delay; use Playwright if requests fails |
| EC-I-02 | AMC PDF factsheet URL changes | Scraper 404s | Log broken URL; skip and alert; maintain fallback PDF URL list |
| EC-I-03 | ChromaDB index corruption | Retrieval fails | Implement index rebuild script; detect corruption on startup; re-ingest if needed |
| EC-I-04 | Partial ingestion (3 of 5 funds indexed) | Incomplete corpus | Atomic ingestion: only commit to ChromaDB after all chunks embedded successfully |
| EC-I-05 | Duplicate scrape of same fund (re-run) | Double-indexed chunks | Deduplication via content hash check before upsert |
| EC-I-06 | PDF factsheet contains scanned images (no text) | Empty parsed content | Detect empty extraction; log warning; skip PDF; rely on HTML source |

---

## 7. Compliance & Security Edge Cases

| # | Scenario | Risk | Expected Behaviour |
|---|---|---|---|
| EC-C-01 | User asks for return history to make investment decision | Borderline factual/advisory | Detect "return history", "past performance"; respond with factsheet link only: "Please refer to the official factsheet for historical performance data." |
| EC-C-02 | User asks for "top performing fund" | Clearly advisory | `ADVISORY` classification → refusal + AMFI link |
| EC-C-03 | User provides Aadhaar number in query | PII in query | Scrub → `[REDACTED]`; never log raw query |
| EC-C-04 | LLM response accidentally includes PAN-like pattern | PII in output | Post-gen PII scrubber redacts before display |
| EC-C-05 | User attempts prompt injection ("Ignore previous instructions and...") | System prompt override | temperature=0.0 + strict system prompt; validate response against advisory/off-topic checkers |

---

## Edge Case Priority Matrix

| Priority | Edge Cases | Action |
|---|---|---|
| 🔴 Critical | EC-Q-01–05 (advisory masking), EC-G-03 (advice generation), EC-C-01–05 (compliance) | Block release until resolved |
| 🟠 High | EC-Q-06–09 (PII), EC-G-06–09 (API failures), EC-R-01 (no chunks) | Resolve before release |
| 🟡 Medium | EC-Q-10–14 (empty/gibberish), EC-R-04–05 (stale data), EC-G-11–13 (hallucination) | Resolve in Phase 8 QA |
| 🟢 Low | EC-U-01–05 (UI), EC-I-01–06 (ingestion), EC-V-01–06 (formatting) | Resolve as discovered |

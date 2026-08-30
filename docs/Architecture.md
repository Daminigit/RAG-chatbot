# Architecture: Mutual Fund FAQ Assistant (Facts-Only RAG Chatbot)

## 1. Overview

The Mutual Fund FAQ Assistant is a **Retrieval-Augmented Generation (RAG)** system built to deliver strict, facts-only answers about mutual fund schemes. It grounds every response in a curated corpus of **5 official Groww mutual fund pages** (HDFC fund scheme listings) and uses **Groq** as the inference engine for ultra-low-latency language model completions. The system is designed for compliance-first operation — no investment advice, no opinions, no hallucinations.

---

## 2. High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         User Interface Layer                        │
│   (Streamlit / HTML+JS)  ─  Welcome Banner, Example Qs, Disclaimer │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │ User Query
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Query Processing Layer                       │
│  ┌──────────────────┐   ┌────────────────────┐  ┌───────────────┐  │
│  │ Query Classifier │──▶│ Intent Guard       │  │ Query Cleaner │  │
│  │ (factual vs.     │   │ (advisory refusal) │  │ (normalise)   │  │
│  │  advisory)       │   └────────────────────┘  └───────────────┘  │
│  └──────────────────┘                                              │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │ Clean Factual Query
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       Retrieval Layer (RAG Core)                    │
│  ┌─────────────────┐   ┌──────────────────┐   ┌─────────────────┐  │
│  │ Embedding Model │──▶│ Vector Store     │──▶│ Chunk Ranker    │  │
│  │ (sentence-      │   │ (ChromaDB /      │   │ (cosine sim. +  │  │
│  │  transformers)  │   │  FAISS)          │   │  MMR re-rank)   │  │
│  └─────────────────┘   └──────────────────┘   └─────────────────┘  │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │ Top-K Chunks + Source Metadata
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Generation Layer (Groq LLM)                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Prompt Builder  →  Groq API (llama3-8b / mixtral-8x7b)     │   │
│  │  System Prompt: "facts-only, 3-sentence limit, cite source" │   │
│  └──────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │ Raw LLM Response
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Response Validation Layer                      │
│  ┌────────────────────┐  ┌──────────────────┐  ┌────────────────┐  │
│  │ Sentence Counter   │  │ Source Injector  │  │ Footer Appender│  │
│  │ (≤ 3 sentences)    │  │ (exactly 1 link) │  │ "Last updated" │  │
│  └────────────────────┘  └──────────────────┘  └────────────────┘  │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │ Final Validated Response
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         User Interface Layer                        │
│            Displays answer + citation + last-updated footer         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Component Breakdown

### 3.1 Data Ingestion Pipeline (Offline / Batch)

| Sub-component | Description |
|---|---|
| **Source Scraper** | Fetches HTML content exclusively from the **5 official Groww fund pages** listed in the corpus below using `requests` + `BeautifulSoup`. |
| **Document Parser** | Normalises Groww HTML into plain text. Targets fund-specific fields (Expense Ratio, Exit Load, SIP, Riskometer, Benchmark, NAV). Strips nav bars, ads, and boilerplate. |
| **Chunker** | Splits cleaned text into overlapping chunks (**800 chars, 100-char overlap**) using LangChain's `RecursiveCharacterTextSplitter`. Benchmarked on all 5 fund pages — produces 23–29 dense chunks per fund with min length ~486 chars. |
| **Metadata Tagger** | Attaches metadata to each chunk: `source_url` (Groww URL), `fund_name`, `category`, `scraped_at` date. |
| **Embedding Generator** | Converts chunks to dense vectors using `sentence-transformers/all-MiniLM-L6-v2`. |
| **Vector Store Writer** | Upserts embeddings + metadata into **ChromaDB** (local, persistent). |

**Corpus — Sole Data Source (Groww URLs only):**

> [!IMPORTANT]
> The corpus is built **exclusively** from the following 5 Groww fund pages. No AMC PDFs, no AMFI portal, no third-party sources are ingested.

| Fund Name | Category | Source URL (Groww) |
|---|---|---|
| HDFC Mid Cap Opportunities Fund | Mid Cap | https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth |
| HDFC Small Cap Fund | Small Cap | https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth |
| HDFC Gold ETF Fund of Fund | Gold/Commodity | https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth |
| HDFC Large and Mid Cap Fund | Large Cap | https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth |
| HDFC ELSS Tax Saver Fund | ELSS / Tax Saving | https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth |

---

### 3.2 Query Processing Layer (Online / Real-time)

| Sub-component | Description |
|---|---|
| **Query Cleaner** | Strips PII patterns (PAN, Aadhaar, phone, email, OTP), lowercases, and normalises whitespace. |
| **Intent Classifier** | Lightweight rule-based + keyword classifier that tags a query as `FACTUAL` or `ADVISORY`. Advisory queries are short-circuited to the Refusal Handler. |
| **Refusal Handler** | Returns a polite, templated refusal with a relevant AMFI/SEBI educational link. Never calls the LLM for advisory queries. |

**Intent Classification Rules (examples):**

| Trigger Keywords / Patterns | Intent |
|---|---|
| "should I invest", "which is better", "recommend", "good fund", "buy", "sell" | `ADVISORY` |
| "expense ratio", "exit load", "minimum SIP", "lock-in", "benchmark", "riskometer", "NAV", "ELSS" | `FACTUAL` |

---

### 3.3 Retrieval Layer

| Sub-component | Description |
|---|---|
| **Query Embedder** | Encodes the cleaned query using the same embedding model used during ingestion (symmetric retrieval). |
| **Vector Search** | Retrieves top-K (K=5) most semantically similar chunks from ChromaDB/FAISS via cosine similarity. |
| **MMR Re-ranker** | Applies Maximal Marginal Relevance to diversify retrieved chunks and avoid redundancy. |
| **Context Builder** | Concatenates top-3 re-ranked chunks into a single context block for the prompt, including source metadata. |

---

### 3.4 Generation Layer — Groq LLM

The LLM inference is handled by the **Groq Cloud API**, which delivers sub-500ms response times via its LPU (Language Processing Unit) hardware.

| Parameter | Value |
|---|---|
| **LLM Provider** | Groq Cloud API |
| **Primary Model** | `qwen/qwen3.8-27b` |
| **Fallback Model** | `openai/gpt-oss-20b` |
| **Max Output Tokens** | 256 |
| **Temperature** | 0.0 (deterministic; eliminates creative hallucination) |
| **Top-P** | 1.0 |
| **API Integration** | `groq` Python SDK / OpenAI-compatible REST endpoint |

**System Prompt Template:**

```
You are a facts-only mutual fund information assistant. Your sole purpose is to
answer objective, verifiable questions about mutual fund schemes using only the
provided context. Follow these rules strictly:

1. Answer in a maximum of 3 sentences.
2. Use only information present in the provided context. Do not infer, speculate,
   or add external knowledge.
3. Do not provide investment advice, recommendations, or performance comparisons.
4. End your answer with the exact source URL from the context metadata.
5. If the context does not contain enough information to answer, say:
   "I could not find this information in the official sources."

Context:
{context}

Question: {question}
Answer:
```

---

### 3.5 Response Validation Layer

| Validator | Rule | Action on Failure |
|---|---|---|
| **Sentence Counter** | Response ≤ 3 sentences | Truncate to 3 sentences |
| **Source Injector** | Exactly 1 citation URL present | Inject `source_url` from chunk metadata if missing |
| **Advisory Content Checker** | Flags phrases like "I recommend", "you should" | Replace flagged response with safe refusal message |
| **PII Scrubber** | Scans output for PAN/Aadhaar/phone patterns | Redacts any detected PII |
| **Footer Appender** | Appends `"Last updated from sources: <scraped_at>"` | Always appended from chunk metadata |

---

### 3.6 User Interface Layer

A minimal, responsive UI built with **Streamlit**.

| UI Element | Details |
|---|---|
| **Welcome Banner** | "Mutual Fund FAQ Assistant — Facts Only. No Investment Advice." |
| **Example Questions** | 3 pre-loaded buttons: "What is the expense ratio of HDFC Mid Cap Fund?", "What is the ELSS lock-in period?", "What is the exit load for HDFC Small Cap Fund?" |
| **Disclaimer** | Persistent footer: "Facts-only. No investment advice." |
| **Chat Input** | Single-line text box for free-form queries |
| **Response Area** | Displays answer, citation link (clickable), and last-updated footer |

---

## 4. Data Flow Summary

```
[User Query]
     │
     ▼
[PII Scrub + Normalise]
     │
     ▼
[Intent Classification]──(ADVISORY)──▶[Refusal Response + AMFI Link]
     │
  (FACTUAL)
     │
     ▼
[Query Embedding]
     │
     ▼
[Vector Search → Top-K Chunks]
     │
     ▼
[MMR Re-rank → Top-3 Chunks]
     │
     ▼
[Prompt Build: System + Context + Question]
     │
     ▼
[Groq API Call (llama3-8b, temp=0.0)]
     │
     ▼
[Response Validation: sentence count, source, PII, advisory check]
     │
     ▼
[Append Footer: "Last updated from sources: <date>"]
     │
     ▼
[Return Final Response to UI]
```

---

## 5. Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| LLM Inference | **Groq Cloud API** (`qwen/qwen3.8-27b`) | Sub-500ms latency via LPU; free tier available; OpenAI-compatible |
| Embedding Model | `sentence-transformers/all-MiniLM-L6-v2` | Lightweight, fast, strong semantic similarity |
| Vector Store | **ChromaDB** (local, persistent) | Zero-infrastructure; easy metadata filtering |
| Document Parsing | `BeautifulSoup4` | Reliable HTML parsing for Groww fund pages |
| Chunking / Orchestration | **LangChain** | Standardised RAG pipeline primitives |
| Web Scraping | `requests`, `Playwright` | `requests` for static pages; `Playwright` fallback for JS-rendered Groww content |
| UI | **Streamlit** | Rapid prototyping; Python-native |
| Language | **Python 3.11+** | Ecosystem compatibility |
| Environment | `python-dotenv` | Secure API key management |

---

## 6. Security & Privacy Design

| Concern | Mitigation |
|---|---|
| PII in user queries | Regex scrubber strips PAN, Aadhaar, phone, email, OTP before processing |
| PII in LLM output | Post-generation scrubber validates the response before display |
| API key exposure | Keys in `.env`; never committed; `.gitignore` enforced |
| Advisory content generation | Temperature = 0.0; system prompt hard-constrains the model; post-gen advisory checker |
| Data storage | No user queries, sessions, or PII persisted to disk |
| Source integrity | Corpus built exclusively from official URLs |

---

## 7. Corpus Refresh Strategy

| Trigger | Action |
|---|---|
| **Manual refresh** | Re-run ingestion pipeline; re-scrape all 5 Groww URLs; rebuild vector index |
| **Scheduled** | Weekly cron job re-scrapes Groww pages (fund data such as NAV and expense ratios updates regularly) |
| **Metadata freshness** | Each chunk stores `scraped_at` timestamp; footer always reflects the actual data date |

---

## 8. Known Limitations

1. **Static corpus** — NAV, expense ratios, and exit loads change frequently on Groww; data may be stale between re-scrapes.
2. **Groww JS rendering** — Groww pages load fund data via JavaScript; `requests` alone may miss some fields; `Playwright` headless browser is used as fallback.
3. **No multi-turn memory** — Each query is answered independently; no conversational context is maintained.
4. **No Hindi/regional language support** — English only.
5. **Groww page layout changes** — If Groww restructures its fund pages, HTML selectors in the scraper will need updating.
6. **Groq rate limits** — Free-tier Groq API has token-per-minute limits; heavy traffic may hit throttling.

---

## 9. Directory Structure

```
RAG-chatbot/
├── docs/
│   ├── Architecture.md
│   ├── implementation-plan.md
│   ├── edge-cases.md
│   └── eval.md
├── data/
│   ├── raw/                     ← Scraped HTML / PDF files
│   └── processed/               ← Cleaned plain-text chunks (JSON)
├── vectorstore/                 ← ChromaDB persistent directory
├── src/
│   ├── ingestion/
│   │   ├── scraper.py
│   │   ├── chunker.py
│   │   └── embedder.py
│   ├── retrieval/
│   │   ├── retriever.py
│   │   └── context_builder.py
│   ├── generation/
│   │   ├── groq_client.py
│   │   └── prompt_builder.py
│   ├── validation/
│   │   ├── response_validator.py
│   │   └── pii_scrubber.py
│   ├── query/
│   │   ├── intent_classifier.py
│   │   └── refusal_handler.py
│   └── app.py                   ← Streamlit entrypoint
├── tests/
│   ├── test_ingestion.py
│   ├── test_retrieval.py
│   ├── test_generation.py
│   └── test_validation.py
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 10. Groq API Integration Details

```python
# src/generation/groq_client.py
from groq import Groq
import os

client = Groq(api_key=os.environ["GROQ_API_KEY"])

def call_groq(system_prompt: str, context: str, question: str) -> str:
    response = client.chat.completions.create(
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
```

**Environment Variables (`.env.example`):**

```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=qwen/qwen3.8-27b
GROQ_FALLBACK_MODEL=openai/gpt-oss-20b
CHROMA_PERSIST_DIR=./vectorstore
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

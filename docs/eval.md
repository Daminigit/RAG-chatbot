# Evaluation Plan: Mutual Fund FAQ Assistant

This document defines the evaluation framework for the RAG chatbot — covering retrieval quality, generation quality, constraint compliance, and system reliability.

---

## 1. Evaluation Philosophy

The assistant is evaluated on **four pillars**:

| Pillar | What It Measures |
|---|---|
| **Retrieval Quality** | Are the right chunks being retrieved for each query? |
| **Generation Quality** | Is the generated answer accurate, grounded, and concise? |
| **Constraint Compliance** | Does every response meet the format and policy rules? |
| **System Reliability** | Does the system handle failures, edge cases, and load gracefully? |

---

## 2. Evaluation Dataset

### 2.1 Golden Dataset — Factual Queries

A curated set of 25 factual queries with ground-truth expected answers, verified against official sources.

| ID | Query | Expected Answer (Ground Truth) | Source |
|---|---|---|---|
| F-01 | What is the expense ratio of HDFC Mid Cap Opportunities Fund? | ~1.56% (Direct Plan) | Groww / AMC factsheet |
| F-02 | What is the minimum SIP amount for HDFC Small Cap Fund? | ₹100/month | Groww fund page |
| F-03 | What is the exit load for HDFC ELSS Tax Saver Fund? | Nil (ELSS lock-in applies) | Groww / AMC |
| F-04 | What is the ELSS lock-in period? | 3 years | SEBI regulation |
| F-05 | What benchmark index does HDFC Large and Mid Cap Fund track? | NIFTY Large Midcap 250 TRI | AMC factsheet |
| F-06 | What is the riskometer classification of HDFC Gold ETF FoF? | Very High Risk | AMC factsheet |
| F-07 | How do I download a capital gains statement from Groww? | Official process description | Groww help docs |
| F-08 | What is the AUM of HDFC Mid Cap Fund? | ~₹70,000+ Cr (updated regularly) | AMC / AMFI |
| F-09 | Who is the fund manager of HDFC Small Cap Fund? | Chirag Setalvad | AMC factsheet |
| F-10 | What is the fund category of HDFC Gold ETF FoF? | Fund of Fund (Gold) | SEBI category |
| F-11 | What is the exit load for HDFC Mid Cap Fund? | 1% if redeemed within 1 year | Groww / AMC |
| F-12 | What is the minimum lump sum investment in HDFC ELSS? | ₹500 | Groww fund page |
| F-13 | What is the NAV of HDFC Large and Mid Cap Fund? | Dynamic (as of data date) | Groww / AMFI |
| F-14 | What is the benchmark for HDFC Small Cap Fund? | NIFTY Smallcap 250 TRI | AMC factsheet |
| F-15 | What is the expense ratio of HDFC Gold ETF FoF? | ~0.18% | AMC factsheet |

### 2.2 Golden Dataset — Advisory Queries (Must Refuse)

| ID | Query | Expected Behaviour |
|---|---|---|
| A-01 | Should I invest in HDFC Mid Cap Fund? | Polite refusal + AMFI link |
| A-02 | Which HDFC fund is better for long-term? | Polite refusal + AMFI link |
| A-03 | Recommend a tax-saving mutual fund | Polite refusal + AMFI link |
| A-04 | Will HDFC Small Cap Fund give 20% returns? | Polite refusal + AMFI link |
| A-05 | Is ELSS better than PPF for tax saving? | Polite refusal + AMFI link |
| A-06 | Which is the best mutual fund right now? | Polite refusal + AMFI link |
| A-07 | Should I do SIP or lump sum? | Polite refusal + AMFI link |
| A-08 | What should be my portfolio allocation? | Polite refusal + AMFI link |
| A-09 | Is HDFC Large Cap a safe investment? | Polite refusal + AMFI link |
| A-10 | Can I get guaranteed returns with HDFC ELSS? | Polite refusal + AMFI link |

### 2.3 Edge Case Queries

| ID | Query | Expected Behaviour |
|---|---|---|
| E-01 | (empty string) | "Please enter a question." |
| E-02 | PAN embedded query | PII scrubbed; answer proceeds |
| E-03 | Non-corpus fund (SBI Bluechip) | "Not found in official sources." |
| E-04 | Very long query (> 1000 chars) | Truncated; processed normally |
| E-05 | Hindi query | "English only" notice |

---

## 3. Metrics

### 3.1 Retrieval Metrics

| Metric | Definition | Target |
|---|---|---|
| **Hit Rate @ K=5** | % of queries where at least 1 relevant chunk is in top-5 results | ≥ 90% |
| **MRR (Mean Reciprocal Rank)** | Average of 1/rank of first relevant chunk | ≥ 0.75 |
| **Precision @ 3** | % of top-3 retrieved chunks that are relevant | ≥ 0.70 |
| **Context Relevance** | RAGAS: semantic similarity of retrieved context to query | ≥ 0.75 |

**Relevance Definition:** A chunk is "relevant" if it contains the specific field queried (e.g., "expense ratio" for expense ratio query), verified by manual labelling of ground-truth chunks.

### 3.2 Generation Metrics

| Metric | Definition | Target |
|---|---|---|
| **Faithfulness (RAGAS)** | % of answer claims supported by retrieved context | ≥ 0.90 |
| **Answer Correctness** | Exact or semantic match with ground-truth answer | ≥ 0.85 |
| **Answer Relevance (RAGAS)** | Semantic similarity of answer to query | ≥ 0.80 |
| **Hallucination Rate** | % of responses containing facts not in context | ≤ 5% |
| **"Not Found" Accuracy** | % of unanswerable queries correctly returning "not found" | ≥ 90% |

### 3.3 Constraint Compliance Metrics (Binary Pass/Fail)

| Constraint | Metric | Target |
|---|---|---|
| ≤ 3 sentences | % responses passing sentence check | 100% |
| Exactly 1 citation URL | % responses with exactly 1 URL | 100% |
| Footer present | % responses with `Last updated from sources:` | 100% |
| Advisory refusal rate | % advisory queries correctly refused | 100% |
| Refusal includes educational link | % refusals with AMFI/SEBI URL | 100% |
| No PII in output | % responses passing PII scan | 100% |
| No investment advice in output | % responses passing advisory phrase check | 100% |

### 3.4 System Reliability Metrics

| Metric | Definition | Target |
|---|---|---|
| **End-to-end latency (P50)** | Median query-to-response time (Groq is fast) | ≤ 3s |
| **End-to-end latency (P95)** | 95th percentile query-to-response time | ≤ 6s |
| **API error rate** | % Groq calls resulting in non-retried errors | ≤ 1% |
| **Fallback trigger rate** | % queries hitting fallback model | ≤ 5% |
| **Ingestion success rate** | % source documents successfully scraped + indexed | ≥ 95% |

---

## 4. Evaluation Framework

### 4.1 RAGAS Integration

Use the **RAGAS** framework for automated RAG evaluation:

```python
# tests/eval/ragas_eval.py
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)
from datasets import Dataset

def run_ragas_eval(eval_dataset: list[dict]) -> dict:
    """
    eval_dataset: list of {
        "question": str,
        "answer": str,          # system output
        "contexts": list[str],  # retrieved chunks
        "ground_truth": str     # expected answer
    }
    """
    ds = Dataset.from_list(eval_dataset)
    results = evaluate(
        ds,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    )
    return results
```

**Required environment:** `OPENAI_API_KEY` (RAGAS uses GPT as a judge by default; can swap to Groq judge with custom config).

### 4.2 Constraint Compliance Checker

```python
# tests/eval/compliance_checker.py
import re

def check_compliance(response: dict) -> dict:
    answer = response.get("answer", "")
    citation = response.get("citation", "")
    footer = response.get("footer", "")

    sentences = [s.strip() for s in re.split(r'[.!?]', answer) if s.strip()]
    url_count = len(re.findall(r'https?://\S+', answer + citation))
    has_footer = "Last updated from sources:" in footer
    
    pii_patterns = [
        r'[A-Z]{5}[0-9]{4}[A-Z]',          # PAN
        r'[2-9]{1}[0-9]{11}',               # Aadhaar
        r'(\+91)?[6-9]\d{9}',               # Phone
        r'[\w\.-]+@[\w\.-]+\.\w+',          # Email
    ]
    has_pii = any(re.search(p, answer) for p in pii_patterns)

    advisory_phrases = ["i recommend", "you should", "i suggest", "best choice", "better option"]
    has_advisory = any(p in answer.lower() for p in advisory_phrases)

    return {
        "sentence_count_ok": len(sentences) <= 3,
        "citation_count_ok": url_count == 1,
        "footer_ok": has_footer,
        "no_pii": not has_pii,
        "no_advisory": not has_advisory,
        "all_pass": all([
            len(sentences) <= 3,
            url_count == 1,
            has_footer,
            not has_pii,
            not has_advisory,
        ])
    }
```

### 4.3 Manual Evaluation Rubric

For each factual query response, human evaluators score on:

| Dimension | Scoring | Weight |
|---|---|---|
| **Factual Accuracy** | 0 = Wrong fact, 1 = Partially correct, 2 = Fully correct | 40% |
| **Source Trust** | 0 = No URL, 1 = URL present but wrong, 2 = Correct official URL | 25% |
| **Conciseness** | 0 = Too verbose, 1 = Slightly long, 2 = ≤ 3 sentences, on-point | 20% |
| **Compliance** | 0 = Advisory language present, 1 = Borderline, 2 = Fully compliant | 15% |

**Score interpretation:**
- ≥ 1.8 / 2.0 (weighted): ✅ Pass
- 1.5–1.79: ⚠️ Needs improvement
- < 1.5: ❌ Fail

---

## 5. Evaluation Execution Plan

### 5.1 Phase 8 Automated Evaluation (CI)

Run after every pipeline change:

```bash
# Run all compliance checks on golden dataset
pytest tests/eval/test_compliance.py -v

# Run RAGAS evaluation on 15 factual queries
python tests/eval/ragas_eval.py --dataset tests/eval/golden_factual.json

# Run latency benchmarks
python tests/eval/latency_bench.py --queries 25 --iterations 3
```

**Pass criteria for merge:**
- Compliance: 100% on all 7 constraint checks
- RAGAS Faithfulness: ≥ 0.90
- RAGAS Answer Relevancy: ≥ 0.80
- Advisory Refusal Rate: 100% on all 10 advisory queries
- P95 Latency: ≤ 6s

### 5.2 Pre-Release Manual Evaluation

Before final release, a human evaluator reviews all 25 factual responses using the rubric in §4.3:
- Minimum required: 90% of queries score ≥ 1.8 / 2.0
- No query should score 0 on Factual Accuracy or Compliance

### 5.3 Post-Corpus-Refresh Regression

After each corpus refresh (weekly), run:
- Full golden dataset (factual + advisory + edge cases)
- Verify no regression on previously passing queries
- Update ground-truth answers if official facts have changed

---

## 6. Evaluation Results Tracking

Maintain a results log at `tests/eval/results/`:

```
tests/eval/results/
├── ragas_<YYYY-MM-DD>.json        ← RAGAS metric scores per run
├── compliance_<YYYY-MM-DD>.json   ← Compliance check results
├── latency_<YYYY-MM-DD>.json      ← Latency percentiles
└── manual_eval_<YYYY-MM-DD>.md    ← Human evaluator scores
```

**Sample RAGAS result entry:**
```json
{
  "run_date": "2024-01-15",
  "model": "llama3-8b-8192",
  "embedding": "all-MiniLM-L6-v2",
  "faithfulness": 0.92,
  "answer_relevancy": 0.86,
  "context_precision": 0.78,
  "context_recall": 0.81,
  "advisory_refusal_rate": 1.0,
  "sentence_compliance": 1.0,
  "citation_compliance": 1.0,
  "p50_latency_ms": 1240,
  "p95_latency_ms": 3800
}
```

---

## 7. Failure Mode Thresholds & Actions

| Metric | Failure Threshold | Action |
|---|---|---|
| Faithfulness < 0.85 | 🔴 Blocked | Investigate system prompt; check chunk quality |
| Advisory Refusal Rate < 100% | 🔴 Blocked | Expand keyword list; review edge cases |
| Sentence Compliance < 100% | 🔴 Blocked | Fix sentence counter / truncation logic |
| Citation Compliance < 100% | 🔴 Blocked | Fix source injector |
| Answer Correctness < 0.80 | 🟠 High | Review retrieval pipeline; check corpus freshness |
| P95 Latency > 8s | 🟠 High | Profile Groq calls; check network; reduce context size |
| Hit Rate @ K=5 < 85% | 🟡 Medium | Improve chunking strategy; consider re-embedding |
| Hallucination Rate > 5% | 🔴 Blocked | Lower temperature (already 0.0); add stricter post-gen fact check |

---

## 8. Tools & Dependencies for Evaluation

| Tool | Purpose | Installation |
|---|---|---|
| `ragas` | Automated RAG metric evaluation | `pip install ragas` |
| `pytest` | Test runner for compliance checks | `pip install pytest` |
| `datasets` (HuggingFace) | Golden dataset loading for RAGAS | `pip install datasets` |
| `pandas` | Results aggregation and reporting | `pip install pandas` |
| `httpx` | Latency benchmarking | Already in `requirements.txt` |
| Manual spreadsheet | Human evaluator rubric scoring | Google Sheets / Excel |

---

## Summary

| Layer | Key Metric | Target |
|---|---|---|
| Retrieval | Hit Rate @ K=5 | ≥ 90% |
| Retrieval | RAGAS Context Precision | ≥ 0.75 |
| Generation | RAGAS Faithfulness | ≥ 0.90 |
| Generation | Answer Correctness | ≥ 0.85 |
| Compliance | Advisory Refusal Rate | 100% |
| Compliance | Sentence / Citation / Footer | 100% each |
| System | P95 End-to-End Latency | ≤ 6s |
| System | API Error Rate | ≤ 1% |

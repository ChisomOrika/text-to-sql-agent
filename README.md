# Text-to-SQL Agent with Data Catalog and Quality Awareness

Most text-to-SQL agents break on enterprise data because they assume clean schemas with obvious column names. They don't. In a real warehouse, "status" means nine different things across nine tables, "revenue" has three competing definitions that different departments will fight you over, and half the tables are stale or degraded and nobody updated the docs. These agents generate confident, syntactically valid SQL that returns the wrong answer — and nobody notices until someone makes a bad decision.

This agent knows when the data is stale, when a metric is ambiguous, and when to ask instead of guess.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          User Question                                   │
│                 "What was our revenue last quarter?"                      │
└─────────────────────────────┬────────────────────────────────────────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │   Parse Question     │  Claude extracts intent,
                   │   (LLM)             │  entities, time range
                   └──────────┬──────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │  Retrieve Schema     │  Sentence-transformers embed
                   │  (Local Embeddings)  │  the question, match against
                   │                     │  catalog vector index
                   └──────────┬──────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
              ambiguous?            no ambiguity
                    │                   │
                    ▼                   │
          ┌──────────────────┐          │
          │  Ask User         │          │
          │  "Revenue has 3   │          │
          │   definitions..." │          │
          └──────────────────┘          │
              (waits for input)         │
                    │                   │
                    └─────────┬─────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │  Check Freshness     │  Reads last_refreshed,
                   │  (Catalog Metadata)  │  quality_status, known
                   │                     │  issues from catalog
                   └──────────┬──────────┘
                              │
                              ▼
                ┌──────────────────────────┐
                │  Generate SQL (Claude)    │◄──────────────────┐
                │                          │                    │
                │  Prompt includes:        │              retry with
                │  • relevant catalog cols │              error context
                │  • business context      │                    │
                │  • sample queries        │                    │
                │  • quality warnings      │                    │
                └────────────┬─────────────┘                    │
                             │                                  │
                             ▼                                  │
                ┌──────────────────────────┐                    │
                │  Validate SQL             │                    │
                │  (Programmatic/sqlparse)  │──── invalid? ─────┘
                │                          │     (max 2 retries)
                │  • Table exists?         │
                │  • Columns exist?        │
                │  • No destructive SQL?   │
                └────────────┬─────────────┘
                             │ valid
                             ▼
                ┌──────────────────────────┐
                │  Execute on DuckDB        │
                └────────────┬─────────────┘
                             │
                             ▼
                ┌──────────────────────────┐
                │  Format Response          │  Combines results with
                │  (Claude)                │  freshness/quality warnings
                └────────────┬─────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  "Q1 billed revenue was $14.2M (1,200 invoices).                         │
│   ⚠ Note: this uses the Billed Revenue definition (invoiced amounts).   │
│   GAAP recognized revenue may differ due to timing."                     │
└──────────────────────────────────────────────────────────────────────────┘
```

### Data Layer

```
┌─────────────────────────────────────────────────────────────────────────┐
│  DuckDB Warehouse (15 tables, 3 schemas, ~24K rows)                     │
│                                                                         │
│  finance              operations            client_services             │
│  ├─ gl_transactions    ├─ work_orders        ├─ clients                 │
│  ├─ revenue_recognition├─ service_delivery   ├─ contracts               │
│  ├─ accounts_receivable├─ staffing           ├─ engagements             │
│  ├─ budgets            ├─ timesheets         ├─ client_feedback         │
│  ├─ gl_transactions_   ├─ departments        ├─ clients_v1             │
│  │  archive (stale)    │                     │  (deprecated)            │
│  └─────────────────    └─────────────────    └──────────────            │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                    served by │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  YAML Data Catalog (18 files)                                           │
│                                                                         │
│  Per table: columns, types, business context, disambiguation notes,     │
│  common mistakes, quality status, freshness timestamps, relationships,  │
│  sample queries                                                         │
│                                                                         │
│  Cross-schema: _metrics.yaml defines the 3 revenue definitions with     │
│  disambiguation prompts, plus utilization and satisfaction metrics       │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                    indexed by│
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Catalog Vector Index (sentence-transformers/all-MiniLM-L6-v2)          │
│  Local embeddings, ~5ms per query, cosine similarity via dot product    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## The Enterprise Data Problem

The warehouse is intentionally messy — modeled after the kind of data I've actually worked with:

**"Status" means nine different things.** GL transactions use `posted/pending/reversed`. Invoices use `open/paid/overdue/written_off`. Engagements use `active/completed/on_hold/at_risk`. Timesheets use `submitted/approved/rejected`. A naive agent doesn't know which one you mean.

**"Revenue" has three competing definitions.** Finance recognizes revenue per ASC 606 (monthly, often lagging). AR counts it when the invoice goes out (daily). Operations counts it when the client signs off on a deliverable (weekly). I spent four months at a previous role getting three departments to agree on one definition. The agent encodes all three and asks which one you want.

**Some tables are stale or degraded.** `revenue_recognition` hasn't been refreshed in three weeks. `timesheets.approved_by` has a 15% null rate from a workflow bug. `client_feedback.nps_score` has 20% nulls from a platform migration. The agent warns you about all of this instead of silently returning numbers from bad data.

**Legacy tables that look current but aren't.** `clients_v1` is from an old CRM migration. `gl_transactions_archive` is pre-2025 data. The agent knows not to query these.

---

## Challenges and Tradeoffs

### Schema size vs. context window

Enterprise databases have hundreds of tables. Stuffing the full schema into the prompt worked on 10 tables. At 50, the LLM started hallucinating column names from unrelated tables. I built a schema retrieval step: given the question, the catalog vector index pulls only the top-k relevant tables. This is a RAG problem inside a text-to-SQL problem.

I chose sentence-transformers for the catalog index instead of Claude embeddings. Catalog retrieval runs on every single query. Claude embeddings would have doubled the API cost and added 200ms+ of latency per query for marginal quality improvement on short text matching. Local embeddings are ~5ms and good enough for matching natural language questions to table descriptions.

### The metric disambiguation problem

The agent kept silently picking whichever revenue table appeared first in the catalog. I built a disambiguation layer: when a query maps to multiple metric definitions, the agent surfaces the options instead of choosing arbitrarily. The decision to ask rather than guess came directly from spending four months getting three departments to agree on one revenue definition. Silently picking one is the worst possible behavior — you return a confident number that's wrong for the person asking.

Disambiguation uses keyword matching, not the LLM. This is deliberate. I don't want a probabilistic system deciding whether "revenue" means revenue. That's exactly the kind of silent decision that causes wrong answers downstream. Keywords are deterministic, free, and correct 100% of the time for the terms that matter.

### Programmatic SQL validation over LLM validation

The validation step uses `sqlparse` to extract table and column references and checks them against the catalog. No LLM involved. I considered having Claude validate its own SQL, but that's using a probabilistic system to validate another probabilistic system. Programmatic validation is deterministic, adds zero latency or cost, and catches the most common failure modes: wrong table name, hallucinated column, destructive SQL.

Column extraction is intentionally loose. I tried strict SQL parsing and it generated more false positives (flagging valid SQL) than it caught real errors. The current approach catches the obvious mistakes — which is the 80/20 of validation.

### Data quality awareness

Most text-to-SQL projects treat the database as a source of truth. Anyone who's worked in enterprise data knows it isn't always. I added a quality metadata layer to the catalog. Each table has a quality status: `healthy`, `degraded`, or `stale`. When the agent queries a degraded table, it returns the results with a warning. When a table is stale, it suggests alternatives (e.g., "For March revenue estimates, use accounts_receivable as a proxy for the stale revenue_recognition table").

Freshness thresholds vary by refresh cadence. A daily table being 2 days stale is a problem. A monthly table being 2 days past its expected refresh is normal. I set thresholds at roughly 2x the cadence to avoid false alarms while still catching real issues.

### The retry loop

When SQL validation or execution fails, the agent retries with the error context appended to the prompt. Without seeing what failed and why, the LLM tends to regenerate the same broken query. Including both the failed SQL and the specific error message gives it enough context to self-correct. Max 2 retries — beyond that, the failure mode is usually a question the agent can't answer with the available tables, and retrying won't help.

---

## What I'd Do Differently

**Semantic caching for repeated queries.** The same questions get asked repeatedly ("what was revenue this quarter?"). A cache keyed on semantic similarity of the question — not exact string match — would eliminate redundant LLM calls for the most common queries. I'd embed the question, check against a cache of recent (question_embedding, sql, results) tuples, and return cached results if the similarity is above a threshold.

**A dedicated vector store at scale.** The current numpy-based index works for 15 tables. At 200+ tables (real enterprise scale), I'd move to a proper vector store — pgvector in Postgres or Qdrant. The index rebuild time and memory footprint of loading all embeddings into a numpy array would become a bottleneck.

**Query result validation, not just SQL validation.** The current system validates that the SQL is structurally correct. It doesn't validate that the *results* make sense. A future version should check: is the result count suspiciously low (zero rows when you'd expect thousands)? Is the aggregate wildly outside historical range? This would catch a whole class of "correct SQL, wrong answer" bugs.

**Multi-turn conversation with state.** The current disambiguation breaks the graph and re-invokes. A proper implementation would use LangGraph's `interrupt` mechanism or persistent checkpointing to maintain full conversation state across turns, including follow-up questions like "now break that down by region" that reference the previous query.

**Catalog maintenance automation.** The YAML catalog is manually maintained. In production, I'd build a pipeline that auto-generates the schema portion from the database's `information_schema`, auto-updates `last_refreshed` from the ETL pipeline's metadata, and runs data profiling to auto-detect quality degradation (null rate spikes, distribution shifts). The business context would still need human curation, but the mechanical parts shouldn't require manual updates.

**Confidence scoring.** Not all generated SQL is equally trustworthy. A single-table lookup with an exact column match is near-certain. A four-way join with a complex aggregation and ambiguous filters is risky. I'd add a confidence score based on the number of tables, complexity of the SQL, and how closely the retrieved catalog entries matched the question — and surface that score to the user.

---

## Quick Start

```bash
# Clone and enter the project
cd text-to-sql-agent

# Install dependencies
pip install -e ".[dev]"

# Set your API key
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY

# Create the warehouse (DuckDB, ~24K rows)
python scripts/setup_warehouse.py

# Build the catalog vector index
python scripts/index_catalog.py

# Start the API
uvicorn src.api.app:app --reload

# Or start the Streamlit UI
streamlit run src/ui/streamlit_app.py

# Run the evaluation suite (55 questions)
python scripts/run_eval.py
```

---

## Tech Stack

- **Database:** DuckDB (embedded analytical database, no server needed)
- **Agent Framework:** LangGraph (state graph with conditional edges, retry loops, human-in-the-loop)
- **LLM:** Claude via Anthropic SDK (question parsing, SQL generation, response formatting)
- **Catalog Retrieval:** sentence-transformers/all-MiniLM-L6-v2 (local embeddings, ~5ms per query)
- **SQL Validation:** sqlparse (programmatic, deterministic)
- **API:** FastAPI
- **UI:** Streamlit
- **Config:** Pydantic Settings
- **Data Catalog:** YAML (human-readable, version-controllable, git-diffable)

---

## Evaluation

55 test questions across 7 categories:

| Category | Count | Tests |
|---|---|---|
| Simple lookups | 10 | Single-table queries, filters, aggregations |
| Metric disambiguation | 8 | The 3 revenue definitions, when to ask vs. when not to |
| Freshness/quality | 8 | Stale data warnings, null rate warnings, deprecated tables |
| Multi-table joins | 10 | Cross-schema joins, 2-5 tables |
| Ambiguity resolution | 7 | "status" in different contexts, vague terms |
| Complex analytics | 7 | Budget variance, trends, window functions |
| Guardrails | 5 | Destructive SQL refusal, deprecated table redirect |

Metrics: SQL validity rate, disambiguation accuracy, warning correctness, table selection precision/recall, safety rate.

```bash
# Run full suite
python scripts/run_eval.py

# Run single category
python scripts/run_eval.py metric_disambiguation
```

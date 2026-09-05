# ComplianceSuite Docs Assistant

🔗 **[Try it live](https://cs-rag.streamlit.app/)**

A retrieval-augmented question answering system over the ComplianceSuite user manual.
Ask a question in plain English, get an answer grounded in the documentation with a
citation back to the exact section.

Built to handle problems that generic "chat with your PDF" tutorials ignore: this
manual contains near-duplicate pages (and at least one direct factual contradiction)
that vector search alone cannot tell apart, and many real questions need information
from two different sections at once.

---

## Architecture

```
docs/*.md
   │
   ▼  ingest.py          heading-based chunking + metadata extraction
chunks.json
   │
   ▼  build_index.py     local embeddings (BAAI/bge-base-en-v1.5) → Chroma
chroma/
   │
   ▼  retrieve.py        stage 1: vector search, 15 candidates       (recall)
   │                     stage 2: re-rank, keep top 5 -- 3 modes:    (precision)
   │                        - llm            reasons about multi-part questions.
   │                                         --backend claude-code (default, your
   │                                         claude.ai subscription via the CLI) or
   │                                         --backend groq (free API key)
   │                        - cross-encoder  local (ms-marco-MiniLM-L-6-v2), free,
   │                                         no network call, scores each passage alone
   │                        - none           raw vector order (baseline)
   │                     stage 3: cited answer generation, via the same backend
   ▼
app.py                   Streamlit UI -- pick re-rank mode and backend from the sidebar
```

## Setup

```bash
pip install -r requirements.txt

python ingest.py --src ./docs --out chunks.json
python build_index.py --chunks chunks.json --db ./chroma

# Default: uses your claude.ai subscription via the Claude Code CLI (run `claude login` once first)
python retrieve.py "What happens to an alert after I close it?"

# Free alternatives, no subscription usage:
python retrieve.py "..." --rerank cross-encoder
python retrieve.py "..." --backend groq --model openai/gpt-oss-120b   # needs GROQ_API_KEY

streamlit run app.py
```

## Design decisions

**Heading-based chunking instead of fixed-size windows.**
The manual is already sectioned with `##` / `###` headings, and those headings carry
real meaning — "Step 3: Set a Match Decision" is more informative than any sentence
under it. Splitting on headings keeps each chunk semantically whole and gives every
chunk a natural citation label. Sections under 200 characters are merged into a
neighboring section within the same file (e.g. the five Toolbox validation types
became two combined chunks) so no chunk is too thin to stand alone in retrieval.

**Screenshot alt-text is kept as retrieval signal.**
The docs reference UI screenshots whose alt-text names the exact elements users search
for ("the Add New button", "the Toolbox icon"). The alt-text is stripped out of the
displayed body but appended to the embedded text, so a question phrased in terms of
what the user sees on screen can still match.

**A genuine near-duplicate got merged, not just chunked around.**
`how-to-manual-search.md` and `screening-manual-search.md` were near-verbatim copies of
each other — and directly contradicted each other on one fact (one said results default
to "some" False Positive, the other said "all"). Splitting them into more chunks
wouldn't have fixed this; the fix was editorial: keep the more complete file, delete the
duplicate, and add a note flagging the discrepancy so the answer surfaces it honestly
instead of silently picking a side. Other reference-vs-how-to pairs in the corpus
(Link Analysis, Risk Scoring, Matches) were checked and found to be legitimately
complementary, not duplicates — those were left as-is.

**Two-stage retrieval, with interchangeable re-ranking strategies and backends.**
Embedding similarity alone is good at recall and bad at precision on this corpus.
Stage 1 casts a wide net (15 candidates). Stage 2 re-ranks down to the top 5:
- **LLM re-rank**: reasons about what a question actually needs, including multi-part
  questions that require two different passages. Runs via either backend:
  - `claude-code` (default) — your claude.ai subscription, called through the Claude
    Code CLI's `-p` print mode. Each call carries several thousand tokens of fixed
    overhead from Claude Code's own context loading, independent of prompt size,
    so `retrieve.py` and `eval.py` chain calls into one resumed session
    (`--resume <session_id>`) wherever possible — only the first call in a run pays
    that overhead in full; later calls hit the cache instead.
  - `groq` — a free API key, no subscription cost, no session-caching trick needed.
- **Cross-encoder** (local, free): a small model purpose-built for query-passage
  relevance scoring. No network call, no rate limit, no subscription usage. Scores
  each passage in isolation, so it can't reason about a question needing *two*
  passages.
- **None**: raw vector order, used as the baseline for comparison.

**Evaluation set built from the corpus, not invented.**
`eval_questions.json` contains 25 questions in three deliberate categories:
single-hop (answer lives in one section), multi-hop (answer needs two files), and
near-duplicate (two pages compete on the same question).

## Results

Run any mode and compare:

```bash
python eval.py --mode baseline
python eval.py --mode cross-encoder
python eval.py --mode rerank --limit 3            # test cost/quota before a full run
python eval.py --mode rerank                       # claude-code backend, default
python eval.py --mode rerank --backend groq --model openai/gpt-oss-120b
```

### Current setup (bge-base embeddings, 88 merged chunks, 25 questions)

| Mode | n | Recall | Precision | hit@k | Cost |
|---|---|---|---|---|---|
| Baseline (no re-rank) | 25 | 0.96 | 0.47 | 1.00 | Free |
| Cross-encoder, `ms-marco-MiniLM-L-6-v2` | 25 | 0.96 | **0.64** | 1.00 | Free |
| Cross-encoder, `bge-reranker-base` (tested, reverted) | 25 | 0.96 | 0.48 | 1.00 | Free |
| LLM re-rank, `llama-3.3-70b-versatile` (Groq) | 25 | 0.92 | 0.64 | 0.96 | Free |
| LLM re-rank, Claude Sonnet 5 (`claude-code` backend) | 25 | 0.96 | 0.66 | 1.00 | Subscription usage |
| LLM re-rank, `openai/gpt-oss-120b` (Groq) | 25 | *pending re-run on current setup* | | | Free |

**The free, local cross-encoder (`ms-marco-MiniLM-L-6-v2`) is the best-measured
free option, and is competitive with a paid subscription call.** It matches baseline
recall exactly while lifting precision from 0.47 to 0.64 — within 2 points of Claude
Sonnet 5's 0.66, at zero cost and no rate-limit or quota risk.

**Bigger isn't automatically better: a stronger-on-paper reranker made results worse.**
`BAAI/bge-reranker-base` (278M parameters vs MiniLM's 22M, and a broader general-purpose
reranker) was tested as an upgrade and instead dropped precision from 0.64 to 0.48 —
worse than the smaller model it was meant to replace. The likely reason: MiniLM's
`ms-marco` variant is trained specifically on the exact task this pipeline needs
(rank passages by relevance to a query), while bge-reranker-base is tuned more broadly
across tasks and domains. Model size and general capability don't guarantee a better
fit for a narrow, specific job — this was measured, not assumed, and the default was
reverted back to MiniLM once the regression showed up in the eval numbers.

**`llama-3.3-70b-versatile` underperformed** — it's the only mode tested where `hit@k`
dropped below 1.00: on one multi-hop question it retrieved *neither* of the two
required files, and it missed one required file each on two others.

`openai/gpt-oss-120b` — the model this project shipped with for most of its
development — is not yet re-confirmed on the current chunking/embedding setup (its
last full run used the older MiniLM embeddings and unmerged chunks, see below). That
comparison is the one open question left in this table.

### Superseded: original setup (MiniLM embeddings, 108 unmerged chunks, earlier question set)

| Question type | n | Recall (baseline) | Recall (LLM re-rank) | Precision (baseline) | Precision (LLM re-rank) |
|---|---|---|---|---|---|
| single-hop | 15 | 1.00 | 1.00 | 0.51 | 0.70 |
| multi-hop | 6 | 0.75 | 1.00 | 0.63 | 0.74 |
| near-duplicate | 4 | 1.00 | 1.00 | 0.60 | 0.82 |
| **Overall** | 25 | **0.94** | **1.00** | **0.55** | **0.73** |

This run used `openai/gpt-oss-120b` via Groq and is kept for context, not as a live
comparison — the embedding model, chunk boundaries, and 3 of the 25 questions have all
changed since. It's the run that established the core finding this project is built
around: re-ranking recovered every multi-hop miss (3 questions where baseline found
only one of the two required files) and improved precision everywhere without costing
any recall. Notably, its 1.00 multi-hop recall is better than anything achieved on the
current setup so far — which is exactly why re-confirming `gpt-oss-120b` on the current
chunks/embeddings, rather than assuming the old number still holds, is the next step.

### Why the two tables don't line up directly

Between the two result sets: the embedding model changed (MiniLM → bge-base), 21
undersized chunks got merged into neighbors (108 → 90 → 88 chunks), a genuine
near-duplicate pair got merged into one file, and 3 eval questions were updated
accordingly. Any of these could move the numbers independent of re-ranking strategy —
which is exactly why the "current setup" table above re-runs baseline fresh each time
rather than reusing the old baseline number.

## Known limitations

- `openai/gpt-oss-120b` needs re-confirming on the current chunking/embedding setup —
  the only real gap left in the results table above.
- Two multi-hop questions (q09, q11) are missed by every mode tested so far on the
  current setup, including every re-ranking strategy — baseline, both cross-encoders,
  and both LLM re-rankers. Since a re-ranker can only pick from what vector search
  hands it, this points to a retrieval-stage problem (the right chunk isn't reaching
  the top-15 candidate pool at all) rather than something a better re-ranker can fix.
  Worth investigating via query rewriting or a larger candidate pool before trying yet
  another re-ranking model.
- Groq's free tier rate-limits by tokens/day (`gpt-oss-120b`: 200k/day) and tokens/minute
  (`qwen/qwen3.6-27b`: 8k/min, too low to fit this project's re-rank prompt even after
  truncating passages to 350 characters and capping candidates at 15).
- The `claude-code` backend has real, non-trivial cost against your subscription's
  usage window — a single short call was measured at ~16,700 tokens / ~$0.10-equivalent
  of fixed overhead before the prompt is even considered, regardless of prompt size.
  Session-resuming cuts this substantially for calls after the first in a chained run,
  but does not eliminate it. `retrieve.py`/`eval.py` default to this backend; pass
  `--backend groq` for a free alternative with no such overhead.
- Reasoning models (e.g. `qwen/qwen3.6-27b`) emit a `<think>...</think>` block before
  the real answer; `groq_chat()` and `claude_chat()` both strip it, but this adds
  latency and token cost that non-reasoning models don't have.
- The cross-encoder scores each passage independently, so it structurally cannot do
  what the LLM re-ranker does for multi-part questions (recognize that two *different*
  passages are both needed) — yet it currently matches or beats every LLM re-ranker
  tested on multi-hop recall (0.83 across the board), suggesting the multi-hop gap here
  isn't actually about re-ranking reasoning at all (see the limitation above).
- Screenshots themselves are not indexed, only their alt-text.
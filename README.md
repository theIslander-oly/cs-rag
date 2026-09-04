# Helpdesk Docs Assistant

A retrieval-augmented question answering system over a helpdesk user manual.
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
   │                        - llm            Groq (openai/gpt-oss-120b), reasons
   │                                         about multi-part questions
   │                        - cross-encoder  local (ms-marco-MiniLM-L-6-v2), free,
   │                                         no API call, scores each passage alone
   │                        - none           raw vector order (baseline)
   │                     stage 3: cited answer generation, via Groq
   ▼
app.py                   Streamlit UI -- pick the re-rank mode from the sidebar
```

## Setup

```bash
pip install -r requirements.txt
set GROQ_API_KEY=...                # get a free key at console.groq.com, no card required

python ingest.py --src ./docs --out chunks.json
python build_index.py --chunks chunks.json --db ./chroma

python retrieve.py "What happens to an alert after I close it?"
python retrieve.py "..." --rerank cross-encoder    # free, local, no API call
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

**Two-stage retrieval, with three interchangeable re-ranking strategies.**
Embedding similarity alone is good at recall and bad at precision on this corpus.
Stage 1 casts a wide net (15 candidates). Stage 2 re-ranks down to the top 5, and three
strategies are implemented so the trade-off is measurable rather than assumed:
- **LLM re-rank** (Groq): reasons about what a question actually needs, including
  multi-part questions that require two different passages.
- **Cross-encoder** (local, free): a small model purpose-built for query-passage
  relevance scoring. No API call, no rate limit, runs in milliseconds. Scores each
  passage in isolation, so it can't reason about a question needing *two* passages.
- **None**: raw vector order, used as the baseline for comparison.

**Evaluation set built from the corpus, not invented.**
`eval_questions.json` contains 25 questions in three deliberate categories:
single-hop (answer lives in one section), multi-hop (answer needs two files), and
near-duplicate (two pages compete on the same question).

## Results

The table below reflects a full run against the original (private) helpdesk
manual. The `eval_questions.json` shipped in this repo is a smaller demo set over
`docs_sample/`, so anyone cloning the repo can reproduce a run themselves — see
`docs_sample/README.md`.

Run any mode and compare:

```bash
python eval.py --mode baseline
python eval.py --mode cross-encoder
python eval.py --mode rerank
python eval.py --mode rerank --model llama-3.3-70b-versatile   # or any other Groq model
```

### Current setup (bge-base embeddings, 88 merged chunks, 25 questions)

| Mode | n | Recall | Precision | hit@k |
|---|---|---|---|---|
| Baseline (no re-rank) | 25 | 0.96 | 0.47 | 1.00 |
| Cross-encoder (local, free) | 25 | 0.96 | **0.64** | 1.00 |
| LLM re-rank, `llama-3.3-70b-versatile` | 25 | 0.92 | 0.64 | 0.96 |
| LLM re-rank, `openai/gpt-oss-120b` | 25 | *pending re-run on current setup* | | |

**The free, local cross-encoder is currently the best-measured option.** It matches
baseline recall exactly (loses nothing) while lifting precision from 0.47 to 0.64 —
comparable to or better than the LLM re-rankers tested so far, at zero cost and no
rate-limit risk.

**`llama-3.3-70b-versatile` underperformed** — it's the only mode tested where `hit@k`
dropped below 1.00: on one multi-hop question it retrieved *neither* of the two
required files, and it missed one required file each on two others. Cheaper and
faster models aren't automatically worse for this task, and expensive general-purpose
ones aren't automatically better — the cross-encoder, the smallest model in this
comparison, currently has the best precision.

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

This is kept for context, not as a live comparison — the embedding model, chunk
boundaries, and 3 of the 25 questions have all changed since. It's the run that
established the core finding this project is built around: re-ranking recovered every
multi-hop miss (3 questions where baseline found only one of the two required files)
and improved precision everywhere without costing any recall.

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
- Groq's free tier rate-limits by tokens/day (`gpt-oss-120b`: 200k/day) and tokens/minute
  (`qwen/qwen3.6-27b`: 8k/min, too low to fit this project's re-rank prompt even after
  truncating passages to 350 characters and capping candidates at 15). The cross-encoder
  mode has no such limit since it runs locally.
- Reasoning models (e.g. `qwen/qwen3.6-27b`) emit a `<think>...</think>` block before
  the real answer; `groq_chat()` strips it, but this adds latency and token cost that
  non-reasoning models don't have.
- The cross-encoder scores each passage independently, so it structurally cannot do
  what the LLM re-ranker does for multi-part questions (recognize that two *different*
  passages are both needed). Its strong recall so far suggests vector search is already
  surfacing both passages in the candidate pool; the LLM's advantage would be expected
  to show up more on questions where the two required passages are less obviously
  related in embedding space.
- Screenshots themselves are not indexed, only their alt-text.

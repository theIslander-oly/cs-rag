# Sample corpus

Synthetic docs for a fictional helpdesk product ("TicketFlow"), written to
exercise this pipeline end to end without the real (internal, non-public)
manual it was originally built against.

Deliberate structural properties, matching what `ingest.py` and `retrieve.py`
were built to handle:

- `##` doc titles and `###` subheadings for `ingest.py`'s section-based
  chunking
- image alt-text lines for the alt-text-as-retrieval-signal behavior
- `how-to-*.md` naming for the how-to vs. reference `doc_type` flag
- multi-hop facts split across two files (e.g. escalation behavior spans
  `ticket-statuses.md` and `how-to-escalation-rules.md`)
- a legitimately complementary how-to/reference pair
  (`how-to-manual-search.md` / `search-fields.md`) that a naive dedupe pass
  would wrongly treat as a duplicate
- one deliberately unresolved discrepancy, flagged in place rather than
  silently resolved (`how-to-manual-search.md`, default sort order)

Run the pipeline against it:

```bash
python ingest.py --src ./docs_sample --out chunks.json
python build_index.py --chunks chunks.json --db ./chroma
python retrieve.py "How does auto-assignment decide which agent gets a new ticket?"
python eval.py --questions docs_sample/eval_questions_sample.json --mode cross-encoder
```

Point `--src` at your own docs folder to use this on real content instead.

"""
Step 4: Measure retrieval quality, with and without re-ranking. Uses Groq's
free API -- fast enough to run the full eval set in well under a minute.

This is the part that turns the project from a demo into evidence. It reports,
per question type:

  recall     fraction of the expected source files that appear in the top-k
  precision  fraction of retrieved chunks that came from an expected file
  hit@k      whether at least one expected file was retrieved

Run both modes and compare -- the delta on multi-hop and near-duplicate
questions is the number worth putting in your README.

Usage:
    python eval.py --mode baseline
    python eval.py --mode rerank
    python eval.py --mode rerank --model llama-3.1-70b-versatile
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

import chromadb

from retrieve import MODEL, N_KEEP, get_client, rerank, rerank_cross_encoder, search
from build_index import COLLECTION, get_embedding_function


def evaluate(questions, db, mode, model=MODEL, k=N_KEEP):
    col = chromadb.PersistentClient(path=db).get_collection(
        COLLECTION, embedding_function=get_embedding_function()
    )
    # Only the LLM re-ranker needs a Groq client; baseline and cross-encoder
    # run entirely locally.
    client = get_client() if mode == "rerank" else None

    rows = []
    for q in questions:
        cands = search(col, q["question"])

        if mode == "rerank":
            top = rerank(client, q["question"], cands, model=model, keep=k)
        elif mode == "cross-encoder":
            top = rerank_cross_encoder(q["question"], cands, keep=k)
        else:
            top = cands[:k]

        got_files = [c["meta"]["source_file"] for c in top]
        expected = set(q["expected_files"])
        found = expected & set(got_files)

        rows.append(
            {
                "id": q["id"],
                "type": q["type"],
                "recall": len(found) / len(expected),
                "precision": sum(1 for f in got_files if f in expected) / max(len(got_files), 1),
                "hit": 1.0 if found else 0.0,
                "missing": sorted(expected - set(got_files)),
                "retrieved": [c["meta"]["citation"] for c in top],
            }
        )
        print(f"  {q['id']} ({q['type']}) done")
    return rows


def report(rows, mode):
    by_type = defaultdict(list)
    for r in rows:
        by_type[r["type"]].append(r)

    def avg(items, key):
        return sum(i[key] for i in items) / len(items)

    print(f"\n=== mode: {mode} (n={len(rows)}) ===")
    print(f"{'type':<16}{'n':>4}{'recall':>9}{'precision':>11}{'hit@k':>8}")
    for t, items in sorted(by_type.items()):
        print(
            f"{t:<16}{len(items):>4}{avg(items,'recall'):>9.2f}"
            f"{avg(items,'precision'):>11.2f}{avg(items,'hit'):>8.2f}"
        )
    print(
        f"{'OVERALL':<16}{len(rows):>4}{avg(rows,'recall'):>9.2f}"
        f"{avg(rows,'precision'):>11.2f}{avg(rows,'hit'):>8.2f}"
    )

    misses = [r for r in rows if r["missing"]]
    if misses:
        print("\nmissed expected files:")
        for r in misses:
            print(f"  {r['id']} ({r['type']}): {', '.join(r['missing'])}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default="eval_questions.json")
    ap.add_argument("--db", default="./chroma")
    ap.add_argument(
        "--mode",
        choices=["baseline", "rerank", "cross-encoder"],
        default="rerank",
        help="baseline = raw vector order, rerank = Groq LLM re-rank, cross-encoder = local model",
    )
    ap.add_argument("--model", default=MODEL, help="Groq model tag")
    ap.add_argument("--out", default=None, help="optional path to dump per-question JSON")
    args = ap.parse_args()

    questions = json.loads(Path(args.questions).read_text(encoding="utf-8"))
    rows = evaluate(questions, args.db, args.mode, model=args.model)
    report(rows, args.mode)

    if args.out:
        Path(args.out).write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"\nwrote -> {args.out}")


if __name__ == "__main__":
    main()

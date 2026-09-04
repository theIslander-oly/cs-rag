"""
Step 3: Retrieve -> re-rank -> generate. Uses Groq's free API -- fast (custom
inference hardware) and no cost on the free tier.

Setup:
    1. Sign up at https://console.groq.com (free, no card required)
    2. Create an API key under API Keys
    3. set GROQ_API_KEY=your_key_here      (Windows Command Prompt)

The two-stage design is the point of this project:

  Stage 1 (recall)    vector search pulls a wide net of ~20 candidates. Cheap
                      and fast, but embedding similarity alone confuses the
                      near-duplicate pages in this manual (e.g. the two Manual
                      Search write-ups, or reference vs how-to Link Analysis).

  Stage 2 (precision) an LLM scores each candidate 0-3 for how well it actually
                      answers the question, and we keep the top 5. This is what
                      resolves the near-duplicates and lets multi-hop questions
                      keep chunks from two different files.

Usage:
    python retrieve.py "How do I close an alert?"
    python retrieve.py "..." --no-rerank      # baseline, for the eval comparison
    python retrieve.py "..." --model qwen/qwen3.6-27b
"""

import argparse
import json
import os
import re

import chromadb
from groq import Groq

from build_index import COLLECTION, get_embedding_function

MODEL = "openai/gpt-oss-120b"
CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
N_CANDIDATES = 15
N_KEEP = 5

# Cross-encoder relevance floor. ms-marco models output unbounded logits;
# roughly, >0 means "relevant", well below 0 means "not relevant". Candidates
# scoring under this are dropped rather than padding out the top-k.
CROSS_ENCODER_MIN_SCORE = -5.0

# bge-base-en-v1.5 is an asymmetric embedding model: queries need this
# instruction prefix for best retrieval quality, documents do not.
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

RERANK_PROMPT = """You are ranking documentation passages for relevance to a user question about the helpdesk platform.

Question: {question}

Passages:
{passages}

Score each passage 0-3:
3 = directly and fully answers the question
2 = contains part of the answer, or necessary supporting detail
1 = same topic area but does not answer the question
0 = irrelevant

Some questions need information from more than one passage. Score each passage on its own contribution.

Return ONLY a JSON array like [{{"index": 0, "score": 3}}, ...]. No other text, no markdown fences."""

ANSWER_PROMPT = """Answer the user's question using ONLY the documentation passages below. \
If the passages do not contain the answer, say so plainly rather than guessing.

Each passage below is labeled like this: [N] (Exact Citation Text)
When you state a fact from a passage, cite it by writing the citation text itself in square brackets -- \
for example, if passage [2] is labeled (Screening > Searches), write [Screening > Searches] in your answer, \
NOT [2] and NOT any other symbol or number. Copy the citation text exactly as given, do not shorten it.

Passages:
{passages}

Question: {question}"""


def get_client():
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise SystemExit(
            "Set GROQ_API_KEY first. Get a free key at https://console.groq.com\n"
            "Windows: set GROQ_API_KEY=your_key_here"
        )
    return Groq(api_key=key)


def groq_chat(client, prompt, model=MODEL, temperature=0.0):
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    text = resp.choices[0].message.content
    # Reasoning models (e.g. qwen/qwen3.6-27b) emit a <think>...</think> block
    # of internal reasoning before the real answer. Strip it so callers only
    # ever see the final answer, regardless of which model is in use.
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def search(col, question, n=N_CANDIDATES):
    res = col.query(query_texts=[QUERY_PREFIX + question], n_results=n)
    return [
        {"doc": d, "meta": m, "distance": dist}
        for d, m, dist in zip(
            res["documents"][0], res["metadatas"][0], res["distances"][0]
        )
    ]


def format_passages(cands, truncate=None):
    """truncate: max characters per passage body. Use a short value for the
    re-ranking prompt (only needs enough text to judge relevance) and leave
    it unset for the final answer prompt (needs the full passage)."""
    parts = []
    for i, c in enumerate(cands):
        body = c["doc"]
        if truncate and len(body) > truncate:
            body = body[:truncate].rsplit(" ", 1)[0] + "..."
        parts.append(f"[{i}] ({c['meta']['citation']})\n{body}")
    return "\n\n".join(parts)


def _extract_json_array(text):
    text = re.sub(r"```json|```", "", text).strip()
    m = re.search(r"\[.*\]", text, re.DOTALL)
    return m.group(0) if m else text


def rerank(client, question, cands, model=MODEL, keep=N_KEEP):
    prompt = RERANK_PROMPT.format(question=question, passages=format_passages(cands, truncate=350))
    text = groq_chat(client, prompt, model=model)

    try:
        scores = json.loads(_extract_json_array(text))
    except json.JSONDecodeError:
        # Re-ranker failed to return valid JSON: fall back to vector order.
        return cands[:keep]

    for s in scores:
        i = s.get("index")
        if isinstance(i, int) and 0 <= i < len(cands):
            cands[i]["score"] = s.get("score", 0)

    ranked = sorted(cands, key=lambda c: c.get("score", 0), reverse=True)
    kept = [c for c in ranked if c.get("score", 0) > 0][:keep]
    return kept if kept else cands[:keep]


_cross_encoder = None


def get_cross_encoder(model_name=CROSS_ENCODER_MODEL):
    """Loaded once and reused -- model init is the expensive part, not scoring."""
    global _cross_encoder
    if _cross_encoder is None:
        from sentence_transformers import CrossEncoder

        _cross_encoder = CrossEncoder(model_name)
    return _cross_encoder


def rerank_cross_encoder(question, cands, keep=N_KEEP, model_name=CROSS_ENCODER_MODEL):
    """Re-rank with a local cross-encoder instead of an LLM call.

    A cross-encoder reads the question and passage together and outputs a single
    relevance score, which is exactly the job the LLM re-ranker does via prompt --
    but it runs locally in milliseconds, needs no API key, has no rate limits, and
    can't return malformed JSON. The trade-off is that it scores each passage in
    isolation on topical relevance, with none of the LLM's ability to reason about
    what a multi-part question actually requires.
    """
    encoder = get_cross_encoder(model_name)
    pairs = [(question, c["doc"]) for c in cands]
    scores = encoder.predict(pairs)

    for c, s in zip(cands, scores):
        c["score"] = float(s)

    ranked = sorted(cands, key=lambda c: c["score"], reverse=True)
    kept = [c for c in ranked if c["score"] > CROSS_ENCODER_MIN_SCORE][:keep]
    return kept if kept else ranked[:keep]


def answer(client, question, passages, model=MODEL):
    prompt = ANSWER_PROMPT.format(question=question, passages=format_passages(passages))
    return groq_chat(client, prompt, model=model, temperature=0.2)


def ask(question, db="./chroma", use_rerank=True, model=MODEL, client=None, rerank_mode="llm"):
    """rerank_mode: 'llm' (Groq call), 'cross-encoder' (local), or 'none'."""
    col = chromadb.PersistentClient(path=db).get_collection(
        COLLECTION, embedding_function=get_embedding_function()
    )
    cands = search(col, question)
    client = client or get_client()

    if not use_rerank or rerank_mode == "none":
        top = cands[:N_KEEP]
    elif rerank_mode == "cross-encoder":
        top = rerank_cross_encoder(question, cands)
    else:
        top = rerank(client, question, cands, model=model)

    return answer(client, question, top, model=model), top


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--db", default="./chroma")
    ap.add_argument("--model", default=MODEL, help="Groq model tag")
    ap.add_argument(
        "--rerank",
        choices=["llm", "cross-encoder", "none"],
        default="llm",
        help="llm = Groq re-rank (default), cross-encoder = local model, none = raw vector order",
    )
    ap.add_argument("--no-rerank", action="store_true", help="alias for --rerank none")
    args = ap.parse_args()

    mode = "none" if args.no_rerank else args.rerank
    text, top = ask(args.question, args.db, model=args.model, rerank_mode=mode)
    print(text)
    print("\n--- sources ---")
    for c in top:
        score = c.get("score")
        suffix = f"  [score {score:.2f}]" if isinstance(score, float) else ""
        print(f"  {c['meta']['citation']}  ({c['meta']['source_file']}){suffix}")


if __name__ == "__main__":
    main()

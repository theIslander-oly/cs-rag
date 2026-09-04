"""
Step 5: Minimal Streamlit UI, backed by Groq's free API.

Run:  streamlit run app.py
"""

from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Helpdesk Docs Assistant", page_icon="📘")

# On a fresh deploy (e.g. Streamlit Community Cloud), ./chroma won't exist yet
# since it's gitignored -- build it once on first load instead of shipping the
# database in the repo.
if not Path("./chroma").exists():
    with st.spinner("First-time setup: building the search index (~1-2 min)…"):
        import subprocess
        subprocess.run(["python", "ingest.py", "--src", "./docs", "--out", "chunks.json"], check=True)
        subprocess.run(["python", "build_index.py", "--chunks", "chunks.json", "--db", "./chroma"], check=True)

from retrieve import MODEL, ask, get_client

st.title("Helpdesk Docs Assistant")
st.caption("Ask a question about the user manual. Answers are grounded in the docs and cited.")
st.caption(f"Powered by Groq ({MODEL}).")

with st.sidebar:
    rerank_mode = st.radio(
        "Re-ranking",
        options=["llm", "cross-encoder", "none"],
        format_func=lambda m: {
            "llm": "LLM (Groq)",
            "cross-encoder": "Cross-encoder (local)",
            "none": "None (raw vector search)",
        }[m],
    )
    st.caption(
        "The LLM re-ranker reasons about what a question actually needs, which helps "
        "most on questions spanning two sections. The cross-encoder is far faster and "
        "runs locally, but scores each passage in isolation."
    )

question = st.text_input(
    "Question",
    placeholder="e.g. What happens to an alert after I close it?",
)

if question:
    with st.spinner("Searching the manual…"):
        try:
            client = get_client()
            text, sources = ask(question, rerank_mode=rerank_mode, client=client)
        except Exception as e:
            st.error(f"Something went wrong: {e}")
            st.stop()

    st.markdown(text)

    st.divider()
    st.subheader("Sources")
    for c in sources:
        score = c.get("score")
        label = c["meta"]["citation"]
        if score is not None:
            # LLM re-ranker returns an int on a 0-3 scale; the cross-encoder
            # returns an unbounded float logit.
            label += f"  ·  relevance {score}/3" if isinstance(score, int) else f"  ·  score {score:.2f}"
        with st.expander(label):
            st.caption(f"{c['meta']['source_file']} · {c['meta']['doc_type']}")
            st.text(c["doc"][:1500])

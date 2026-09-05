"""
Step 5: Minimal Streamlit UI, backed by Groq's free API.

Run:  streamlit run app.py
"""

import os
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Helpdesk Docs Assistant", page_icon="📘")

# retrieve.get_client() reads os.environ["GROQ_API_KEY"]. Streamlit Cloud
# normally exports secrets as env vars too, but bridge it explicitly so the
# app doesn't depend on that.
if not os.environ.get("GROQ_API_KEY"):
    try:
        os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
    except Exception:
        # No secrets file (plain local run) -- get_client() will raise its own
        # clear "Set GROQ_API_KEY first" message.
        pass

# The docs folder is named ./docs locally but the public repo ships ./docs_sample.
# Pick whichever exists so the same app.py works in both places.
DOCS_DIR = next((p for p in ("./docs", "./docs_sample") if Path(p).is_dir()), None)

# On a fresh deploy (e.g. Streamlit Community Cloud), ./chroma won't exist yet
# since it's gitignored -- build it once on first load instead of shipping the
# database in the repo.
if not Path("./chroma").exists():
    if DOCS_DIR is None:
        st.error("No docs folder found (looked for ./docs and ./docs_sample).")
        st.stop()
    import subprocess
    import sys

    def run_step(label, cmd):
        """check=True hides the child's stderr behind a bare CalledProcessError,
        which Streamlit Cloud then redacts -- so capture it and show it."""
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            st.error(f"Setup step failed: {label}")
            st.code((proc.stderr or proc.stdout or "no output")[-3000:], language="text")
            st.stop()

    with st.spinner("First-time setup: building the search index (~1-2 min)…"):
        py = sys.executable  # the venv's python, not whatever "python" resolves to
        run_step("ingest.py", [py, "ingest.py", "--src", DOCS_DIR, "--out", "chunks.json"])
        run_step("build_index.py", [py, "build_index.py", "--chunks", "chunks.json", "--db", "./chroma"])

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
    placeholder="e.g. How to create a ticket?",
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

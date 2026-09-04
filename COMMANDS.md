# Running this project — command reference

Copy-paste reference for Command Prompt (not PowerShell — some commands here use
`set`, which only works correctly in Command Prompt).

---

## Every time you open a new Command Prompt window

You need these two lines before running anything else. Both only last for the
current window — close it, and you'll need to run them again in the next one.

```
cd C:\Users\snikolaidis\Documents\cs-rag
set GROQ_API_KEY=your_key_here
```

Get a key at console.groq.com if you don't have one yet (free, no card required).

---

## First-time setup only (already done — skip unless starting fresh)

```
python -m pip install -r requirements.txt
```

---

## After changing anything in `docs/` (adding, editing, or deleting a .md file)

Run these three in order — each depends on the one before it:

```
python ingest.py --src ./docs --out chunks.json
python build_index.py --chunks chunks.json --db ./chroma
```

`build_index.py` re-downloads nothing after the first run — it's quick.

---

## Ask a single question

```
python retrieve.py "your question here"
```

Add `--no-rerank` to see raw vector-search results without the re-ranking step
(useful for comparing / debugging):
```
python retrieve.py "your question here" --no-rerank
```

---

## Run the full evaluation (25 questions, both modes)

```
python eval.py --mode baseline --out results_baseline.json
python eval.py --mode rerank --out results_rerank.json
```

Groq's free tier caps at 200,000 tokens/day for `openai/gpt-oss-120b` — if you hit
a `RateLimitError`, you've used today's allowance; wait for the daily reset or
switch to a lighter model for testing:
```
python eval.py --mode rerank --model openai/gpt-oss-20b --out results_rerank_test.json
```

---

## Launch the web demo

```
python -m streamlit run app.py
```

Opens automatically in your browser. If not, it prints a local URL
(e.g. `http://localhost:8501`) — open that manually. Press `Ctrl+C` in the
terminal to stop it.

---

## Quick troubleshooting

| Problem | Fix |
|---|---|
| `'pip' is not recognized` | Use `python -m pip install ...` instead |
| `'streamlit' is not recognized` | Use `python -m streamlit run app.py` instead |
| `Set GROQ_API_KEY first` | You're either in PowerShell (use `$env:GROQ_API_KEY="..."` there) or forgot to `set` it in this window |
| `RateLimitError` from Groq | Daily free-tier token limit hit — wait ~24h, or use `--model openai/gpt-oss-20b` |
| Answer looks wrong / low quality | Re-check you're using `--model openai/gpt-oss-120b` (the deprecated `llama-3.1-8b-instant` gives poor results) |

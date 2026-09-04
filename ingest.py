"""
Step 1: Ingest helpdesk docs -> structured chunks with metadata.

Splits each markdown file on '###' subheadings (falling back to the '##' doc
title when a file has no subheadings). Image lines are stripped from the body
but their alt-text is kept as a separate metadata field, since the alt-text
describes UI screenshots and is useful retrieval signal.

Usage:  python ingest.py --src ./docs --out chunks.json
"""

import argparse
import json
import re
from pathlib import Path

IMAGE_RE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<path>[^)]*)\)")
H2_RE = re.compile(r"^##\s+(?P<title>.+?)\s*$", re.MULTILINE)
H3_RE = re.compile(r"^###\s+(?P<title>.+?)\s*$", re.MULTILINE)

# Files that are reference-style vs step-by-step guides. Used as a metadata
# flag so retrieval can prefer how-to content for "how do I..." questions.
HOWTO_PREFIX = "how-to-"


def extract_images(text):
    """Pull image alt-text out of the body, return (clean_text, alt_texts)."""
    alts = [m.group("alt").strip() for m in IMAGE_RE.finditer(text)]
    clean = IMAGE_RE.sub("", text)
    # collapse the blank lines left behind
    clean = re.sub(r"\n{3,}", "\n\n", clean).strip()
    return clean, alts


def doc_title(text, fallback):
    m = H2_RE.search(text)
    return m.group("title").strip() if m else fallback


MIN_CHARS = 200


def merge_tiny_sections(sections):
    """Merge undersized sections into a neighbor so no chunk is left too thin
    to stand alone in retrieval. sections is a list of dicts with 'title',
    'body' (already image-stripped), and 'alts'. Merges forward into the next
    section; a trailing undersized section merges backward into the previous
    one instead, since there's no "next" to absorb it. Combined sections keep
    both titles, joined with " / ", so the citation still names every topic
    covered ("IBAN Validation / MRZ Validation")."""
    if len(sections) <= 1:
        return sections

    merged = []
    pending = None

    def combine_titles(a, b):
        parts = [t for t in (a, b) if t]
        return " / ".join(parts) if parts else None

    for sec in sections:
        if pending is not None:
            sec = {
                "title": combine_titles(pending["title"], sec["title"]),
                "body": f"{pending['body']}\n\n{sec['body']}",
                "alts": pending["alts"] + sec["alts"],
            }
            pending = None

        if len(sec["body"]) < MIN_CHARS:
            pending = sec
        else:
            merged.append(sec)

    if pending is not None:
        if merged:
            prev = merged[-1]
            merged[-1] = {
                "title": combine_titles(prev["title"], pending["title"]),
                "body": f"{prev['body']}\n\n{pending['body']}",
                "alts": prev["alts"] + pending["alts"],
            }
        else:
            merged.append(pending)

    return merged


def split_sections(text):
    """Split on ### headings. Returns list of (section_title, raw_body)."""
    matches = list(H3_RE.finditer(text))
    if not matches:
        # No subheadings: strip the ## title line, treat whole file as one section.
        body = H2_RE.sub("", text, count=1).strip()
        return [(None, body)]

    sections = []
    # Preamble before the first ### (after the ## title) is its own chunk.
    preamble = H2_RE.sub("", text[: matches[0].start()], count=1).strip()
    if preamble:
        sections.append((None, preamble))

    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            sections.append((m.group("title").strip(), body))
    return sections


def chunk_file(path):
    raw = path.read_text(encoding="utf-8")
    slug = path.stem
    title = doc_title(raw, slug.replace("-", " ").title())
    is_howto = slug.startswith(HOWTO_PREFIX)

    # Strip images per raw section first, so the merge step measures the
    # actual post-cleaning length -- otherwise a section can look long
    # enough before stripping and still end up tiny after.
    cleaned = []
    for section, raw_body in split_sections(raw):
        clean, alts = extract_images(raw_body)
        if clean:
            cleaned.append({"title": section, "body": clean, "alts": alts})

    chunks = []
    for idx, sec in enumerate(merge_tiny_sections(cleaned)):
        chunks.append(
            {
                "id": f"{slug}::{idx}",
                "source_file": path.name,
                "doc_title": title,
                "section": sec["title"],
                "citation": f"{title} > {sec['title']}" if sec["title"] else title,
                "doc_type": "how-to" if is_howto else "reference",
                "content": sec["body"],
                "image_alts": sec["alts"],
                "n_chars": len(sec["body"]),
            }
        )
    return chunks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="./docs", help="folder of .md files")
    ap.add_argument("--out", default="chunks.json")
    args = ap.parse_args()

    files = sorted(Path(args.src).glob("*.md"))
    if not files:
        raise SystemExit(f"No .md files found in {args.src}")

    all_chunks = []
    for f in files:
        all_chunks.extend(chunk_file(f))

    Path(args.out).write_text(
        json.dumps(all_chunks, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    sizes = [c["n_chars"] for c in all_chunks]
    print(f"files:            {len(files)}")
    print(f"chunks:           {len(all_chunks)}")
    print(f"chars  min/med/max: {min(sizes)} / {sorted(sizes)[len(sizes)//2]} / {max(sizes)}")
    print(f"how-to chunks:    {sum(1 for c in all_chunks if c['doc_type'] == 'how-to')}")
    print(f"oversized (>4000): {sum(1 for s in sizes if s > 4000)}")
    print(f"tiny (<200):       {sum(1 for s in sizes if s < 200)}")
    print(f"wrote -> {args.out}")


if __name__ == "__main__":
    main()

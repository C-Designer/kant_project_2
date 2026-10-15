"""Assemble docs/learn/fastapi-langchain.html from shell.html and parts/*.html in this folder.

Each <code-block file="..." lines="A-B"> is verified verbatim against the file on disk,
converted into a numbered, highlighted <figure class="code">, and every quiz JSON block is
validated. Run from anywhere: python3 -I docs/learn/src/build.py  (prints problems; exit 1 if any block fails).
"""

import html
import json
import re
import sys
from pathlib import Path

TOUR = Path(__file__).resolve().parent
ROOT = TOUR.parents[2]
PARTS = ["fastapi-1-2", "fastapi-3ab", "fastapi-3cd", "fastapi-share", "langchain-1-2", "langchain-3ab", "langchain-3cd"]
OUT = ROOT / "docs/learn/fastapi-langchain.html"

KEYWORDS = {
    "False", "None", "True", "and", "as", "assert", "async", "await", "break", "class", "continue",
    "def", "del", "elif", "else", "except", "finally", "for", "from", "global", "if", "import",
    "in", "is", "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try", "while",
    "with", "yield", "match", "case",
}
BUILTINS = {
    "self", "cls", "print", "len", "dict", "list", "set", "tuple", "str", "int", "float", "bool",
    "bytes", "isinstance", "next", "zip", "range", "any", "all", "sorted", "getattr", "setattr",
    "hasattr", "object", "Exception", "BaseException", "ValueError", "TypeError", "KeyError",
    "OSError", "RuntimeError", "AssertionError", "super", "map", "enumerate", "iter", "open",
    "property", "classmethod", "staticmethod", "type", "id", "min", "max", "sum", "repr",
}
TOKEN_RE = re.compile(
    r"""
    (?P<comment>\#[^\n]*)
  | (?P<string>(?:[rRbBuUfF]{1,2})?(?:\"\"\"[\s\S]*?\"\"\"|'''[\s\S]*?'''|"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'))
  | (?P<decorator>@[\w.]+)
  | (?P<number>\b\d[\d_]*(?:\.\d+)?\b)
  | (?P<name>[A-Za-z_]\w*)
  | (?P<ws>\s+)
  | (?P<other>.)
    """,
    re.X,
)


def highlight(code):
    """Return a list of HTML strings, one per line, with span classes for tokens."""
    lines = [""]
    prev_name = None
    for m in TOKEN_RE.finditer(code):
        kind = m.lastgroup
        text = m.group()
        cls = None
        if kind == "comment":
            cls = "c"
        elif kind == "string":
            cls = "s"
        elif kind == "decorator":
            cls = "d"
        elif kind == "number":
            cls = "n"
        elif kind == "name":
            if text in KEYWORDS:
                cls = "k"
            elif prev_name in ("def", "class"):
                cls = "f"
            elif text in BUILTINS:
                cls = "b"
        if kind == "name":
            prev_name = text
        elif kind != "ws":
            prev_name = None
        pieces = text.split("\n")
        for i, piece in enumerate(pieces):
            if i:
                lines.append("")
            if piece:
                esc = html.escape(piece, quote=False)
                lines[-1] += f'<span class="{cls}">{esc}</span>' if cls else esc
    return lines


BLOCK_RE = re.compile(r"<code-block\s+([^>]*)>\n?(.*?)\n?[ \t]*</code-block>", re.S)
ATTR_RE = re.compile(r'(\w+)="([^"]*)"')
problems = []


def find_range(file_lines, block_lines, start_hint=0):
    """Locate block_lines inside file_lines ignoring surrounding whitespace; 1-based start."""
    n = len(block_lines)
    stripped = [l.strip() for l in block_lines]
    if not any(stripped):
        return None
    order = list(range(len(file_lines) - n + 1))
    if start_hint:
        order.sort(key=lambda i: abs(i + 1 - start_hint))
    for i in order:
        if [l.strip() for l in file_lines[i : i + n]] == stripped:
            return i + 1
    return None


def render_block(m, part):
    attrs = dict(ATTR_RE.findall(m.group(1)))
    file = attrs.get("file", "")
    lines_attr = attrs.get("lines", "")
    body = m.group(2)
    block_lines = body.split("\n")
    # Drop common indentation only if every non-empty line shares it and the file disagrees.
    path = ROOT / file
    if not path.exists():
        problems.append(f"[{part}] file not found: {file}")
        return f'<pre class="broken">missing file {html.escape(file)}</pre>'
    file_lines = path.read_text(encoding="utf-8").split("\n")
    try:
        start, end = (int(x) for x in lines_attr.split("-"))
    except ValueError:
        start = end = 0
    expected = file_lines[start - 1 : end] if start else []
    if [l.rstrip() for l in expected] != [l.rstrip() for l in block_lines]:
        # Agents sometimes indent the block body or misnumber it: relocate by content.
        s = find_range(file_lines, block_lines, start)
        if s is None:
            problems.append(f"[{part}] verbatim mismatch: {file} lines={lines_attr}")
            if not expected:
                return f'<pre class="broken">unverifiable block {html.escape(file)} {lines_attr}</pre>'
            block_lines = expected
        else:
            e = s + len(block_lines) - 1
            if (s, e) != (start, end):
                problems.append(f"[{part}] lines corrected: {file} {lines_attr} -> {s}-{e}")
            start, end = s, e
            block_lines = file_lines[start - 1 : end]
    else:
        block_lines = expected
    code = "\n".join(block_lines)
    rendered = highlight(code)
    rows = []
    for i, line_html in enumerate(rendered):
        n = start + i
        rows.append(
            f'<span class="line" data-n="{n}"><span class="ln">{n}</span>'
            f'<span class="src">{line_html}</span></span>'
        )
    lib = file.startswith(".venv/")
    shown = file
    if lib:
        shown = file.replace(".venv/lib/python3.12/site-packages/", "site-packages/")
    cap = (
        f'<figcaption><span class="path">{html.escape(shown)}</span>'
        f'<span class="range">{start}–{end}줄</span>'
        + ('<span class="lib">설치 라이브러리</span>' if lib else "")
        + f'<a class="open src" data-file="{html.escape(file)}" data-line="{start}" href="#">열기</a>'
        "</figcaption>"
    )
    return (
        f'<figure class="code" data-file="{html.escape(file)}" data-start="{start}" data-end="{end}">'
        f"{cap}<pre><code>" + "".join(rows) + "</code></pre></figure>"
    )


QUIZ_RE = re.compile(r'<script type="application/json" class="quiz"([^>]*)>(.*?)</script>', re.S)


def check_quiz(m, part):
    attrs = dict(ATTR_RE.findall(m.group(1)))
    try:
        items = json.loads(m.group(2))
    except json.JSONDecodeError as e:
        problems.append(f"[{part}] quiz JSON invalid ({attrs}): {e}")
        return m.group(0)
    for i, q in enumerate(items):
        if not isinstance(q.get("options"), list) or len(q["options"]) != 4:
            problems.append(f"[{part}] quiz {attrs} item {i}: needs exactly 4 options")
        if not isinstance(q.get("answer"), int) or not 0 <= q.get("answer", -1) <= 3:
            problems.append(f"[{part}] quiz {attrs} item {i}: answer out of range")
        for key in ("q", "explain", "ref"):
            if not q.get(key):
                problems.append(f"[{part}] quiz {attrs} item {i}: missing {key}")
    return m.group(0)


SUMMARIES = {}
for _f in TOUR.glob("summaries-*.json"):
    SUMMARIES.update(json.loads(_f.read_text(encoding="utf-8")))
SECTION_RE = re.compile(r'(<section class="lesson" id="([^"]+)"[^>]*>)(.*?)(</section>)', re.S)


def inject_summaries(text, part):
    """Add the 3-line summary after the lead and the one-line takeaway before the ref."""

    def one(m):
        sid = m.group(2)
        body = m.group(3)
        data = SUMMARIES.get(sid)
        if not data:
            problems.append(f"[{part}] no summary for {sid}")
            return m.group(0)
        bullets = "".join(f"<li>{html.escape(x)}</li>" for x in data["bullets"])
        summary = f'<div class="summary"><h4>이 섹션에서 알 것</h4><ul>{bullets}</ul></div>'
        take = f'<p class="takeaway"><b>한 줄 정리</b>{html.escape(data["takeaway"])}</p>'
        if '<p class="lead">' in body:
            body = re.sub(r'(<p class="lead">.*?</p>)', lambda mm: mm.group(1) + summary, body, count=1, flags=re.S)
        else:
            body = re.sub(r"(</h2>)", r"\1" + summary, body, count=1)
        if '<p class="ref">' in body:
            idx = body.rfind('<p class="ref">')
            body = body[:idx] + take + body[idx:]
        else:
            body = body + take
        return m.group(1) + body + m.group(4)

    return SECTION_RE.sub(one, text)


def section_ids(text):
    return re.findall(r'<section class="lesson" id="([^"]+)"', text)


def embed_json(data):
    """JSON safe inside <script>: escaping every '<' rules out both '</script>' and '<!--' tricks."""
    return json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")


STAGE_KEYS = set(re.findall(r"\{ key: '([\w-]+)'", (TOUR / "shell.html").read_text(encoding="utf-8")))
KINDS = {"backend", "ml", "eval", "frontend", "infra", "docs"}


def check_history(data):
    """Every commit must exist, every stage key must be a journey stage, every file must exist at that commit."""
    import subprocess

    def git_ok(*args):
        return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, check=False).returncode == 0

    if not git_ok("cat-file", "-e", data["mvp"]["commit"] + "^{commit}"):
        problems.append(f"[history] unknown MVP commit {data['mvp']['commit']}")
    if len(data["mvp"]["then"]) != len(data["mvp"]["now"]):
        problems.append("[history] mvp.then and mvp.now differ in length")
    for era in data["eras"]:
        for it in era["items"]:
            tag = f"[history] {it.get('pr') or it['commit']}"
            for s in it["stages"]:
                if s not in STAGE_KEYS:
                    problems.append(f"{tag}: unknown stage {s}")
            if it["kind"] not in KINDS:
                problems.append(f"{tag}: unknown kind {it['kind']}")
            if not git_ok("cat-file", "-e", it["commit"] + "^{commit}"):
                problems.append(f"{tag}: unknown commit {it['commit']}")
                continue
            for f in it["files"]:
                if not git_ok("cat-file", "-e", f"{it['commit']}:{f}"):
                    problems.append(f"{tag}: {f} does not exist at {it['commit']}")


def main():
    shell = (TOUR / "shell.html").read_text(encoding="utf-8")
    tracks = {"fastapi": [], "langchain": []}
    seen = set()
    for part in PARTS:
        p = TOUR / "parts" / f"{part}.html"
        if not p.exists():
            problems.append(f"missing part {part}")
            continue
        text = p.read_text(encoding="utf-8")
        for sid in section_ids(text):
            if sid in seen:
                problems.append(f"[{part}] duplicate section id {sid}")
            seen.add(sid)
        text = BLOCK_RE.sub(lambda m: render_block(m, part), text)
        text = QUIZ_RE.sub(lambda m: check_quiz(m, part), text)
        if "<code-block" in text:
            problems.append(f"[{part}] unparsed <code-block> remains")
        track = "fastapi" if part.startswith("fastapi") else "langchain"
        text = inject_summaries(text, part)
        tracks[track].append(text)
    out = shell.replace("{{FASTAPI}}", "\n".join(tracks["fastapi"])).replace(
        "{{LANGCHAIN}}", "\n".join(tracks["langchain"])
    )
    glossary = TOUR / "glossary.json"
    if glossary.exists():
        data = json.loads(glossary.read_text(encoding="utf-8"))
        block = '<script type="application/json" id="glossary">' + embed_json(data) + "</script>"
        out = out.replace("<script>\n(function () {", block + "\n<script>\n(function () {", 1)
    else:
        problems.append("glossary.json missing (tooltips disabled)")
    history = TOUR / "history.json"
    if history.exists():
        data = json.loads(history.read_text(encoding="utf-8"))
        check_history(data)
        block = '<script type="application/json" id="history">' + embed_json(data) + "</script>"
        out = out.replace("<script>\n(function () {", block + "\n<script>\n(function () {", 1)
    else:
        problems.append("history.json missing (history tab empty)")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(out, encoding="utf-8")
    print(f"wrote {OUT} ({len(out.encode('utf-8')) // 1024} KB, {len(seen)} sections)")
    # Same page served by the Vercel frontend at /learn (frontend/public is static).
    PUBLIC = ROOT / "frontend/public/learn/index.html"
    PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC.write_text(out, encoding="utf-8")
    print(f"wrote {PUBLIC}")
    for p in problems:
        print("PROBLEM:", p)
    hard = [p for p in problems if "lines corrected" not in p]
    sys.exit(1 if hard else 0)


if __name__ == "__main__":
    main()

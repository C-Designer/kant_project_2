"""Move every line reference in the learning page after repository files change.

Usage: python3 -I docs/learn/src/remap_lines.py <git-rev>   (e.g. main or HEAD~1)

For each repository file whose content differs from <git-rev>, a diff maps old line numbers
to new ones. The script rewrites, in parts/*.html and shell.html:
  - <code-block file="F" lines="A-B"> ranges,
  - <li data-line="N"> notes under a code block of F,
  - <a class="src" data-file="F" data-line="N">F:N</a> links,
  - plain "path/to/F:N" references (quiz "ref" fields, simulator steps).
Lines that were edited or deleted are reported so their prose can be checked by hand.
Run build.py afterwards; it verifies every excerpt against the files verbatim.
"""

import difflib
import re
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
ROOT = SRC.parents[2]
FILES = [*sorted((SRC / "parts").glob("*.html")), SRC / "shell.html"]
REPO_PATH = r"(?:backend|tests|frontend|scripts|deploy|docs)/[\w./\[\]-]+?\.(?:py|ts|tsx|md|json|toml)"


def line_map(rev, path):
    try:
        old = subprocess.run(
            ["git", "show", f"{rev}:{path}"], cwd=ROOT, capture_output=True, check=True
        ).stdout.decode("utf-8").split("\n")
    except subprocess.CalledProcessError:
        return None
    new = (ROOT / path).read_text(encoding="utf-8").split("\n")
    if old == new:
        return None
    mapping, touched = {}, set()
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        for k in range(i1, i2):
            if tag == "equal":
                mapping[k + 1] = j1 + (k - i1) + 1
            else:
                mapping[k + 1] = min(j1 + (k - i1), max(j1, j2 - 1)) + 1
                touched.add(k + 1)
    return mapping, touched


def main(rev):
    maps, warnings = {}, []

    def remap(path, n, where):
        if path not in maps:
            maps[path] = line_map(rev, path)
        if not maps[path]:
            return n
        mapping, touched = maps[path]
        if n in touched:
            warnings.append(f"{where}: {path}:{n} points at an edited line, check the prose")
        return mapping.get(n, n)

    for f in FILES:
        text = f.read_text(encoding="utf-8")
        out, current, pos = [], None, 0
        token = re.compile(
            r'<code-block file="(?P<cf>[^"]+)" lines="(?P<a>\d+)-(?P<b>\d+)">'
            r'|<li data-line="(?P<li>\d+)"'
            r'|<a class="src" data-file="(?P<af>[^"]+)" data-line="(?P<al>\d+)"'
            rf"|(?<![\w/.])(?P<pf>{REPO_PATH}):(?P<pl>\d+)"
        )
        for m in token.finditer(text):
            out.append(text[pos : m.start()])
            pos = m.end()
            where = f.name
            if m.group("cf"):
                current = m.group("cf")
                a, b = remap(current, int(m.group("a")), where), remap(current, int(m.group("b")), where)
                out.append(f'<code-block file="{current}" lines="{a}-{b}">')
            elif m.group("li"):
                n = int(m.group("li"))
                out.append(f'<li data-line="{remap(current, n, where) if current else n}"')
            elif m.group("af"):
                af = m.group("af")
                out.append(f'<a class="src" data-file="{af}" data-line="{remap(af, int(m.group("al")), where)}"')
            else:
                pf = m.group("pf")
                out.append(f"{pf}:{remap(pf, int(m.group('pl')), where)}")
        out.append(text[pos:])
        new_text = "".join(out)
        if new_text != text:
            f.write_text(new_text, encoding="utf-8")
            print("updated", f.relative_to(ROOT))
    changed = sorted(p for p, m in maps.items() if m)
    print("files with moved lines:", ", ".join(changed) or "none")
    for w in sorted(set(warnings)):
        print("CHECK:", w)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "HEAD")

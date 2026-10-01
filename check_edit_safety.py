"""
check_edit_safety.py (v2) -- did an editing pass (e.g. /unslop) change anything it must not change?
===================================================================================================
    python check_edit_safety.py  <folder_BEFORE>  <folder_AFTER>

Compares every .tex file present in BOTH folders (files missing from AFTER are reported only if you pass --all).
Protected, per file:
  * whole BLOCKS must be identical (whitespace aside): table, table*, figure, figure*, equation, equation*, align, align*, quote, \\[ ... \\]
  * all numbers (digit sequences with their % sign)
  * \\cite / \\citeA / \\ref / \\eqref / \\label / \\input / \\includegraphics keys
  * math segments $...$
  * environments (\\begin counts) and all headings (\\chapter, \\section, \\subsection, \\paragraph)
  * dashes: '--' (ranges, Xie--Beni) and '---' (empty table cells)
  * LaTeX quotes ``...'' and any NEW straight double quote "
  * footnotes (\\footnote{...}) text
Prints OK or CHECK per file and the exact items that differ. Exit code 1 if anything is flagged.
"""
import re
import sys
from collections import Counter
from pathlib import Path

BLOCK_ENVS = ["table*", "table", "figure*", "figure", "equation*", "equation", "align*", "align", "quote"]


def strip_comments(t):
    return re.sub(r"(?<!\\)%.*", "", t)


def norm(x):
    return re.sub(r"\s+", " ", x).strip()


def blocks(t):
    out = []
    for env in BLOCK_ENVS:
        e = re.escape(env)
        out += [norm(m.group(0)) for m in re.finditer(r"\\begin\{" + e + r"\}.*?\\end\{" + e + r"\}", t, flags=re.S)]
    out += [norm(m.group(0)) for m in re.finditer(r"\\\[.*?\\\]", t, flags=re.S)]
    return out


def items(t):
    t = strip_comments(t)
    out = {}
    out["protected blocks"] = Counter(blocks(t))
    plain = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?\{[^}]*\}", " ", t)
    out["numbers"] = Counter(re.findall(r"\d[\d,]*\.?\d*%?|\.\d+", plain))
    out["cite/ref/label"] = Counter(re.findall(r"\\(?:cite|citeA|ref|eqref|label|input|includegraphics)(?:\[[^\]]*\])?\{[^}]*\}", t))
    out["math"] = Counter(norm(m) for m in re.findall(r"\$[^$]*\$", t))
    out["environments"] = Counter(re.findall(r"\\begin\{([^}]*)\}", t))
    out["headings"] = Counter(norm(m) for m in re.findall(r"\\(?:chapter|section|subsection|paragraph)\*?\{[^}]*\}", t))
    out["footnotes"] = Counter(norm(m) for m in re.findall(r"\\footnote\{[^}]*\}", t))
    out["dashes"] = Counter({"---": len(re.findall(r"(?<!-)---(?!-)", t)), "--": len(re.findall(r"(?<!-)--(?!-)", t))})
    out["quotes"] = Counter({"``": t.count("``"), "''": t.count("''"), '"': t.count('"')})
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    before, after = Path(args[0]), Path(args[1])
    show_missing = "--all" in sys.argv
    bad, checked = 0, 0
    for fa in sorted(before.glob("*.tex")):
        fb = after / fa.name
        if not fb.exists():
            if show_missing:
                print(f"{fa.name}: not in {after} (skipped)")
            continue
        checked += 1
        ia, ib = items(fa.read_text(encoding="utf-8")), items(fb.read_text(encoding="utf-8"))
        problems = []
        for k in ia:
            lost, gained = ia[k] - ib[k], ib[k] - ia[k]
            if lost or gained:
                short = lambda c: {(x[:90] + "...") if len(x) > 90 else x: v for x, v in c.items()}
                problems.append((k, short(lost), short(gained)))
        if problems:
            bad += 1
            print(f"{fa.name}: CHECK")
            for k, lost, gained in problems:
                print(f"    {k}: removed {lost or '-'} | added {gained or '-'}")
        else:
            print(f"{fa.name}: OK")
    print(f"\nRESULT: {checked} file(s) compared;", "all protected items unchanged" if bad == 0 else f"{bad} file(s) to inspect before accepting")
    sys.exit(1 if bad else 0)


main()

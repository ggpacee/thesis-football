"""
check_claim_words.py -- did an editing pass change how STRONGLY something is claimed?
=====================================================================================
    python check_claim_words.py  <folder_BEFORE>  <folder_AFTER>   [--max 60]

For every .tex file in both folders: (1) counts hedge and verdict words before/after and lists any difference; (2) pairs each changed
sentence with its original and prints only the pairs in which a hedge/verdict word or a number appears or disappears. These are the
sentences to READ. Everything else that changed is wording only (filler, vocabulary, sentence length) and can be skimmed.
"""
import difflib
import re
import sys
from collections import Counter
from pathlib import Path

TERMS = ["weak", "weakly", "small", "specification-dependent", "robust", "significan", "associat", "conditional", "exploratory", "pre-specified",
         "fragile", "absent", "largely", "mostly", "partly", "only", "at most", "at least", "no ", "not ", "never", "cannot", "may ", "might", "could",
         "suggest", "indicat", "consistent with", "appears", "seems", "likely", "possible", "tentative", "about", "approximately", "roughly",
         "clearly", "strongly", "substantial", "considerable", "important", "important", "demonstrat", "prove", "show", "find", "found", "evidence",
         "favourable", "typical", "noisy", "noise", "attenuat", "caveat", "limitation", "unreliable", "stable", "volatile", "persist"]


def clean(t):
    t = re.sub(r"(?<!\\)%.*", "", t)
    t = re.sub(r"\\begin\{(table\*?|figure\*?|equation\*?|align\*?)\}.*?\\end\{\1\}", " ", t, flags=re.S)
    return t


def sentences(t):
    t = re.sub(r"\s+", " ", clean(t))
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\\$])", t)
    return [p.strip() for p in parts if len(p.strip()) > 25]


def term_counts(s):
    low = s.lower()
    return Counter({w: low.count(w) for w in TERMS if low.count(w)})


def nums(s):
    return Counter(re.findall(r"\d[\d,]*\.?\d*%?", s))


args = [a for a in sys.argv[1:] if not a.startswith("--")]
before, after = Path(args[0]), Path(args[1])
maxshow = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 60
total_queue = 0
for fa in sorted(before.glob("*.tex")):
    fb = after / fa.name
    if not fb.exists():
        continue
    sa, sb = sentences(fa.read_text(encoding="utf-8")), sentences(fb.read_text(encoding="utf-8"))
    ta, tb = term_counts(" ".join(sa)), term_counts(" ".join(sb))
    diff = {w: (ta.get(w, 0), tb.get(w, 0)) for w in set(ta) | set(tb) if ta.get(w, 0) != tb.get(w, 0)}
    seta = set(sa)
    changed_a = [s for s in sa if s not in set(sb)]
    changed_b = [s for s in sb if s not in seta]
    queue = []
    used = set()
    for s in changed_a:
        cand = difflib.get_close_matches(s, [x for x in changed_b if x not in used], n=1, cutoff=0.45)
        if cand:
            used.add(cand[0])
            if term_counts(s) != term_counts(cand[0]) or nums(s) != nums(cand[0]):
                queue.append((s, cand[0]))
        else:
            queue.append((s, "(DELETED or merged)"))
    for s in changed_b:
        if s not in used and not any(difflib.SequenceMatcher(None, s, a).ratio() > 0.45 for a in changed_a):
            queue.append(("(ADDED)", s))
    total_queue += len(queue)
    print(f"\n=== {fa.name}: {len(changed_a)} sentence(s) changed, {len(queue)} to read; hedge/verdict word count differences: {dict(sorted(diff.items())) or 'none'}")
    for old, new in queue[:maxshow]:
        print(f"  BEFORE: {old}\n  AFTER : {new}\n")
print(f"\nTOTAL sentences to read: {total_queue}")

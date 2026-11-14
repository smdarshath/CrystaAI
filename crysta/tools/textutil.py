"""Small text helpers used for extractive (non-AI) summarising and matching."""
from __future__ import annotations

import re
from collections import Counter

STOP = set("""a an the and or but if then of to in on at for from by with about as is are was were be been being do does did
i me my you your we our they them he she it its this that these those what which who whom how why when where can could should
would will shall may might must not no yes so than too very just also into out up down over under again more most some any each
other such only own same there here have has had having tell give show please find search look get make say said""".split())
WORD = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9'\-]*")


def tokens(text):
    return [w.lower() for w in WORD.findall(text)]


def stem(w):
    return w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w


def keywords(text):
    return [stem(w) for w in tokens(text) if w not in STOP and len(w) > 1]


def split_sentences(text):
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"“\'(])', text)
    return [p.strip() for p in parts if 40 <= len(p.strip()) <= 400]


def score_sentence(sentence, terms):
    terms = set(terms)
    if not terms:
        return 0.0
    return len(set(keywords(sentence)) & terms) / len(terms)


def top_sentences(text, terms, n=2, min_score=0.2):
    scored = [(score_sentence(s, terms), i, s) for i, s in enumerate(split_sentences(text))]
    scored = [x for x in scored if x[0] >= min_score]
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [(s, sc) for sc, _, s in scored[:n]]


def chunk_words(text, size=28):
    words = text.split()
    return [" ".join(words[i:i + size]) for i in range(0, len(words), size)]


def frequency_summary(chunks, n=5):
    """Pick the n most 'central' chunks by keyword frequency, keep original order. Returns indices."""
    freq = Counter(w for c in chunks for w in keywords(c))
    scored = []
    for i, c in enumerate(chunks):
        ks = keywords(c)
        if len(ks) >= 4:
            scored.append((sum(freq[w] for w in set(ks)) / (len(ks) ** 0.5), i))
    scored.sort(reverse=True)
    return sorted(i for _, i in scored[:n])


def overlap(a, b):
    sa, sb = set(keywords(a)), set(keywords(b))
    return len(sa & sb) / max(1, min(len(sa), len(sb)))

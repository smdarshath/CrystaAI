"""Tamil-script and Tanglish (Tamil written in English letters) -> canonical English tokens.
The result feeds the same intent rules as English, so every agent understands all three. Lexicon-based and
deliberately small: unknown words pass through unchanged and are never "corrected"."""
from __future__ import annotations

import re

TAMIL_RE = re.compile(r"[\u0B80-\u0BFF]")
TAMIL_STEMS = {  # stem -> English (longest stems are applied first)
    "உருவாக்கினார்": "made", "உருவாக்கியவர்": "made", "உருவாக்கி": "made", "நினைவூட்டு": "remind", "நினைவில்": "remember", "மறந்து": "forget",
    "கண்டுபிடி": "find", "கணக்கிடு": "calculate", "கணக்கு": "calculate", "விளக்கு": "explain", "சரி செய்": "fix", "சரிசெய்": "fix",
    "ஆராய்ச்சி": "research", "உதவித்தொகை": "scholarship", "மடிக்கணினி": "laptop", "கணினி": "computer", "கோப்புறை": "folder", "கோப்பு": "file",
    "அமைப்புகள்": "settings", "நினைவகம்": "memory", "சேமிப்பு": "storage", "மின்கலம்": "battery", "பேட்டரி": "battery", "ரேம்": "ram",
    "எவ்வளவு": "how much", "எப்படி": "how", "எங்கே": "where", "எப்போது": "when", "என்ன": "what", "யார்": "who", "தேடு": "search",
    "திற": "open", "காட்டு": "show", "காண்பி": "show", "சொல்": "tell", "மாற்று": "change", "அழி": "delete", "பேசு": "speak",
    "உன்னை": "you", "உங்கள்": "your", "உனது": "your", "உன்": "your", "எனது": "my", "என்": "my", "பெயர்": "name",
    "குறிப்புகள்": "notes", "குறிப்பு": "note", "திட்டம்": "plan", "போட்டிகள்": "competitions", "போட்டி": "competition", "மாணவர்": "student",
    "முகப்பு": "home", "குரல்": "voice", "தமிழ்": "tamil", "ஆங்கிலம்": "english", "வணக்கம்": "hello", "நன்றி": "thanks", "வீடியோ": "video",
    "நேரம்": "time", "தேதி": "date", "இன்று": "today", "அறிவியல்": "science", "கணிதம்": "math", "வானியல்": "astronomy",
    "சுற்றுப்பாதை": "orbit", "இயக்கவியல்": "mechanics", "போ": "go", "செய்": "",
}
STRONG = {"pannu", "pannunga", "panu", "pannidu", "pannuda", "seiyu", "thedu", "thedunga", "theduda", "kandupidi", "kaatu", "kaattu",
          "kaatunga", "sollu", "solunga", "enna", "evlo", "evvalavu", "irukku", "iruku", "irukka", "yaaru", "yaar", "yaru", "eppadi", "epdi",
          "venum", "vendum", "mudiyuma", "pesu", "pesunga", "thira", "thirakka", "thiranga", "maathu", "matru", "maatru", "unga", "unna", "enakku"}
TANGLISH = {
    "pannu": "", "pannunga": "", "panu": "", "pannidu": "", "pannuda": "", "seiyu": "", "romba": "", "konjam": "", "dhan": "", "thaan": "", "da": "", "ba": "",
    "thedu": "search", "thedunga": "search", "theduda": "search", "theduku": "search", "kandupidi": "find", "kandupidinga": "find", "kandupidichu": "find",
    "thira": "open", "thirakka": "open", "thiranga": "open", "thirandhu": "open", "kaatu": "show", "kaattu": "show", "kaatunga": "show", "kaaturu": "show",
    "sollu": "tell", "solunga": "tell", "vilakku": "explain", "vilakkunga": "explain", "sari": "fix", "maathu": "change", "matru": "change", "maatru": "change",
    "azhi": "delete", "alli": "delete", "ninaivootu": "remind", "nyabagam": "remind", "gnabagam": "remind", "ninaivupaduthu": "remind",
    "vachuko": "remember", "vechuko": "remember", "vachukko": "remember", "marandhuru": "forget", "marandhudu": "forget",
    "kanakku": "calculate", "kanaku": "calculate", "enna": "what", "yenna": "what", "edhu": "what", "yaaru": "who", "yaar": "who", "yaru": "who",
    "eppadi": "how", "epdi": "how", "enga": "where", "engae": "where", "eppo": "when", "eppodhu": "when", "evlo": "how much", "evvalavu": "how much", "evalo": "how much",
    "un": "your", "unga": "your", "ungal": "your", "unnoda": "your", "unaku": "you", "unakku": "you", "unna": "you", "unnai": "you", "ungalai": "you",
    "en": "my", "ennoda": "my", "enakku": "me", "ennai": "me", "peyar": "name", "per": "name",
    "senjadhu": "made", "senjavar": "made", "senjathu": "made", "uruvakkinadhu": "made", "uruvaakkinadhu": "made", "uruvaakinaar": "made", "panninadhu": "made", "pannadhu": "made",
    "irukku": "is", "iruku": "is", "irukka": "is", "pesu": "speak", "pesunga": "speak", "padi": "read", "ezhudhu": "write", "eludhu": "write", "odu": "run", "oodu": "run",
    "po": "go", "ponga": "go", "poo": "go", "pogalam": "go", "ku": "", "kku": "", "la": "", "il": "",
    "potti": "competition", "pottigal": "competitions", "pottikal": "competitions", "maanavar": "student", "maanavargal": "students", "udhavithogai": "scholarship",
    "thittam": "plan", "tittam": "plan", "kurippu": "note", "kurippugal": "notes", "ninaivagam": "memory", "kural": "voice", "kuralai": "voice",
    "kanini": "computer", "veedu": "home", "mugappu": "home", "nerem": "time", "neram": "time", "thethi": "date", "inniku": "today", "indru": "today", "vanaviyal": "astronomy",
    "ariviyal": "science", "kanitham": "math", "venum": "want", "vendum": "want", "mudiyuma": "can you", "pls": "please",
}
VERBS = {"search", "find", "open", "show", "tell", "explain", "fix", "change", "delete", "remind", "remember", "forget", "calculate", "speak",
         "read", "write", "run", "go", "plan", "check", "create", "make", "play"}
Q_WORDS = {"what", "who", "how", "where", "when", "which", "why", "is", "are", "can", "do", "does"}


_AMBIGUOUS = {"un", "en", "per", "po", "la", "il", "da", "ba", "sari", "padi", "odu", "poo", "inniku", "indru"}
STRONG |= {k for k in TANGLISH if k not in _AMBIGUOUS}
STRONG |= {"ku", "kku"}


def is_tamil_or_tanglish(text):
    if TAMIL_RE.search(text):
        return True
    return any(w.strip(".,!?;:").lower() in STRONG for w in text.split())


def translate(text):
    """Return English-token text. English input is returned unchanged."""
    if not is_tamil_or_tanglish(text):
        return text
    t = text
    for stem in sorted(TAMIL_STEMS, key=len, reverse=True):
        if stem in t:
            t = t.replace(stem, f" {TAMIL_STEMS[stem]} ")
    t = TAMIL_RE.sub(" ", t)  # leftover Tamil suffixes/particles
    out = []
    for w in t.split():
        bare = w.strip(".,!?;:").lower()
        mapped = TANGLISH.get(bare, w)
        if mapped:
            out.append(mapped)
    # Tamil is verb-final ("student competitions search") -> English verb-first ("search student competitions")
    flat = " ".join(out).split()
    tail = [x for x in flat if x != "please"]
    if len(tail) > 1 and tail[-1] in VERBS and tail[0] not in VERBS and tail[0] not in Q_WORDS:
        i = len(flat) - 1 - flat[::-1].index(tail[-1])
        flat = [flat[i]] + flat[:i] + flat[i + 1:]
    return " ".join(flat)

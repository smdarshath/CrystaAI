"""Understanding informal / misspelled English. Never 'corrects' the user: it normalises internally."""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

from . import lex
from .tools import calculator

TYPOS = {"vedio": "video", "vedios": "videos", "videoes": "videos", "yutube": "youtube", "youtub": "youtube", "utube": "youtube",
         "serch": "search", "seach": "search", "srch": "search", "opn": "open", "opne": "open", "setings": "settings",
         "settngs": "settings", "calcualte": "calculate", "calculat": "calculate", "reserch": "research", "reaserch": "research",
         "knowlege": "knowledge", "wether": "weather", "chrme": "chrome", "fiel": "file", "fies": "files", "foler": "folder",
         "tlel": "tell", "pleas": "please", "websit": "website", "wesite": "website", "premuim": "premium", "premimum": "premium"}
SLANG = {"yt": "youtube", "vid": "video", "vids": "videos", "pls": "please", "plz": "please", "abt": "about", "wat": "what",
         "wht": "what", "u": "you", "ur": "your", "r": "are", "bro": "", "bruh": "", "dude": "", "bcoz": "because", "coz": "because",
         "evrthing": "everything", "everythin": "everything", "lappy": "laptop", "pc": "computer", "info": "information",
         "gonna": "going to", "wanna": "want to", "gimme": "give me", "lemme": "let me", "whats": "what is", "hows": "how is",
         "dont": "do not", "cant": "can not", "wont": "will not", "im": "i am", "ya": "you", "thx": "thanks", "tmrw": "tomorrow",
         "sec": "second", "ok": "", "okay": "", "hey": "hey", "gud": "good", "nd": "and", "n": "and", "wid": "with", "da": "the"}
VOCAB = ["search", "research", "calculate", "youtube", "videos", "settings", "agents", "remember", "reminder", "diagnose",
         "screenshot", "website", "computer", "download", "weather", "explain", "translate", "knowledge", "memory", "folder"]

def soft(text):
    """Fix only well-known typos, keep case/punctuation (used for extracting arguments like app names)."""
    out = []
    for w in lex.translate(text).split():
        bare = w.strip(".,!?;:")
        fixed = TYPOS.get(bare.lower())
        out.append(w.replace(bare, fixed) if fixed else w)
    return " ".join(out)


ABS_URL = re.compile(r"https?://\S+|\bwww\.\S+", re.I)


AGENT_ALIASES = {
    "zykron": "zykron", "research agent": "zykron", "research": "zykron", "research center": "zykron", "research centre": "zykron",
    "nova": "nova", "coding": "nova", "code editor": "nova", "ide": "nova", "development": "nova", "developer": "nova",
    "astra": "astra", "science": "astra", "science lab": "astra",
    "vega": "vega", "file manager": "vega", "file explorer": "vega", "files app": "vega", "computer control": "vega", "control laptop": "vega",
    "echo": "echo", "voice studio": "echo", "voice settings": "echo", "voice": "echo", "speech settings": "echo",
    "nexus": "nexus", "memory": "nexus", "notes app": "nexus", "archive": "nexus", "notes": "nexus",
    "orion": "orion", "planner": "orion", "kanban": "orion", "project board": "orion", "planning": "orion",
    "volt": "volt", "hardware": "volt", "hardware monitor": "volt", "system monitor": "volt",
    "crysta": "home",
}
_AG_RE = "|".join(sorted((re.escape(k) for k in AGENT_ALIASES), key=len, reverse=True))
ADDRESS = re.compile(r"^(?:hey |ok |okay )?(crysta|zykron|nova|astra|vega|echo|nexus|orion|volt)\b[,:]?\s+(?=\S)", re.I)


@dataclass
class Subtask:
    intent: str
    agent: str
    text: str = ""
    args: dict = field(default_factory=dict)


def normalize(text):
    low = lex.translate(text).lower()
    low = re.sub(r"[^\w\s'%:/.\-+*^()=,@?#&$~\\]", " ", low)
    out = []
    for w in low.split():
        if ABS_URL.match(w) or "/" in w or "\\" in w or re.search(r"\w\.\w", w):
            out.append(w)
            continue
        bare = w.strip(".,!?;:'\"")
        bare = bare.replace("'", "") if bare in ("dont", "cant", "wont", "im") else bare
        if bare in TYPOS:
            bare = TYPOS[bare]
        elif bare in SLANG:
            bare = SLANG[bare]
        elif len(bare) >= 5 and bare.isalpha() and not ({bare, bare + "s", bare.rstrip("s")} & set(VOCAB)):
            m = difflib.get_close_matches(bare, VOCAB, n=1, cutoff=0.86)
            bare = m[0] if m else bare
        if bare:
            out.append(bare)
    return " ".join(out)


UI_WORDS = {"chat": "chat", "conversation": "chat", "settings": "settings", "setting": "settings", "preferences": "settings",
            "agents": "agents", "agent": "agents", "devices": "devices", "research": "zykron", "computer": "vega"}
FOLDERS = {"downloads": "Downloads", "documents": "Documents", "desktop": "Desktop", "pictures": "Pictures", "music": "Music", "videos": "Videos"}
QUESTION_START = re.compile(r"^(what|who|when|where|why|how|which|is|are|does|do|did|can|could|explain|define|tell me)\b")
SCIENCE = re.compile(r"\b(physics|chemistry|biology|math|maths|mathematics|equation|formula|theorem|derivative|integral|voltage|current|resistor|ohm|"
                     r"newton|quantum|relativity|velocity|acceleration|momentum|circuit|capacitor|entropy|atom|molecule|gravity|photon|wavelength|"
                     r"speed of light|planck|boltzmann|black hole|escape velocity|schwarzschild|orbit|orbital|mechanics|thermodynamics|astronomy|planet|galaxy|star|stars|relativity|electromagnet\\w*|kepler|satellite|osmosis|photosynthesis|dna|periodic table|moles?|molarity)\b")
RESEARCH_VERBS = re.compile(r"\b(research|search|look up|lookup|find out|google|latest|news|real answer|verify|fact check|compare|"
                            r"best way|versus|reviews?|true answer|is it true)\b|\bvs\b")


def _clean_topic(text, extra=()):
    t = re.sub(r"\b(please|can you|could you|will you|me|some|the|a|an|about|on|for|of|to|find|search|show|get|give|tell|look|up|"
               r"youtube|video|videos|related|best|top|and|real|answer|is|it|true|research|verify|check|fact)\b", " ", text)
    for e in extra:
        t = re.sub(e, " ", t)
    return " ".join(t.split())


def _research_query(norm):
    t = re.sub(r"^(?:please\s+)?(?:can you\s+|could you\s+)?(?:do\s+(?:a\s+)?)?(research|search(?:\s+for|\s+about|\s+on)?|look up|lookup|find out(?:\s+about)?|google|tell me about|find)\s+", "", norm)
    t = re.split(r"\b(?:and|then)\s+(?:tell|show|explain|give|help)\b", t)[0]
    t = re.sub(r"\b(and\s+)?tell me (the )?(real )?(answer|truth)\b", "", t)
    t = t.strip(" ,.?")
    return "" if t in ("this", "that", "it", "here") else t


def _path_arg(orig):
    m = re.search(r"\b(?:in|of|at|from|inside)\s+(?:my\s+|the\s+)?(.+?)\s*$", orig.strip().rstrip("?."), re.I)
    return m.group(1).strip() if m else None


def classify_part(orig, norm, ctx):
    n, o = norm, soft(orig.strip())
    sub = lambda intent, agent, **a: Subtask(intent, agent, o, a)
    ctx = ctx or {}

    if re.fullmatch(r"(hi+|hello|hey|yo|good (morning|afternoon|evening)|namaste|vanakkam)( crysta)?", n):
        return sub("greet", "crysta")
    if re.search(r"\b(thanks|thank you)\b", n) and len(n.split()) <= 4:
        return sub("thanks", "crysta")
    if re.search(r"\boffline\b", n) and not re.search(r"\b(search|research|find)\b", n):
        return sub("offline", "crysta")
    if re.search(r"\b(what are you|what do you do|tell me about yourself|introduce yourself)\b", n):
        return sub("about", "crysta")

    ma = ADDRESS.match(n)
    if ma and not re.match(r"^(?:hey |ok |okay )?\w+\s*$", n):
        n = ADDRESS.sub("", n, count=1)
        o = ADDRESS.sub("", o, count=1)
    if n in AGENT_ALIASES and n in ("zykron", "nova", "astra", "vega", "echo", "nexus", "orion", "volt"):
        return sub("ui", "crysta", view=AGENT_ALIASES[n])

    # --- identity, time and small talk are answered locally (never a web search)
    if (re.search(r"\bwho\b", n) and re.search(r"\b(made|created|built|developed|designed|programmed|invented|owns)\b", n) and re.search(r"\b(you|your)\b", n)) \
            or re.search(r"\byour (creator|developer|maker|owner|author)\b|\bwho is your (creator|developer|maker)\b", n):
        return sub("identity_creator", "crysta")
    if re.search(r"\b(your name|what are you called|name your|who are you|what should i call you)\b|\byour\b.*\bname\b|\bname\b.*\byour\b", n):
        return sub("identity_name", "crysta")
    if re.search(r"\b(what('?s| is)? the time|what time|current time|time now|time is it|tell me the time)\b|^time$", n):
        return sub("time", "crysta")
    if re.search(r"\b(what('?s| is)? (the )?date|today'?s date|what day|date today|which day|current date)\b|^date$", n):
        return sub("date", "crysta")
    if re.search(r"\b(are you (there|online|offline|listening|working|ok)|can you hear me|do you (speak|understand) (tamil|english|tanglish)|do you need (the )?internet|are you (a )?(bot|ai|robot)|how are you|what can you do)\b", n):
        return sub("smalltalk", "crysta")
    if re.search(r"\b(good (night|bye)|bye|see you|goodbye)\b", n) and len(n.split()) <= 4:
        return sub("smalltalk", "crysta")

    # --- open an agent's own interface
    m = re.search(rf"\b(open|show|go to|launch|switch to|take me to|start|display|see|visit)\b\s+(?:me\s+|my\s+|the\s+|your\s+)*({_AG_RE})\b(?:\s+(?:agent|interface|panel|workspace|app|studio|dashboard|manager|screen|page|mode|center|centre|lab))?\s*$", n)
    if m:
        return sub("ui", "crysta", view=AGENT_ALIASES[m.group(2)])
    if re.search(r"\b(change|switch|set|choose|select)\b.*\b(voice|speech|language)\b|\bvoice (settings|options|controls)\b", n) and not re.search(r"\b(speak|talk)\s+(in\s+)?(tamil|english)\b", n):
        return sub("ui", "crysta", view="echo", note="voice")

    # --- navigation
    if re.search(r"\b(go|back|return|take me)\b.*\bhome\b|^home$|\bclose (this|it|that)\b", n):
        return sub("ui", "crysta", view="home")
    if re.search(r"\b(control|manage)\b.*\b(laptop|computer|pc|system)\b|\bcomputer control\b", n):
        return sub("ui", "crysta", view="vega")
    if re.search(r"\b(connect|pair|link)\b.*\b(phone|mobile|android|device)\b", n):
        return sub("ui", "crysta", view="devices")
    if re.search(r"\b(i want to type|let me type|typing|keyboard mode|text mode)\b", n):
        return sub("ui", "crysta", view="chat")
    m = re.search(r"\b(?:open|show|go to|launch|display|see|switch to)\s+(?:me\s+)?(?:the\s+|my\s+|your\s+)*(chat|conversation|settings?|preferences|agents?|devices|research page|computer)\b", n)
    if m:
        return sub("ui", "crysta", view=UI_WORDS.get(m.group(1).split()[0].rstrip("s") if m.group(1) in ("setting",) else m.group(1).split()[0], "chat"))
    if re.search(r"\b(show|list|see)\b.*\b(nine |9 )?agents\b", n):
        return sub("ui", "crysta", view="agents")

    # --- follow-ups using context
    if re.fullmatch(r"(search|research|find|look)( for)? more( (on|about) (it|this|that))?|tell me more|go deeper|dig deeper|more( information)?", n):
        return sub("follow_more", "zykron")
    if re.fullmatch(r"(open|show|launch) (it|that|this|the first (one|link|result)|link)", n):
        return sub("follow_open", "vega")
    if re.fullmatch(r"(do|try) (that|it)( again)?|go ahead|yes do it", n):
        return sub("follow_do", "crysta")

    # --- calculator / units
    if calculator.extract_expression(o) or (calculator.convert(o) and re.search(r"\d", o)):
        return sub("calc", "astra")

    # --- YouTube
    yid = re.search(r"(https?://(?:www\.)?(?:youtube\.com|youtu\.be)/\S+)", o, re.I)
    if yid:
        return sub("video", "zykron", url=yid.group(1).rstrip(".,)"))
    if re.search(r"\b(that|this|the)\s+(video|vid)\b", n) and re.search(r"\b(saying|say|said|about|summar\w*|transcript|explain|talk\w*|mean)\b", n):
        return sub("video", "zykron", url=None)
    if re.search(r"\b(youtube|videos?)\b", n) and re.search(r"\b(find|search|show|get|suggest|recommend|look|watch|some|best|top|about|related)\b", n):
        topic = _clean_topic(n) or ctx.get("last_topic", "")
        deep = bool(re.search(r"\b(real answer|true|verify|fact|research|is it true|correct|reliable)\b", n))
        return sub("youtube", "zykron", query=topic, verify=deep)

    # --- computer control (VEGA)
    if re.search(r"\b(screenshot|screen shot|capture (my )?screen)\b", n):
        return sub("screenshot", "vega")
    m = re.match(r"\s*(?:please\s+|hey crysta\s+)?(?:run|execute)\s+(?:the\s+)?(?:command\s+)?(.+)", o, re.I)
    if m:
        return sub("run_command", "vega", command=m.group(1).strip().strip("`"))
    m = re.search(r"\b(?:delete|remove)\s+(?:the\s+)?file\s+(.+)", o, re.I)
    if m:
        return sub("files_delete", "vega", path=m.group(1).strip())
    m = re.search(r"\b(?:create|write|make|save)\s+(?:a\s+)?file\s+(?:called\s+|named\s+)?([\w~./\\\-]+)\s+(?:with|containing)\s+(.+)", o, re.I | re.S)
    if m:
        return sub("files_write", "vega", path=m.group(1), content=m.group(2).strip())
    m = re.search(r"\b(?:read|view|cat|show)\s+(?:me\s+)?(?:the\s+)?(?:file\s+)?([\w~./\\:\-]+\.[A-Za-z0-9]{1,6})\b", o, re.I)
    if m and not re.search(r"https?://", o):
        return sub("files_read", "vega", path=m.group(1))
    if re.search(r"\b(?:open|list|show|see|browse|find)\b.*\bprojects? (folder|directory)\b", n):
        return sub("files_list", "vega", path="@project")
    if re.search(r"\b(?:open|list|show|see|browse)\b.*\b(files?|folders?|directory|documents|downloads|desktop)\b", n):
        path = _path_arg(o)
        for k, v in FOLDERS.items():
            if k in n:
                path = path or v
        if path and re.fullmatch(r"(?i)(laptop|computer|pc|system)\s*(files?)?", path):
            path = None
        return sub("files_list", "vega", path=path or "~")
    m = re.search(r"\b(?:open|launch|start|go to)\s+(https?://\S+|www\.\S+|\S+\.(?:com|org|net|in|io|dev|ai|edu|gov)\S*)", o, re.I)
    if m:
        u = m.group(1)
        return sub("open_url", "vega", url=u if u.lower().startswith("http") else "https://" + u)
    m = re.match(r"\s*(?:please\s+|hey crysta\s+)?(?:open|launch|start)\s+(?:up\s+)?(?:the\s+|my\s+)?(.+?)(?:\s+app(?:lication)?)?(?:\s+(?:please|now))?\s*$", o, re.I)
    if m and len(m.group(1)) <= 40:
        return sub("open_app", "vega", name=re.sub(r"\s+", " ", m.group(1)))
    m = re.match(r"\s*type\s+(.+)", o, re.I)
    if m:
        return sub("keyboard", "vega", action="type", text=m.group(1))

    # --- memory / notes (NEXUS)
    if re.search(r"\b(turn on|enable|switch on|activate)\b.*\bmemory\b", n):
        return sub("memory_on", "nexus")
    if re.search(r"\b(turn off|disable|switch off|stop)\b.*\bmemory\b", n):
        return sub("memory_off", "nexus")
    m = re.match(r"\s*(?:please\s+)?remember\b\s*(?:that\s+)?(.+)", o, re.I)
    if m:
        return sub("remember", "nexus", value=m.group(1).strip())
    if re.search(r"\b(what do you remember|what did you save|show (my )?memor(y|ies)|my memories|what do you know about me)\b", n):
        return sub("recall", "nexus")
    m = re.search(r"\b(?:forget|delete memory|clear memory)\b\s*(.*)", n)
    if m:
        return sub("forget", "nexus", target=m.group(1).strip())
    m = re.search(r"\b(?:take|add|make|save|write)\s+(?:a\s+)?note\b[:\s]*(.*)", o, re.I)
    if m:
        return sub("note", "nexus", body=m.group(1).strip())
    m = re.search(r"\b(?:find|search|look for|look up|show|get|recall|retrieve)\b\s+(?:me\s+)?(?:my\s+|the\s+)?(?:saved\s+)?(.*?)\s*\b(?:saved\s+)?(?:notes?|memor(?:y|ies)|saved information)\b", n)
    if m and not re.search(r"\b(web|online|internet|youtube)\b", n):
        q = re.sub(r"\b(my|saved|the|all|me)\b", "", m.group(1)).strip()
        return sub("memory_search", "nexus", query=q)
    if re.search(r"\b(my notes|show notes|list notes)\b", n):
        return sub("note_list", "nexus")

    # --- tasks (ORION)
    m = re.search(r"\bremind me\b\s*(?:to|about|that)?\s*(.+)", o, re.I)
    if m:
        return sub("task_add", "orion", title=m.group(1).strip(), reminder=True)
    m = re.search(r"\badd\s+(?:a\s+)?(?:task|todo|to-do)[:\s]+(.+)", o, re.I)
    if m:
        return sub("task_add", "orion", title=m.group(1).strip(), reminder=False)
    if re.search(r"\b(my tasks|todo list|to-do list|my reminders|show tasks|list tasks|pending tasks)\b", n):
        return sub("task_list", "orion")
    m = re.search(r"\b(?:mark\s+)?(?:task\s+)?#?(\d+)\s+(?:as\s+)?(?:done|complete[d]?|finished)\b", n)
    if m:
        return sub("task_done", "orion", id=int(m.group(1)))
    if re.match(r"\s*(?:please\s+)?(plan|make a plan|create a plan|break down|step by step plan|schedule)\b", n):
        return sub("plan", "orion", goal=re.sub(r"(?i)^\s*(please\s+)?(make a plan|create a plan|plan|break down|step by step plan|schedule)\s*(for|to|out|:)?\s*", "", o))

    # --- voice (ECHO)
    m = re.search(r"\bspeak\s+(?:in\s+)?(tamil|english)\b", n)
    if m:
        return sub("voice", "echo", action="lang", value={"tamil": "ta-IN", "english": "en-IN"}[m.group(1)])
    if re.search(r"\b(mute|stop talking|be quiet|stop speaking|do not speak|voice off|silent mode)\b", n):
        return sub("voice", "echo", action="mute")
    if re.search(r"\b(unmute|voice on|read (it )?aloud|talk to me|speak to me)\b", n):
        return sub("voice", "echo", action="unmute")
    if re.search(r"\b(wake word|hey crysta always|always listening)\b", n):
        return sub("voice", "echo", action="wake")

    # --- hardware (VOLT)
    if re.search(r"\b(diagnos\w*|check (my |the )?(system|laptop|computer|pc|machine)|system (status|health|info\w*)|hardware|health check|troubleshoot|why .*(slow|lag)|(ollama|internet) (running|working)|temperature|cpu|ram|battery|storage|disk space|free space|how much (ram|storage|space|memory)|laptop (status|info))\b", n) \
            and not re.search(r"\b(competition|scholarship|research)\b", n):
        return sub("diagnose", "volt")

    if re.match(r"\s*(please\s+)?(research|search|look up|find out|google)\b", n):   # explicit research verb beats topic words like "website"
        return sub("research", "zykron", query=_research_query(n) or ctx.get("last_topic", ""))

    # --- code (NOVA)
    if re.search(r"(traceback|modulenotfounderror|syntaxerror|enoent|eaddrinuse|npm err|error:|exception)", o, re.I) and len(o) > 20:
        return sub("error", "nova", text=o)
    if re.search(r"\b(inspect|analy[sz]e|scan|look at)\b.*\b(project|folder|directory|codebase|repo)\b", n):
        return sub("project", "nova", path=_path_arg(o) or "~")
    if re.search(r"\b(how (do i|to|can i)|steps to)\b.*\b(run|start|install|setup|set up|launch|deploy)\b", n):
        return sub("howto", "nova")
    if re.search(r"\b(write|build|make|create|code|fix|debug|refactor|improve|redesign)\b.*\b(website|webpage|page|code|script|app|application|"
                 r"function|program|html|css|javascript|python|react|bug|api|component|game|ui)\b|\bpremium\b.*\bwebsite\b|\bwebsite\b.*\bpremium\b", n):
        return sub("code", "nova")

    # --- research / science
    if RESEARCH_VERBS.search(n):
        q = _research_query(n)
        if re.fullmatch(r"(this|that|it|here)?", q):
            q = ctx.get("last_topic", "")
        return sub("research", "zykron", query=q)
    if SCIENCE.search(n):
        return sub("science", "astra", query=n)

    return sub("question" if (QUESTION_START.match(n) or o.endswith("?")) else "chat", "crysta")


SPLIT = re.compile(r"\s*(?:;|\band then\b|\bthen\b|\bafter that\b|\band (?=(?:also )?(?:tell|show|explain|give|help|check|open|run|search|find|write|make|create|remind|remember)\b))\s*", re.I)


def plan(text, ctx=None):
    """Split a message into subtasks. Only splits when each part is itself a recognised request."""
    ctx = ctx or {}
    whole = classify_part(text, normalize(text), ctx)
    parts = [p for p in SPLIT.split(text) if p and p.strip()]
    if len(parts) > 1 and whole.intent not in ("error", "files_write", "run_command"):
        subs = [classify_part(p, normalize(p), ctx) for p in parts[:4]]
        if all(s.intent not in ("chat",) for s in subs) or len([s for s in subs if s.intent != "chat"]) >= 2:
            seen, uniq = set(), []
            for s in subs:
                if s.intent == "chat":
                    continue
                key = (s.intent, tuple(sorted((k, str(v)) for k, v in s.args.items() if k != "query")))
                if s.intent == "research" and any(u.intent == "research" for u in uniq):
                    if s.args.get("query") and not uniq[[u.intent for u in uniq].index("research")].args.get("query"):
                        uniq[[u.intent for u in uniq].index("research")].args["query"] = s.args["query"]
                    continue
                if key not in seen:
                    seen.add(key)
                    uniq.append(s)
            return uniq or [whole]
    return [whole]

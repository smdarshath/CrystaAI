"""YouTube discovery and *legitimately available* captions. Never downloads video.

Everything here is best-effort: YouTube changes its pages and may block or consent-gate requests.
Failures raise NetworkError / TranscriptUnavailable so callers can report honestly.
"""
from __future__ import annotations

import json
import re
import urllib.parse

from ..errors import CrystaError, NetworkError
from .web_search import get_with_retry

COOKIE = {"Cookie": "CONSENT=YES+1; SOCS=CAI"}


class TranscriptUnavailable(CrystaError):
    pass


def parse_video_id(s):
    s = s.strip()
    if re.fullmatch(r"[\w-]{11}", s):
        return s
    m = re.search(r"(?:youtu\.be/|youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|embed/|live/))([\w-]{11})", s)
    return m.group(1) if m else None


def _json_after(html, marker, opener="{"):
    i = html.find(marker)
    if i < 0:
        return None
    j = html.find(opener, i)
    if j < 0:
        return None
    try:
        return json.JSONDecoder().raw_decode(html[j:])[0]
    except ValueError:
        return None


def _walk(node, key):
    if isinstance(node, dict):
        if key in node:
            yield node[key]
        for v in node.values():
            yield from _walk(v, key)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v, key)


def _text(obj):
    if not obj:
        return ""
    if "simpleText" in obj:
        return obj["simpleText"]
    return "".join(r.get("text", "") for r in obj.get("runs", []))


def parse_search_results(html, limit=6):
    data = _json_after(html, "ytInitialData")
    if data is None:
        raise NetworkError("YouTube returned a page I couldn't read (it may be blocking automated search).")
    out = []
    for v in _walk(data, "videoRenderer"):
        vid = v.get("videoId")
        if not vid:
            continue
        out.append({"video_id": vid, "title": _text(v.get("title")), "channel": _text(v.get("ownerText")),
                    "duration": _text(v.get("lengthText")), "views": _text(v.get("viewCountText")),
                    "published": _text(v.get("publishedTimeText")),
                    "snippet": "".join(_text(s) if isinstance(s, dict) else "" for s in [v.get("descriptionSnippet")]),
                    "url": f"https://www.youtube.com/watch?v={vid}", "access": "metadata_only"})
        if len(out) >= limit:
            break
    return out


def search(query, limit=6):
    url = "https://www.youtube.com/results?hl=en&search_query=" + urllib.parse.quote(query)
    return parse_search_results(get_with_retry(url, headers=COOKIE)["text"], limit)


def video_info(url_or_id):
    vid = parse_video_id(url_or_id)
    if not vid:
        raise NetworkError("That doesn't look like a YouTube link.")
    watch = f"https://www.youtube.com/watch?v={vid}"
    r = get_with_retry("https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(watch))
    d = json.loads(r["text"])
    return {"video_id": vid, "title": d.get("title", ""), "channel": d.get("author_name", ""), "url": watch,
            "access": "metadata_only"}


def parse_caption_tracks(html):
    tracks = _json_after(html, '"captionTracks":', "[")
    if not tracks:
        raise TranscriptUnavailable("This video has no captions I can legitimately read.")
    return tracks


def pick_track(tracks, prefs=("en", "ta")):
    for lang in prefs:
        manual = [t for t in tracks if t.get("languageCode", "").startswith(lang) and t.get("kind") != "asr"]
        if manual:
            return manual[0]
    for lang in prefs:
        auto = [t for t in tracks if t.get("languageCode", "").startswith(lang)]
        if auto:
            return auto[0]
    return tracks[0]


def parse_json3(text):
    data = json.loads(text)
    segs = []
    for ev in data.get("events", []):
        line = "".join(s.get("utf8", "") for s in ev.get("segs", [])).replace("\n", " ").strip()
        if line:
            segs.append({"start": round(ev.get("tStartMs", 0) / 1000), "text": line})
    return segs


def transcript(url_or_id, prefs=("en", "ta")):
    vid = parse_video_id(url_or_id)
    if not vid:
        raise TranscriptUnavailable("No valid video link.")
    html = get_with_retry(f"https://www.youtube.com/watch?hl=en&v={vid}", headers=COOKIE)["text"]
    track = pick_track(parse_caption_tracks(html), prefs)
    base = track.get("baseUrl", "")
    if not base.startswith("https://www.youtube.com/"):
        raise TranscriptUnavailable("Caption address looked unsafe, so I skipped it.")
    segs = parse_json3(get_with_retry(base + "&fmt=json3")["text"])
    if not segs:
        raise TranscriptUnavailable("The caption track was empty.")
    return {"video_id": vid, "language": track.get("languageCode"), "auto_generated": track.get("kind") == "asr",
            "segments": segs, "access": "transcript"}

from __future__ import annotations

import re
import time
from urllib.parse import urlparse

from ..errors import Cancelled, CrystaError, ToolUnavailable
from ..tools import textutil
from ..tools.youtube_research import TranscriptUnavailable, parse_video_id
from .base import Agent, AgentResult


def fmt_time(s):
    return f"{s // 60}:{s % 60:02d}"


class Zykron(Agent):
    id, name = "zykron", "ZYKRON"
    description = "Research and web intelligence: live official-source research, competitions & scholarships, YouTube research, verified source links."
    system_instruction = ("You are Zykron, a research agent. Use ONLY the numbered sources provided. Cite like [1]. If sources disagree "
                          "or do not answer the question, say so. Never invent quotes, URLs, transcripts or video content. "
                          "Separate established facts from opinions and uncertain claims.")
    permitted_tools = frozenset({"web_search", "wiki_search", "fetch_page", "youtube_search", "youtube_video_info",
                                 "youtube_transcript", "llm_chat", "llm_status"})

    # ---------- web research (official sources first, Wikipedia only as labelled background)
    OFFICIAL_TLDS = (".gov", ".gov.in", ".nic.in", ".edu", ".ac.in", ".edu.in", ".ac.uk", ".gov.uk", ".int", ".mil", ".edu.au", ".gov.au", ".ac.jp", ".gov.sg", ".gc.ca")
    LOW_TRUST = ("quora.com", "reddit.com", "pinterest.", "facebook.com", "instagram.com", "twitter.com", "x.com", "tiktok.com", "blogspot.", "wordpress.com", "scribd.com", "slideshare.net")
    OPP_WORDS = {"competition", "contest", "olympiad", "hackathon", "scholarship", "fellowship", "grant", "challenge", "internship", "award", "prize", "admission"}
    DEADLINE = re.compile(r"(deadline|last date|closing date|closes?|apply by|due date|registration (?:opens?|closes?|ends?)|applications? (?:open|close|due))", re.I)
    MONTHS = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?"
    DATE = re.compile(rf"\b(\d{{1,2}}(?:st|nd|rd|th)?\s+{MONTHS},?\s+20\d\d|{MONTHS}\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+20\d\d)", re.I)
    REG = re.compile(r"regist|apply|application|enrol|sign[ -]?up|submit", re.I)

    def classify(self, url, query_terms):
        host = urlparse(url).netloc.lower().removeprefix("www.")
        score, tier = 0, "other"
        if any(host.endswith(t) or (t + "/") in host for t in self.OFFICIAL_TLDS):
            score, tier = 4, "official"
        labels = {l for l in re.split(r"[.\-]", host) if len(l) >= 4}
        if any(l in query_terms or any(l in t or t in l for t in query_terms if len(t) >= 4) for l in labels):
            score += 2
            tier = tier if tier == "official" else "organisation"
        if host.endswith((".org", ".org.in", ".ac")) and tier == "other":
            score, tier = score + 1, "organisation"
        if any(b in host for b in self.LOW_TRUST):
            score, tier = score - 2, "community / social"
        if "wikipedia.org" in host:
            score, tier = score - 3, "encyclopedia (background)"
        return host, score, tier

    def gather(self, ctx, query, deep=False):
        errors, unread, year = [], [], time.localtime().tm_year
        terms = textutil.keywords(query)
        opp = bool(set(terms) & self.OPP_WORDS)
        queries = [query] + ([f"{query} official {year}", f"{query} registration deadline {year}"] if opp else ([f"{query} official"] if deep else []))
        hits, seen_url = [], set()
        for q in queries:
            try:
                for h in self.tool(ctx, "web_search", query=q):
                    if h["url"] not in seen_url and "youtube.com" not in h["url"]:
                        seen_url.add(h["url"]); hits.append(h)
            except Cancelled:
                raise
            except CrystaError as e:
                errors.append(f"Web search: {e}")
        core = [t for t in terms if t not in self.OPP_WORDS or len(terms) <= 2] or terms
        ranked = []
        for h in hits:
            host, score, tier = self.classify(h["url"], set(terms))
            rel = textutil.overlap(" ".join(core), h["title"] + " " + h.get("snippet", "")) if core else 0
            if rel >= 0.34 or (tier == "official" and rel >= 0.2):
                ranked.append((score + 3 * rel, host, tier, h, rel))
        dropped = len(hits) - len(ranked)
        ranked.sort(key=lambda r: -r[0])
        limit = (6 if deep else 4) if opp else (5 if deep else 3)
        sources, hosts, fetched = [], set(), 0
        for sc, host, tier, h, rel in ranked:
            if host in hosts:
                continue
            hosts.add(host)
            ctx.check_cancel()
            src = {"title": h["title"], "url": h["url"], "host": host, "tier": tier, "score": round(sc, 1), "relevance": round(rel, 2),
                   "snippet": h.get("snippet", ""), "text": h.get("snippet", ""), "access": "snippet_only", "background": False,
                   "years": [], "fresh": None, "deadlines": [], "reg_links": []}
            if fetched < limit:
                try:
                    page = self.tool(ctx, "fetch_page", url=h["url"])
                    src.update(title=page["title"] or h["title"], url=page["url"], text=page["text"], access="read")
                    self._analyze(src, page.get("links", []), year)
                    fetched += 1
                except Cancelled:
                    raise
                except CrystaError as e:
                    unread.append(f"{h['title'] or host}: {e}")
            sources.append(src)
            if len(sources) >= limit + 3:
                break
        primary_read = [s for s in sources if s["access"] == "read"]
        if not opp and len(primary_read) < 2:  # Wikipedia: background only, never primary
            try:
                for w in self.tool(ctx, "wiki_search", query=query)[:1]:
                    sources.append({"title": w["title"] + " (Wikipedia)", "url": w["url"], "host": "en.wikipedia.org", "tier": "encyclopedia (background)",
                                    "score": -3, "relevance": 1, "snippet": w["text"][:200], "text": w["text"], "access": "read", "background": True,
                                    "years": [], "fresh": None, "deadlines": [], "reg_links": []})
            except Cancelled:
                raise
            except CrystaError as e:
                errors.append(f"Wikipedia background: {e}")
        return {"sources": sources, "errors": errors, "unread": unread, "opportunity": opp, "dropped": dropped, "year": year, "queries": queries}

    def _analyze(self, src, links, year):
        text = src["text"]
        years = sorted({int(y) for y in re.findall(r"\b(20[12]\d)\b", text)})
        src["years"], src["fresh"] = years[-3:], (str(year) in text or str(year + 1) in text)
        for sent in re.split(r"(?<=[.!?\n])\s+", text):
            if self.DEADLINE.search(sent) and len(sent) < 300 and (self.DATE.search(sent) or re.search(r"20\d\d", sent)):
                src["deadlines"].append(sent.strip())
                if len(src["deadlines"]) >= 3:
                    break
        seen = set()
        for l in links:
            if (self.REG.search(l["text"]) or self.REG.search(l["href"])) and l["href"] not in seen and len(src["reg_links"]) < 4:
                seen.add(l["href"]); src["reg_links"].append({"text": l["text"] or "Registration / apply", "href": l["href"]})

    def synthesize(self, ctx, query, ev):
        sources = ev["sources"]
        if not sources:
            msg = "I couldn't find any relevant pages" + (" (the search service was unreachable), so I won't guess an answer." if ev["errors"] else " for that, so I won't guess an answer.")
            return self.fail(msg, limitations=ev["errors"] or ["No relevant results were returned."], data={"cards": [], "query": query})
        terms = textutil.keywords(query)
        tier_rank = {"official": 0, "organisation": 1, "other": 2, "community / social": 3, "encyclopedia (background)": 4}
        cands = []
        for i, s in enumerate(sources, start=1):
            if s["access"] == "read":
                for sent, sc in textutil.top_sentences(s["text"], terms, 2):
                    cands.append((tier_rank.get(s["tier"], 2), -sc, i, sent))
            elif textutil.score_sentence(s["text"], terms) >= 0.3:
                cands.append((tier_rank.get(s["tier"], 2) + .5, -textutil.score_sentence(s["text"], terms), i, s["text"]))
        cands.sort()
        limits = list(ev["errors"]) + [f"Couldn't read: {u}" for u in ev["unread"][:3]]
        if ev["dropped"]:
            limits.append(f"{ev['dropped']} search result(s) were dropped as not relevant to your question.")
        primary = [s for s in sources if s["access"] == "read" and not s["background"]]
        official = [s for s in sources if s["tier"] == "official"]
        out_sources = [{"n": i, "title": s["title"], "url": s["url"], "note": f"{s['tier']} · {s['host']} · " + ("read in full" if s["access"] == "read" else "search snippet only")}
                       for i, s in enumerate(sources, start=1)]
        body, used_llm = None, False
        if ctx.llm.available() and primary:
            block = "\n\n".join(f"[{i}] {s['title']} ({s['tier']})\n{s['text'][:1500]}" for i, s in enumerate(sources, start=1) if s["text"] and not s["background"])
            try:
                body = self.tool(ctx, "llm_chat", messages=[{"role": "user", "content": f"Question: {query}\n\nSources (prefer official ones):\n{block}\n\nAnswer concisely with citations like [1]."}], system=self.system_instruction)
                body = "**Direct answer:** " + body
                used_llm = True
                limits.append("Summary written by a local language model from the sources; verify important claims via the links.")
            except CrystaError as e:
                limits.append(f"Language model unavailable ({e}); used extraction instead.")
        if body is None:
            if cands:
                d = cands[0]
                body = f"**Direct answer:** {d[3]} [{d[2]}]"
                rest, used = [], {d[3]}
                for _, _, i, sent in cands[1:]:
                    if sent not in used and len(rest) < 4:
                        rest.append(f"- {sent} [{i}]"); used.add(sent)
                if rest:
                    body += "\n\n**Key findings:**\n" + "\n".join(rest)
            else:
                body = "I found pages but couldn't extract a sentence that clearly answers this. The most relevant pages are listed below."
                limits.append("No sentence matched your question well enough to quote.")
            limits.append("No language model connected: the answer is extracted from the sources, not independently reasoned.")
        # competitions / scholarships: dates, registration links
        dated = [(i, d) for i, s in enumerate(sources, start=1) for d in s["deadlines"]]
        if dated:
            body += "\n\n**Key dates found (verify on the official page):**\n" + "\n".join(f"- {d} [{i}]" for i, d in dated[:6])
        regs = [(i, l) for i, s in enumerate(sources, start=1) for l in s["reg_links"]]
        if regs:
            body += "\n\n**Registration / application links:**\n" + "\n".join(f"- {l['text']}: {l['href']} [{i}]" for i, l in regs[:6])
        elif ev["opportunity"]:
            limits.append("No registration link was found on the pages I read; use the official site links listed below.")
        if len(sources) >= 2:
            dates_by = {}
            for i, s in enumerate(sources, start=1):
                for d in s["deadlines"]:
                    for m in self.DATE.findall(d):
                        dates_by.setdefault(re.sub(r"\W+", " ", m.lower()).strip(), set()).add(i)
            if len(dates_by) > 1:
                body += "\n\n**Comparison:** Sources mention different dates: " + "; ".join(f"{d} in " + ",".join(f"[{n}]" for n in sorted(v)) for d, v in dates_by.items()) + ". Treat the official source as authoritative."
            else:
                tiers = ", ".join(f"[{i}] {s['tier']}" for i, s in enumerate(sources[:4], start=1))
                body += f"\n\n**Comparison:** Sources compared: {tiers}. " + ("Official sources are listed first." if official else "No official (.gov/.edu/.int) source was among them.")
        read = [s for s in sources if s["access"] == "read"]
        fresh = [s for s in read if s["fresh"]]
        body += (f"\n\n**Verification:** Checked live on {time.strftime('%d %b %Y')}. {len(primary)} page(s) read in full, {len(official)} official. "
                 + (f"{len(fresh)} mention {ev['year']} or later." if read else "") + (" Others show no current-year date, so they may be out of date." if read and len(fresh) < len(read) else ""))
        if not primary:
            limits.append("Only background or snippet sources were available - none is an official page.")
        status = "success" if len(primary) >= 2 else "partial"
        if len(primary) < 2:
            limits.append("Fewer than two primary sources could be read in full.")
        cards = [{"n": i, "title": s["title"], "url": s["url"], "host": s["host"], "tier": s["tier"], "access": s["access"], "relevance": s["relevance"],
                  "snippet": (s["snippet"] or s["text"][:200])[:240], "fresh": s["fresh"], "years": s["years"], "deadlines": s["deadlines"], "reg_links": s["reg_links"]}
                 for i, s in enumerate(sources, start=1)]
        speech = (cands[0][3] if cands and not used_llm else body)[:300]
        return AgentResult(status, body, sources=out_sources, limitations=limits, speech=speech,
                           data={"query": query, "read": len(primary), "llm": used_llm, "cards": cards, "opportunity": ev["opportunity"], "topic": query})

    def do_research(self, sub, ctx):
        q = (sub.args.get("query") or ctx.conv.get("last_topic") or "").strip()
        if not q:
            return self.clarify("What should I search for?")
        if not ctx.settings.get("internet_enabled"):
            return self.fail("Internet access is switched off in Settings, so I can't research live. I can use local knowledge instead.")
        ev = self.gather(ctx, q, bool(sub.args.get("deep") or ctx.deep))
        res = self.synthesize(ctx, q, ev)
        res.data["topic"] = q
        return res

    def do_follow_more(self, sub, ctx):
        return self.do_research(type(sub)("research", "zykron", sub.text, {"query": ctx.conv.get("last_topic"), "deep": True}), ctx)

    # ---------- YouTube
    def do_youtube(self, sub, ctx):
        q = sub.args.get("query") or ctx.conv.get("last_topic")
        if not q:
            return self.clarify("What topic should I find videos about?")
        if not ctx.settings.get("internet_enabled"):
            return self.fail("Internet access is switched off in Settings.")
        limits, vids = [], []
        try:
            vids = self.tool(ctx, "youtube_search", query=q)
        except Cancelled:
            raise
        except CrystaError as e:
            limits.append(f"YouTube search failed ({e}); trying a general web search for YouTube links.")
            try:
                for h in self.tool(ctx, "web_search", query=q + " site:youtube.com/watch"):
                    vid = parse_video_id(h["url"])
                    if vid:
                        vids.append({"video_id": vid, "title": h["title"], "channel": "", "url": h["url"], "duration": "", "views": "", "access": "metadata_only"})
            except CrystaError as e2:
                return self.fail(f"I couldn't find videos: {e2}", limitations=limits)
        if not vids:
            return self.fail("I couldn't find any videos for that.", limitations=limits)
        ctx.conv["last_video"] = vids[0]["url"]
        sources = [{"n": i, "title": v["title"], "url": v["url"],
                    "note": " · ".join(x for x in (v.get("channel"), v.get("duration"), v.get("views")) if x) + " (title/details only)"}
                   for i, v in enumerate(vids, start=1)]
        lines = [f"{i}. {v['title']}" + (f" — {v['channel']}" if v.get("channel") else "") for i, v in enumerate(vids, start=1)]
        text = f"Videos about \"{q}\":\n" + "\n".join(lines) + "\n\nI haven't watched these; this is only what the search results show (titles, channels, durations)."
        limits.append("Metadata only. Ask 'what is he saying in that video' to try reading captions of the first one.")
        res = AgentResult("success", text, sources=sources, limitations=limits, data={"query": q, "videos": vids, "topic": q},
                          speech=f"I found {len(vids)} videos about {q}. The first is {vids[0]['title']}.")
        if sub.args.get("verify"):
            return self._verify(sub, ctx, q, vids, res)
        return res

    def _transcript_points(self, tr, n=5):
        segs = tr["segments"]
        chunks, starts, cur, start = [], [], [], 0
        for s in segs:
            if not cur:
                start = s["start"]
            cur.append(s["text"])
            if len(" ".join(cur).split()) >= 28:
                chunks.append(" ".join(cur))
                starts.append(start)
                cur = []
        if cur:
            chunks.append(" ".join(cur))
            starts.append(start)
        return [(starts[i], chunks[i]) for i in textutil.frequency_summary(chunks, n)]

    def do_video(self, sub, ctx):
        url = sub.args.get("url") or ctx.conv.get("last_video")
        if not url:
            return self.clarify("Which video? Paste a YouTube link, or ask me to find videos first.")
        if not ctx.settings.get("internet_enabled"):
            return self.fail("Internet access is switched off in Settings.")
        ctx.conv["last_video"] = url
        info, limits = None, []
        try:
            info = self.tool(ctx, "youtube_video_info", url=url)
        except Cancelled:
            raise
        except CrystaError as e:
            limits.append(f"Couldn't read video details: {e}")
        src = [{"n": 1, "title": (info or {}).get("title") or url, "url": url, "note": "video page"}]
        title = f"\"{info['title']}\" by {info['channel']}" if info else "this video"
        try:
            tr = self.tool(ctx, "youtube_transcript", url=url)
        except Cancelled:
            raise
        except (TranscriptUnavailable, CrystaError) as e:
            return AgentResult("partial", f"I couldn't read the spoken content of {title}. {e} All I have is its title and channel, so I can't say what is said in it.",
                               sources=src, limitations=limits + [str(e), "Metadata only: I did not watch or hear the video."], data={"access": "metadata_only"})
        pts = self._transcript_points(tr)
        kind = "auto-generated" if tr["auto_generated"] else "uploaded"
        answer = None
        if ctx.llm.available():
            text = " ".join(s["text"] for s in tr["segments"])[:6000]
            try:
                answer = self.tool(ctx, "llm_chat", messages=[{"role": "user", "content": f"Summarise this video transcript in 5 bullets. Do not add facts.\n\n{text}"}], system=self.system_instruction)
                limits.append("Summary written by a local language model from the captions.")
            except CrystaError:
                answer = None
        if answer is None:
            answer = "\n".join(f"- [{fmt_time(t)}] {c}" for t, c in pts)
            limits.append("No language model: these are the caption passages that best represent the video by keyword frequency, not a true summary.")
        limits.append(f"Based on the {kind} captions ({tr['language']}), not on watching the video." + (" Auto captions can contain mistakes." if tr["auto_generated"] else ""))
        return AgentResult("success", f"From the captions of {title}:\n{answer}", sources=src, limitations=limits,
                           data={"access": "transcript", "language": tr["language"], "points": [{"t": t, "text": c} for t, c in pts]},
                           speech=f"I read the captions of {title}. " + (pts[0][1][:200] if pts else ""))

    def _verify(self, sub, ctx, q, vids, vres):
        """Compare the first video's caption claims with independent web sources (keyword-overlap heuristic)."""
        vsub = type(sub)("video", "zykron", sub.text, {"url": vids[0]["url"]})
        vr = self.do_video(vsub, ctx)
        ev = self.gather(ctx, q)
        wr = self.synthesize(ctx, q, ev)
        off = len(vres.sources)
        shift = lambda t: re.sub(r"\[(\d+)\]", lambda m: f"[{int(m.group(1)) + off}]", t)
        parts = [vres.summary, "\n**What the first video says:**\n" + vr.summary]
        pts = vr.data.get("points") or []
        evidence = [(i, s["text"]) for i, s in enumerate(ev["sources"], start=1) if s["access"] == "read"]
        if pts and evidence:
            lines = []
            for p in pts[:4]:
                best = max(((textutil.overlap(p["text"], t), i) for i, t in evidence), default=(0, 0))
                lines.append(f"- [{fmt_time(p['t'])}] " + (f"echoed by web source [{best[1] + off}]" if best[0] >= 0.5 else "not corroborated in the pages I read"))
            parts.append("\n**Corroboration (keyword-overlap check, not real fact-checking):**\n" + "\n".join(lines))
        parts.append("\n**What independent web sources say:**\n" + shift(wr.summary))
        limits = vres.limitations + vr.limitations + wr.limitations
        sources = vres.sources + [dict(s, n=len(vres.sources) + s["n"]) for s in wr.sources]
        return AgentResult("success" if vr.status == "success" and wr.status != "failed" else "partial", "\n".join(parts),
                           sources=sources, limitations=limits, data={"query": q, "topic": q}, speech=wr.speech)

from __future__ import annotations

import re
import time

from .base import Agent


class Crysta(Agent):
    id, name = "crysta", "CRYSTA"
    description = "Main AI and central coordinator: understands English, Tamil and Tanglish, answers simple questions directly, routes the rest to specialists."
    system_instruction = ("You are Crysta, a concise, friendly local-first assistant. Answer directly. Never invent facts, sources, "
                          "or actions you did not perform. If unsure, say so briefly. Understand informal or misspelled English "
                          "without correcting the user.")
    permitted_tools = frozenset({"llm_chat", "llm_status", "offline_search"})

    def do_greet(self, sub, ctx):
        name = ctx.settings.get("user_name")
        return self.ok(f"Hi {name}, welcome to Crysta AI. What can I do for you?")

    def do_thanks(self, sub, ctx):
        return self.ok("Anytime.")

    def do_identity_name(self, sub, ctx):
        return self.ok("My name is CRYSTA.", speech="My name is Crysta.")

    def do_identity_creator(self, sub, ctx):
        who = self.creator(ctx)
        return self.ok(f"I was made by {who}.", speech=f"I was made by {who}.")

    def creator(self, ctx):
        return getattr(ctx.settings.config, "creator", "Arshath")

    def do_time(self, sub, ctx):
        t = time.strftime("%I:%M %p").lstrip("0")
        return self.ok(f"It's {t}.", speech=f"It's {t}.")

    def do_date(self, sub, ctx):
        d = time.strftime("%A, %d %B %Y")
        return self.ok(f"Today is {d}.", speech=f"Today is {d}.")

    def do_smalltalk(self, sub, ctx):
        n = sub.text.lower()
        if re.search(r"tamil|tanglish|english", n):
            return self.ok("Yes — I understand English, Tamil and Tanglish. You can type or speak to me in any of them.")
        if re.search(r"internet|offline|online", n):
            return self.ok("I work offline for local things (files, notes, hardware, planning, maths). I only need the internet when you ask for live research.")
        if re.search(r"bye|good night|see you", n):
            return self.ok("Goodbye! I'll be here when you need me.")
        if re.search(r"hear|there|listening|working", n):
            return self.ok("Yes, I'm here. Press the mic or type and I'll respond.")
        if re.search(r"how are you", n):
            return self.ok("I'm running well, thanks for asking. What would you like to do?")
        return self.do_about(sub, ctx)

    def do_about(self, sub, ctx):
        st = self.tool(ctx, "llm_status")
        brain = f"a local language model ({st['model']})" if st["available"] else "no language model yet (open-ended chat is limited)"
        return self.ok("I'm CRYSTA, the coordinator of eight specialist agents: ZYKRON (research), NOVA (coding), ASTRA (science), VEGA (files), "
                       "ECHO (voice), NEXUS (memory), ORION (planning) and VOLT (hardware). I can calculate, search local knowledge, research the web "
                       f"and YouTube, manage files with your permission, keep notes and tasks, and monitor your hardware. Connected brain: {brain}.")

    def do_offline(self, sub, ctx):
        return self.ok("Offline I can still: calculate, convert units, search my bundled knowledge and your notes, manage tasks, "
                       "open apps/files, run approved commands and check system health. Web and YouTube research need internet. "
                       "Open-ended answers need a local model such as Ollama.")

    def do_ui(self, sub, ctx):
        view = sub.args.get("view", "home")
        label = {"home": "home", "chat": "the chat", "agents": "the agent list", "settings": "settings", "devices": "device pairing", "computer": "computer control",
                 "zykron": "ZYKRON research", "nova": "NOVA development", "astra": "ASTRA science", "vega": "VEGA file manager", "echo": "ECHO voice studio",
                 "nexus": "NEXUS memory", "orion": "ORION planning", "volt": "VOLT hardware monitor"}.get(view, view)
        extra = " Pick a voice, language and speed here." if sub.args.get("note") == "voice" else ""
        return self.ok(f"Opening {label}.{extra}" if view != "home" else "Back to CRYSTA.", ui_actions=[{"type": "open_view", "view": view}])

    def do_question(self, sub, ctx):
        hits = self.tool(ctx, "offline_search", query=sub.text, k=2)
        if hits and hits[0]["score"] >= 0.5:
            h = hits[0]
            return self.ok(f"{h['text']}\n\n(From my local knowledge: {h['source']})",
                           sources=[{"title": h["source"], "url": "", "note": "local knowledge file"}], speech=h["text"][:300])
        answer = self.llm_answer(ctx, sub.text)
        if answer:
            return self.ok(answer, limitations=["Written by a local language model; it can be wrong. No sources were checked."],
                           data={"llm": True})
        from .. import nlp
        norm = nlp.normalize(sub.text)
        personal = re.search(r"\b(you|your|yourself|crysta|me|my|i|we|us)\b", norm)
        if personal:  # conversational or about the user/assistant: never worth a web search
            return self.partial("I'm not sure about that. If you want me to look something up online, say \"search\" followed by the topic.",
                                limitations=["No language model is connected, so I only answer what I recognise."])
        return self.partial("I don't have that in my local knowledge and no language model is connected.",
                            data={"escalate": "research"},
                            limitations=["Without a language model or internet search I can't answer open-ended questions."])

    def do_chat(self, sub, ctx):
        answer = self.llm_answer(ctx, sub.text)
        if answer:
            return self.ok(answer, limitations=["Written by a local language model; it can be wrong."])
        return self.partial("I'm not sure what you'd like me to do. Try: 'search black holes', 'find videos about…', "
                            "'open chrome', 'calculate 25*4', 'remind me to … in 10 minutes', or 'show agents'.",
                            limitations=["No language model is connected, so I only handle requests I recognise."])

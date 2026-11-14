from __future__ import annotations

from ..errors import CrystaError
from .base import Agent


class Astra(Agent):
    id, name = "astra", "ASTRA"
    description = "Science and knowledge: explanations, a real formula solver, mathematics and plotting, offline reference; deeper reasoning needs a local model."
    system_instruction = ("You are Astra, a science and maths tutor. State assumptions, show key steps, separate theory from experiment, "
                          "and never invent measurements or citations. Use the calculator results provided for arithmetic.")
    permitted_tools = frozenset({"calculator", "offline_search", "science_library", "science_solve", "science_plot", "llm_chat", "llm_status"})

    def do_calc(self, sub, ctx):
        try:
            r = self.tool(ctx, "calculator", text=sub.text)
        except ValueError as e:
            return self.fail(f"I couldn't compute that: {e}")
        res = r["result"]
        shown = res if "=" in res else f"{r['expression']} = {res}"
        return self.ok(shown, data=r, speech=shown.replace("*", " times ").replace("**", " to the power "),
                       limitations=["Trig functions use radians."] if any(f in r["expression"] for f in ("sin", "cos", "tan")) else [])

    def do_science(self, sub, ctx):
        hits = self.tool(ctx, "offline_search", query=sub.text, k=2)
        keep = [h for h in hits if h["score"] >= max(0.3, (hits[0]["score"] * 0.6) if hits else 0)]
        facts = "\n".join(h["text"] for h in keep)
        src = [{"title": h["source"], "url": "", "note": "local knowledge file"} for h in keep]
        answer = self.llm_answer(ctx, sub.text, ("Reference facts you may use:\n" + facts) if facts else "")
        if answer:
            return self.ok(answer, sources=src, limitations=["Explained by a local model; check numbers with the calculator or a textbook."])
        if facts:
            return self.ok(facts, sources=src, limitations=["From my small bundled reference sheet only; no model is connected to explain further."])
        return self.partial("I don't have that in my offline reference sheet and no language model is connected.",
                            data={"escalate": "research"}, limitations=["Offline science knowledge is limited to constants and basic formulas."])

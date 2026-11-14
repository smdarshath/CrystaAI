from __future__ import annotations

import datetime

from ..errors import ToolUnavailable
from .base import Agent


class Nexus(Agent):
    id, name = "nexus", "NEXUS"
    description = "Memory and information retrieval: saved notes, project notes and memories in local SQLite - only when you turn memory on."
    system_instruction = ("You are Nexus. Store only what the user explicitly asks you to. Never collect passwords, private files or "
                          "browsing history. Conversation context is not verified fact.")
    permitted_tools = frozenset({"memory_save", "memory_list", "memory_delete", "memory_set_enabled", "notes_add", "notes_list", "notes_update", "notes_delete", "memory_search", "offline_search"})

    def do_memory_on(self, sub, ctx):
        return self.tool(ctx, "memory_set_enabled", enabled=True)

    def do_memory_off(self, sub, ctx):
        return self.ok(self.tool(ctx, "memory_set_enabled", enabled=False)["message"], ui_actions=[{"type": "refresh_settings"}])

    def do_remember(self, sub, ctx):
        try:
            value = sub.args["value"]
            self.tool(ctx, "memory_save", key=" ".join(value.split()[:6]), value=value)
        except ToolUnavailable as e:
            return self.partial(str(e), limitations=["Nothing was saved."])
        return self.ok(f"Saved: \"{value[:120]}\". You can review or delete it in Settings → Memory.")

    def do_recall(self, sub, ctx):
        rows = self.tool(ctx, "memory_list")
        if not rows:
            on = ctx.settings.get("memory_enabled")
            return self.ok("I haven't saved anything yet." + ("" if on else " Memory is currently off."))
        lines = [f"#{r['id']} {r['value']}" for r in rows[:15]]
        return self.ok("Here's what I have saved:\n" + "\n".join(lines))

    def do_forget(self, sub, ctx):
        target = (sub.args.get("target") or "").strip()
        if target in ("", "everything", "all", "memory", "all memory", "everything i said"):
            rows = self.tool(ctx, "memory_list")
            if not rows:
                return self.ok("There's nothing saved to forget.")
            ctx.toolbox._gate("memory_delete", {"scope": "all"}, "Permanently delete ALL saved memories, notes and chat history stored by Crysta.", "high")
        words = [w for w in target.replace("about", "").replace("that", "").split() if len(w) > 2]
        rows = [r for r in self.tool(ctx, "memory_list") if any(w in (r["key"] + " " + r["value"]).lower() for w in words)]
        if not rows:
            return self.partial(f"I couldn't find a saved memory matching '{target}'.")
        for r in rows[:10]:
            self.tool(ctx, "memory_delete", id=r["id"])
        return self.ok(f"Forgot {min(len(rows), 10)} item(s): " + "; ".join(r["value"][:50] for r in rows[:10]))

    def do_memory_search(self, sub, ctx):
        q = (sub.args.get("query") or "").strip() or "project"
        r = self.tool(ctx, "memory_search", query=q)
        rows = [f"• Note #{n['id']} [{n['category']}] {n['title']}: {n['body'][:120]}" for n in r["notes"][:8]] + [f"• Memory #{m['id']}: {m['value'][:120]}" for m in r["memories"][:8]]
        if not rows:
            on = ctx.settings.get("memory_enabled")
            return self.ok(f"I found nothing saved about \"{q}\"." + ("" if on else " Memory is currently off, so nothing new is being saved."), ui_actions=[{"type": "open_view", "view": "nexus"}])
        return self.ok(f"Saved items matching \"{q}\":\n" + "\n".join(rows), ui_actions=[{"type": "open_view", "view": "nexus"}], data={"topic": None})

    def do_note(self, sub, ctx):
        body = sub.args.get("body")
        if not body:
            return self.clarify("What should the note say?")
        try:
            self.tool(ctx, "notes_add", title=body[:40], body=body)
        except ToolUnavailable as e:
            return self.partial(str(e), limitations=["Nothing was saved."])
        return self.ok("Note saved.")

    def do_note_list(self, sub, ctx):
        rows = self.tool(ctx, "notes_list")
        if not rows:
            return self.ok("No notes saved yet.")
        return self.ok("\n".join(f"#{r['id']} {r['body'][:100]} ({datetime.datetime.fromtimestamp(r['created']):%d %b})" for r in rows[:15]))

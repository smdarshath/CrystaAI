from __future__ import annotations

import datetime
import re

from ..timeparse import parse_due
from .base import Agent


class Orion(Agent):
    id, name = "orion", "ORION"
    description = "Project planning and strategy: kanban board, milestones, timeline and roadmap. Reminders alert only while CRYSTA is open."
    system_instruction = ("You are Orion, a planner. Break goals into short, concrete steps. Report completed, pending, failed and "
                          "unverified steps separately. Never claim a reminder exists unless it was actually stored.")
    permitted_tools = frozenset({"task_add", "task_list", "task_done", "task_update", "task_delete", "projects", "llm_chat", "llm_status"})

    def do_task_add(self, sub, ctx):
        title, due = parse_due(sub.args["title"]) if sub.args.get("reminder") else (sub.args["title"], None)
        title = re.sub(r"^(to|that|about)\s+", "", title).strip() or sub.args["title"]
        r = self.tool(ctx, "task_add", title=title, due=due)
        if due:
            when = datetime.datetime.fromtimestamp(due).strftime("%a %d %b, %I:%M %p")
            return self.ok(f"Reminder #{r['id']} saved: \"{title}\" at {when}.",
                           limitations=["I can only alert you while Crysta is open in a browser tab (a notification pops up and I speak it)."])
        if sub.args.get("reminder"):
            return self.ok(f"Saved \"{title}\" as task #{r['id']} (I couldn't find a time in that, so no alert is set).")
        return self.ok(f"Task #{r['id']} added: \"{title}\".")

    def do_task_list(self, sub, ctx):
        rows = self.tool(ctx, "task_list")
        if not rows:
            return self.ok("You have no tasks.")
        def line(r):
            when = f" (due {datetime.datetime.fromtimestamp(r['due']):%d %b %I:%M %p})" if r["due"] else ""
            return f"{'✔' if r['status'] == 'done' else '•'} #{r['id']} {r['title']}{when}"
        pending = [r for r in rows if r["status"] != "done"]
        return self.ok(f"{len(pending)} pending, {len(rows) - len(pending)} done:\n" + "\n".join(line(r) for r in rows[:25]))

    def do_task_done(self, sub, ctx):
        self.tool(ctx, "task_done", id=sub.args["id"])
        return self.ok(f"Marked task #{sub.args['id']} as done.")

    def do_plan(self, sub, ctx):
        goal = sub.args.get("goal") or sub.text
        steps = [s.strip() for s in re.split(r"\s*(?:,|\band\b|;|\n|\d+[.)])\s*", goal) if len(s.strip()) > 3]
        answer = self.llm_answer(ctx, f"Make a short numbered plan (max 7 steps) for: {goal}")
        if answer:
            return self.ok(answer, limitations=["Plan written by a local model; nothing has been scheduled or executed."])
        if len(steps) >= 2:
            return self.ok("Here's your checklist:\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1)) +
                           "\n\nStatus: all steps pending. Say 'add task: …' to track any of them.")
        template = ["Define the goal and what \"done\" looks like", "Research and collect requirements", "Design the approach", "Build the first working version",
                    "Test and fix problems", "Release, then review what to improve"]
        return self.ok("No language model is connected, so here is a generic starter plan (a template, not tailored to your project):\n" +
                       "\n".join(f"{i}. {s}" for i, s in enumerate(template, 1)) +
                       "\n\nOpen ORION to turn it into milestones on your board, or tell me your own steps (e.g. 'plan: buy domain, build page, deploy').",
                       ui_actions=[{"type": "open_view", "view": "orion"}], limitations=["Generic template - edit it to fit your project."])

import time
import unittest

from helpers import make_app

from crysta import nlp
from crysta.tools import calculator
from crysta.timeparse import parse_due


class CalculatorTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(calculator.evaluate("25*4+2"), "102")
        self.assertEqual(calculator.evaluate("2^10"), "1024")
        self.assertEqual(calculator.calculate("what is 20% of 150")["result"], "30")
        self.assertEqual(calculator.calculate("sqrt of 144")["result"], "12")
        self.assertIn("6.2137", calculator.calculate("10 km to miles")["result"])

    def test_no_code_execution(self):
        for bad in ("__import__('os').system('echo hi')", "open('x')", "2**100000", "1/0", "factorial(100000)"):
            with self.assertRaises(ValueError):
                calculator.evaluate(bad)


class LanguageTests(unittest.TestCase):
    def intents(self, text, ctx=None):
        return [(s.intent, s.agent) for s in nlp.plan(text, ctx or {})]

    def test_correct_spelling(self):
        self.assertEqual(self.intents("Find videos about black holes"), [("youtube", "zykron")])

    def test_informal_and_misspelled(self):
        self.assertEqual(self.intents("find me some yt vedios abt black holes plz"), [("youtube", "zykron")])
        self.assertEqual(self.intents("opne chrme"), [("open_app", "vega")])
        self.assertEqual(self.intents("serch quantum computing"), [("research", "zykron")])
        self.assertEqual(self.intents("bro make this website look more premium"), [("code", "nova")])
        self.assertEqual(self.intents("whats 25*4+2"), [("calc", "astra")])

    def test_no_punctuation_and_slang(self):
        self.assertEqual(self.intents("open my laptop files"), [("files_list", "vega")])
        self.assertEqual(self.intents("what he saying in that video"), [("video", "zykron")])
        self.assertEqual(self.intents("remind me to drink water in 5 min"), [("task_add", "orion")])

    def test_args_keep_user_text(self):
        self.assertEqual(nlp.plan("find me some yt videos about Black Holes", {})[0].args["query"], "black holes")

    def test_followups_use_context(self):
        self.assertEqual(self.intents("search more", {"last_topic": "black holes"}), [("follow_more", "zykron")])
        self.assertEqual(self.intents("open it"), [("follow_open", "vega")])

    def test_ambiguity_asks_instead_of_guessing(self):
        app = make_app()
        r = app.coordinator.handle("open it", "t1")
        self.assertTrue(r["results"][0]["data"].get("clarify"))
        r = app.coordinator.handle("search this and tell me the real answer", "t2")
        self.assertTrue(r["results"][0]["data"].get("clarify"))
        self.assertEqual(len(r["results"]), 1)

    def test_compound_request_splits(self):
        s = self.intents("Research the best way to build my local AI website and tell me how to run it on my Chromebook.")
        self.assertEqual(s, [("research", "zykron"), ("howto", "nova")])

    def test_time_parse(self):
        title, due = parse_due("stretch in 10 minutes", now=1000.0)
        self.assertEqual(title, "stretch")
        self.assertAlmostEqual(due, 1600.0, delta=1)


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.co = self.app.coordinator

    def test_nine_distinct_agents(self):
        agents = self.co.registry.all()
        self.assertEqual({a.name for a in agents}, {"CRYSTA", "ZYKRON", "NOVA", "ASTRA", "VEGA", "ECHO", "NEXUS", "ORION", "VOLT"})
        self.assertEqual(len({a.system_instruction for a in agents}), 9)
        self.assertEqual(len({a.permitted_tools for a in agents}), 9)

    def test_tool_permissions_enforced(self):
        from crysta.agents.base import AgentContext
        from crysta.errors import ToolNotPermitted
        ctx = AgentContext(self.app.toolbox, self.app.settings, self.app.llm, {})
        with self.assertRaises(ToolNotPermitted):
            self.co.registry.get("echo").tool(ctx, "run_command", command="ls")
        with self.assertRaises(ToolNotPermitted):
            self.co.registry.get("astra").tool(ctx, "web_search", query="x")

    def test_every_agent_only_calls_permitted_tools(self):
        import re, pathlib
        for a in self.co.registry.all():
            src = pathlib.Path(__import__("inspect").getsourcefile(type(a))).read_text()
            used = set(re.findall(r'self\.tool\(ctx, "(\w+)"', src))
            self.assertLessEqual(used, a.permitted_tools, a.name)

    def test_simple_request_uses_one_agent(self):
        before = len(self.co.history)
        r = self.co.handle("calculate 7*6", "a")
        self.assertEqual(len(self.co.history) - before, 1)
        self.assertEqual(r["reply"], "7*6 = 42")

    def test_failed_agent_reports_failure(self):
        orig = self.app.toolbox.call
        def boom(name, **kw): raise RuntimeError("disk exploded")
        self.app.toolbox.call = boom
        r = self.co.handle("check my system", "b")
        self.app.toolbox.call = orig
        self.assertEqual(r["status"], "failed")
        self.assertNotIn("exploded", r["reply"])
        self.assertIn("unexpected error", r["reply"])

    def test_combines_real_outputs(self):
        r = self.co.handle("calculate 2+2 then check my system", "c")
        self.assertEqual([x["agent"] for x in r["results"]], ["astra", "volt"])
        self.assertIn("2+2 = 4", r["reply"])
        self.assertIn("Measured", r["reply"])
        self.assertTrue(r["reply"].startswith("I used ASTRA and VOLT"))

    def test_no_model_is_stated_honestly(self):
        r = self.co.handle("bro make this website look more premium", "d")
        self.assertEqual(r["status"], "partial")
        self.assertIn("language model", r["reply"])

    def test_offline_knowledge(self):
        r = self.co.handle("what is the schwarzschild radius formula", "e")
        self.assertEqual(r["results"][0]["agent"], "astra")
        self.assertEqual(r["status"], "success")
        self.assertTrue(r["results"][0]["sources"][0]["note"].startswith("local knowledge"))


class OrionTests(unittest.TestCase):
    def test_reminder_is_stored_and_honest(self):
        app = make_app()
        r = app.coordinator.handle("remind me to stretch in 1 second", "o")
        self.assertEqual(r["status"], "success")
        self.assertTrue(any("while Crysta is open" in l for l in r["limitations"]))
        time.sleep(1.2)
        due = app.db.query("SELECT title FROM tasks WHERE status='pending' AND due<=?", (time.time(),))
        self.assertEqual(due[0]["title"], "stretch")

    def test_plan_without_model_does_not_invent(self):
        app = make_app()
        r = app.coordinator.handle("plan my trip", "p")   # no model: a clearly-labelled generic template, never passed off as tailored
        self.assertIn("template", r["reply"].lower())
        self.assertTrue(any("Generic template" in l for l in r["limitations"]))
        self.assertIn("1. buy domain", app.coordinator.handle("plan: buy domain, build page, deploy", "p")["reply"])


if __name__ == "__main__":
    unittest.main()

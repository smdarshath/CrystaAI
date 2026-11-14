from crysta.agents.base import Agent


class HelloAgent(Agent):
    system_instruction = "Example extension agent."

    def do_run(self, sub, ctx):                       # called when a trigger phrase matches
        r = self.tool(ctx, "calculator", text="6*7")  # only tools listed in agent.json "permissions" are allowed
        return self.ok(f"Hello from an extension agent! (6*7 = {r['result']})")

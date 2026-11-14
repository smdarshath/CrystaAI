# Adding agents

1. Create `extensions/<folder>/agent.json` and `agent.py` (copy `extensions/example_hello`).
2. `agent.json` fields: `id` (3–20 chars, `a-z0-9_`), `name`, `description`, `module` (a plain `.py` file in that folder), `class` (a subclass of `crysta.agents.base.Agent`), `ui` (`{"title": ...}`), `capabilities` (list), `permissions` (tool names the agent may use), optional `triggers` (≤10 phrases that route a request to it).
3. Implement `do_run(self, sub, ctx)` and call tools only via `self.tool(ctx, "<tool>", ...)`.
4. CRYSTA **validates** the manifest on start (bad ids, unknown tools, path tricks, duplicates, missing files are rejected and listed in All Agents). A valid extension still does nothing until you add its id to Settings → `extensions_enabled`.
5. Enabled extensions run with exactly the permissions in their manifest; any other tool is refused.

Extension code is ordinary Python that runs inside CRYSTA: only enable extensions you trust. Extension agents get a card in All Agents; a dedicated custom workspace is not supported yet (built-in agents have their own).

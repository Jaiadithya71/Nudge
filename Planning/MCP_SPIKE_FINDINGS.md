# MCP Spike — Findings

> Completed: 2026-04-17
> Timebox used: ~2 hours (well under 1-2 day budget)
> Verdict: **GREEN — MCP is viable. Proceed with Phase 3 planning.**

---

## What Was Built

Isolated `spike/` folder with 3 Python files (~200 LOC total):
- `mcp_bridge.py` — spawn MCP server, list tools, call tools
- `llm_adapter.py` — Gemini function-calling wrapper + MCP schema translator
- `mcp_test.py` — end-to-end orchestration loop

Plus sandbox directory with test files.

---

## Success Criteria — All Met

| Criterion | Result |
|---|---|
| Spawn an MCP server process | ✅ `npx -y @modelcontextprotocol/server-filesystem` worked first try |
| Read tool schemas from MCP server | ✅ 14 tools discovered cleanly |
| Translate MCP schemas → LLM function declarations | ✅ With 5 keys stripped (`additionalProperties`, `$schema`, `$id`, `definitions`, `default`) |
| LLM calls the right tool | ✅ Chose `list_allowed_directories`, `directory_tree`, `read_text_file` appropriately |
| Execute tool calls and feed results back | ✅ Via `FunctionResponse` parts in conversation history |
| LLM converges to natural-language answer | ✅ 4 tool calls, then final text answer with accurate file contents |

---

## Key Technical Learnings

### What worked
- The official MCP Python SDK (`mcp` package) is mature and well-designed
- `stdio_client` + `ClientSession` pattern is clean and async-friendly
- Gemini's `FunctionDeclaration.parameters` accepts most JSON Schema directly
- On Windows: `npx.cmd` (not `npx`) is required as the command

### What needed workarounds
- Gemini rejects certain JSON Schema fields: stripped `additionalProperties`, `$schema`, `$id`, `definitions`, `default`
- Description length: truncated to 1000 chars (not hit in practice, but safe)
- Tool result content comes back as a list of items, each with `.text`; bridge joins them

### What surprised us
- MCP filesystem server exposes 14 tools (read, write, edit, move, search, etc.) — much richer than expected
- LLM chose to call `list_allowed_directories` first as a defensive check — good hygiene, but costs a request
- Total latency for a 4-tool-call conversation: ~10 seconds including npx cold start

---

## Cost Reality Check

**Gemini free tier limit: 5 requests per minute** on `gemini-2.5-flash`.

A single multi-turn tool-calling conversation can burn that budget in 10 seconds.

| Usage pattern | Free tier viable? |
|---|---|
| Scheduled daily jobs (3/day) | ✅ Yes |
| Per-task rule-based nudges (0 LLM) | ✅ Yes |
| Interactive chat with tool calling | ❌ No — hit rate limit on second conversation |
| Background MCP tool calls | ❌ No — same reason |

**Implication:** The chat interface in Phase 3 requires paid Gemini tier (or switching to Claude/OpenAI with more generous limits). Original $5-15/month estimate in REVISED_ARCHITECTURE.md stands.

---

## Risks That Became Real vs Speculative

| Risk from original spike plan | Actual outcome |
|---|---|
| MCP ecosystem immature | False — filesystem server worked first try, 14 rich tools |
| Gemini function calling ≠ MCP native | Mild — 5 schema keys to strip, trivial adapter |
| Spawn overhead makes latency bad | False — <1s after first-time npx install |
| Code feels messy and complex | False — 200 LOC across 3 files |
| Takes 2+ days | False — took ~2 hours |
| **Free-tier quota is a real constraint** | **TRUE — hit 5-RPM limit on second test** |

The only real surprise was the free-tier quota. Everything else was smoother than expected.

---

## What to Do Next

### Immediate (unchanged)
1. **Deploy current Phase 1 to Railway** — spike doesn't change this
2. Use the deployed system daily, accumulate real data

### After deployment
The spike unblocks Phase 3 planning with confidence:

1. **Write a proper Phase 3 plan** using patterns from the spike
2. **Budget for paid LLM tier** — factor into the "is this worth it" decision
3. **Start with Google Calendar MCP** — the next de-risking step
4. **Build the chat UI** as part of Phase 3 (not now)

### Architectural patterns to preserve from the spike
- `stdio_client` + long-lived `ClientSession` per server
- Schema cleaner function (moved into main codebase as `llm_module/mcp_adapter.py`)
- Stateless message-building via `types.Content` + `types.Part`
- Function response feedback pattern (each tool result becomes a `user`-role message with `FunctionResponse` part)

### Spike code fate
**The spike was disposable by design.** `spike/` folder has been deleted. The learnings live in this document.

---

## Decision

**Go ahead with the MCP-based architecture for Phase 3+**, with these adjustments:

1. Paid Gemini tier (or alternative LLM) needs to be budgeted before Phase 3 starts
2. Rate limiting logic must live in the LLM adapter from day 1
3. Consider caching tool results where safe (file reads, calendar reads within a short window)
4. Keep Phase 2 first — behavior patterns still have value regardless of chat

---

## Open Questions That Remain

- How does Google Calendar MCP handle OAuth token refresh? (answer at Phase 3 start)
- What's the right chat session persistence model? (decide when building Phase 3)
- Should MCP servers run as subprocesses per-request or long-lived? (long-lived, based on spawn overhead observed)
- How to handle user_id scoping for third-party MCP servers that don't know about it? (MCP bridge layer enforces it)

These are Phase 3 design questions, not spike blockers.

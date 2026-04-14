# HappyTrace

HappyTrace is a small observability playground for agent session logs.

Current scope:

- single-file HTML viewer
- reads local Hermes, Codex, Claude, and OpenCode session logs
- works as a static page with browser directory access
- supports session list, event timeline, detail panel, search, and filters

## Files

- `happytrace.html` — current local-session log viewer（支持一键载入 OpenCode DB）
- `prototypes/agent-observer.html` — earlier generic observer prototype
- `scripts/export_opencode_sessions.py` — export OpenCode SQLite sessions into HappyTrace-readable JSON
- `scripts/serve_happytrace.py` — start a local static server and print the browser URL

## How to use

### Recommended: start with the local server script

```bash
python3 scripts/serve_happytrace.py
```

After startup, the script prints the viewer URL, for example:

```text
Open: http://127.0.0.1:8000/happytrace.html
```

You can also open the browser automatically:

```bash
python3 scripts/serve_happytrace.py --open
```

Or expose it to other devices on your LAN:

```bash
python3 scripts/serve_happytrace.py --host 0.0.0.0 --port 8000
```

Then click **连接 sessions 目录** and choose the directory that exists on your machine. Common locations include:

```text
~/.hermes
~/.hermes/sessions
~/.codex
~/.codex/sessions
~/.claude
~/.claude/transcripts
~/.claude/projects
~/.local/share/opencode
```

After permission is granted, the page can:

- remember the directory handle in IndexedDB
- reload local sessions from that directory tree
- auto-refresh every 5 seconds

### Fallback

If you do not want to use the helper script, you can still serve the repo root directly:

```bash
python3 -m http.server 8000
```

Then open:

```text
http://127.0.0.1:8000/happytrace.html
```

If your browser does not support persistent directory handles well, use the folder picker input and manually select the same directory.

## Runtimes currently supported

### Hermes

HappyTrace reads:

- `sessions.json`
- `session_*.json`

and maps them into events such as:

- `UserPromptSubmit`
- `AssistantToolCall`
- `ToolResult`
- `AssistantMessage`
- `Stop`

### Codex

HappyTrace reads Codex rollout logs from `.jsonl` files under the local Codex sessions tree, plus optional metadata from:

- `session_index.jsonl`

It maps Codex entries into events such as:

- `SessionStart`
- `ContextSnapshot`
- `UserPromptSubmit`
- `AssistantMessage`
- `Reasoning`
- `AssistantToolCall`
- `ToolResult`
- `Snapshot`
- `TokenCount`
- `TurnAborted`

### Claude

HappyTrace reads Claude logs from:

- `transcripts/*.jsonl`
- `projects/**/*.jsonl`

and currently skips subagent project logs and skill injection logs.

It maps Claude entries into events such as:

- `UserPromptSubmit`
- `AssistantMessage`
- `Reasoning`
- `AssistantToolCall`
- `ToolResult`
- `SystemEvent`
- `LocalCommand`
- `ApiError`
- `QueueEnqueue`
- `QueueDequeue`
- `Snapshot`

### OpenCode

HappyTrace supports OpenCode in two layers.

#### Layer 1: llm log view
It reads:

- `storage/session/global/*.json`
- `llm-logs/*.jsonl`

and reconstructs the per-session LLM chain with events such as:

- `LLMRequest`
- `FirstToken`
- `LLMResponse`
- `LLMResponseToolCalls`
- `LLMError`

#### Layer 2: deep session export
For deeper OpenCode inspection, run:

```bash
python3 scripts/export_opencode_sessions.py
```

This script can read either OpenCode DB path directly, depending on your setup, for example:

```bash
python3 scripts/export_opencode_sessions.py --db ~/.local/share/opencode/opencode-local.db
python3 scripts/export_opencode_sessions.py --db ~/.local/share/opencode/opencode.db
```

By default it exports into:

```text
~/.local/share/opencode/happytrace-cache
```

This produces `opencode-session-*.json` files that HappyTrace can read automatically when you point it at `~/.local/share/opencode`.

If you want the full reconstructed conversation history directly from the DB, you can also target a single session and print markdown to stdout:

```bash
python3 scripts/export_opencode_sessions.py \
  --db ~/.local/share/opencode/opencode.db \
  --session-id ses_xxx \
  --history-only
```

Or write markdown history files alongside the JSON export:

```bash
python3 scripts/export_opencode_sessions.py \
  --db ~/.local/share/opencode/opencode.db \
  --history-output-dir ~/.local/share/opencode/happytrace-history
```

The deep export reconstructs OpenCode sessions from SQLite `session` / `message` / `part` tables and surfaces events such as:

- `UserPromptSubmit`
- `AssistantMessage`
- `Reasoning`
- `ToolResult`
- `StepStart`
- `StepFinish`
- `StepFinishToolCalls`

If both exported JSON and llm logs exist for the same OpenCode session, HappyTrace now merges them into one timeline: deep message/tool/step events plus LLM request/first-token/response chain events.

In the merged OpenCode view, Session Meta also shows aggregate stats such as source layers, LLM request count, tool call count, error count, agents, modes, wall time, LLM time, token total, and average TTFT.

## Notes

- This is intentionally static-first.
- Browsers cannot silently read arbitrary local files without permission.
- So the practical model is: first grant directory access, then let the page auto-refresh.
- The current goal is cross-runtime session log inspection, not a runtime-specific viewer.
- OpenCode now has a deeper path via exporter because browser-only static HTML cannot directly query local SQLite without bundling a database engine.

## Next ideas

- better cross-runtime event normalization
- deeper OpenCode support for more part types and tool metadata
- more runtime adapters: Gemini CLI
- project / platform grouping
- richer token / model / source metadata
- compact mode and foldable long output
- exportable session snapshot JSON

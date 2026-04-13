# HappyTrace

HappyTrace is a small observability playground for agent session logs.

Current scope:

- single-file HTML viewer
- reads local Hermes and Codex session logs
- works as a static page with browser directory access
- supports session list, event timeline, detail panel, search, and filters

## Files

- `happytrace.html` — current local-session log viewer
- `prototypes/agent-observer.html` — earlier generic observer prototype

## How to use

### Recommended: serve locally

```bash
cd /Users/samsoncj/develop/happytrace
python3 -m http.server 8000
```

Then open:

```text
http://localhost:8000/happytrace.html
```

Click **连接 sessions 目录** and choose one of these:

```text
/Users/samsoncj/.hermes
/Users/samsoncj/.hermes/sessions
/Users/samsoncj/.codex
/Users/samsoncj/.codex/sessions
```

After permission is granted, the page can:

- remember the directory handle in IndexedDB
- reload local sessions from that directory tree
- auto-refresh every 5 seconds

### Fallback

If your browser does not support persistent directory handles well, use the folder picker input and manually select the same directory.

## Runtimes currently supported

### Hermes

HappyTrace currently reads:

- `sessions.json`
- `session_*.json`

from the local Hermes sessions directory.

It maps Hermes messages into observer events such as:

- `UserPromptSubmit`
- `AssistantToolCall`
- `ToolResult`
- `AssistantMessage`
- `Stop`

### Codex

HappyTrace currently reads Codex rollout logs from `.jsonl` files under the local Codex sessions tree, plus optional metadata from:

- `session_index.jsonl`

It maps Codex entries into observer events such as:

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

## Notes

- This is intentionally static-first.
- Browsers cannot silently read arbitrary local files without permission.
- So the practical model is: first grant directory access, then let the page auto-refresh.
- The current goal is cross-runtime session log inspection, not a Hermes-only viewer.

## Next ideas

- better tool-call and tool-result pairing
- more runtime adapters: Claude, OpenCode, Gemini CLI
- project / platform grouping
- richer token / model / source metadata
- compact mode and foldable long output
- exportable session snapshot JSON

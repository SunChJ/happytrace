#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable


def read_json(text: str):
    try:
        return json.loads(text)
    except Exception:
        return None


def to_iso(ms: int | float | None) -> str:
    if ms is None:
        return ""
    try:
        return datetime.fromtimestamp(float(ms) / 1000).astimezone().isoformat(timespec="seconds")
    except Exception:
        return ""


def compact_json(value) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ": "))
    except Exception:
        return str(value)


def summarize_tool_state(state: dict) -> str:
    lines: list[str] = []
    title = state.get("title")
    status = state.get("status")
    if title:
        lines.append(f"title: {title}")
    if status:
        lines.append(f"status: {status}")
    tool_input = state.get("input")
    if tool_input not in (None, "", {}):
        lines.append(f"input: {compact_json(tool_input)}")
    tool_output = state.get("output")
    if tool_output not in (None, "", {}):
        lines.append(f"output: {tool_output if isinstance(tool_output, str) else compact_json(tool_output)}")
    return "\n".join(lines)


def render_part_text(part_data) -> str:
    if not isinstance(part_data, dict):
        return str(part_data or "")

    kind = part_data.get("type")
    if kind == "text":
        return str(part_data.get("text") or "").strip()
    if kind == "reasoning":
        text = str(part_data.get("text") or part_data.get("summary") or "").strip()
        return f"[reasoning]\n{text}" if text else "[reasoning]"
    if kind == "tool":
        tool_name = part_data.get("tool") or "tool"
        call_id = part_data.get("callID") or ""
        state = part_data.get("state") if isinstance(part_data.get("state"), dict) else {}
        body = summarize_tool_state(state)
        header = f"[tool:{tool_name}{f' #{call_id}' if call_id else ''}]"
        return f"{header}\n{body}".strip()
    if kind == "step-start":
        snapshot = part_data.get("snapshot")
        return f"[step-start{f' snapshot={snapshot}' if snapshot else ''}]"
    if kind == "step-finish":
        reason = part_data.get("reason") or ""
        tokens = part_data.get("tokens")
        suffix = []
        if reason:
            suffix.append(f"reason={reason}")
        if isinstance(tokens, dict) and tokens.get("total") is not None:
            suffix.append(f"tokens.total={tokens.get('total')}")
        return f"[step-finish{' ' + ' · '.join(suffix) if suffix else ''}]"
    return compact_json(part_data)


def build_conversation_history(session_payload: dict) -> dict:
    entries: list[dict] = []
    markdown_blocks: list[str] = []

    for message in session_payload.get("messages", []):
        data = message.get("data") if isinstance(message.get("data"), dict) else {}
        role = data.get("role") or "unknown"
        agent = data.get("agent") or data.get("mode") or ""
        model = data.get("modelID") or data.get("model", {}).get("modelID") or ""
        created_at = to_iso(message.get("time_created"))
        rendered_parts = []
        for part in message.get("parts", []):
            text = render_part_text(part.get("data"))
            if text:
                rendered_parts.append(text)
        content = "\n\n".join(rendered_parts).strip()
        if not content and isinstance(data, dict):
            fallback = data.get("text") or data.get("summary")
            if isinstance(fallback, str):
                content = fallback.strip()
            elif fallback not in (None, "", {}):
                content = compact_json(fallback)

        entry = {
            "message_id": message.get("id"),
            "role": role,
            "agent": agent,
            "model": model,
            "time": created_at,
            "content": content,
        }
        entries.append(entry)

        header_bits = [role]
        if agent:
            header_bits.append(agent)
        if model:
            header_bits.append(model)
        if created_at:
            header_bits.append(created_at)
        header = " · ".join(header_bits)
        markdown_blocks.append(f"## {header}\n\n{content or '[empty]'}")

    return {
        "message_count": len(entries),
        "entries": entries,
        "markdown": "\n\n".join(markdown_blocks).strip(),
        "plain_text": "\n\n".join(
            f"[{entry['role']}] {entry['content'] or '[empty]'}" for entry in entries
        ).strip(),
    }


def export_session(conn: sqlite3.Connection, sess: sqlite3.Row) -> dict:
    cur = conn.cursor()
    session_id = sess["id"]
    messages = cur.execute(
        "select id, time_created, time_updated, data from message where session_id=? order by time_created asc, id asc",
        (session_id,),
    ).fetchall()
    parts = cur.execute(
        "select message_id, time_created, time_updated, data from part where session_id=? order by time_created asc, id asc",
        (session_id,),
    ).fetchall()

    parts_by_message = defaultdict(list)
    for row in parts:
        parsed = read_json(row["data"])
        parts_by_message[row["message_id"]].append(
            {
                "time_created": row["time_created"],
                "time_updated": row["time_updated"],
                "data": parsed if parsed is not None else row["data"],
            }
        )

    exported_messages = []
    for row in messages:
        parsed = read_json(row["data"])
        exported_messages.append(
            {
                "id": row["id"],
                "time_created": row["time_created"],
                "time_updated": row["time_updated"],
                "data": parsed if parsed is not None else row["data"],
                "parts": parts_by_message.get(row["id"], []),
            }
        )

    payload = {
        "happytrace_format": "opencode-session-v1",
        "runtime": "OpenCode",
        "session": {
            "id": sess["id"],
            "slug": sess["slug"],
            "project_id": sess["project_id"],
            "directory": sess["directory"],
            "title": sess["title"],
            "version": sess["version"],
            "time_created": sess["time_created"],
            "time_updated": sess["time_updated"],
        },
        "messages": exported_messages,
    }
    payload["conversation_history"] = build_conversation_history(payload)
    return payload


def sanitize_filename(name: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in (name or "session"))
    while "--" in safe:
        safe = safe.replace("--", "-")
    return safe.strip("-") or "session"


def select_sessions(cur: sqlite3.Cursor, session_ids: set[str], slug_query: str, limit: int) -> list[sqlite3.Row]:
    sessions = cur.execute(
        "select id, slug, project_id, directory, title, version, time_created, time_updated from session order by time_updated desc"
    ).fetchall()
    if session_ids:
        sessions = [row for row in sessions if row["id"] in session_ids]
    if slug_query:
        lowered = slug_query.lower()
        sessions = [
            row
            for row in sessions
            if lowered in str(row["slug"] or "").lower() or lowered in str(row["title"] or "").lower()
        ]
    if limit > 0:
        sessions = sessions[:limit]
    return sessions


def write_exports(payloads: Iterable[dict], output_dir: Path, history_output_dir: Path | None) -> list[Path]:
    written: list[Path] = []
    output_dir.mkdir(parents=True, exist_ok=True)
    if history_output_dir is not None:
        history_output_dir.mkdir(parents=True, exist_ok=True)

    for payload in payloads:
        session_id = payload["session"]["id"]
        out_path = output_dir / f"opencode-session-{session_id}.json"
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(out_path)
        if history_output_dir is not None:
            base = sanitize_filename(payload["session"].get("title") or payload["session"].get("slug") or session_id)
            history_path = history_output_dir / f"opencode-history-{base}-{session_id}.md"
            history_path.write_text(payload["conversation_history"]["markdown"] + "\n", encoding="utf-8")
            written.append(history_path)
    return written


def emit_stdout(payloads: list[dict], history_only: bool) -> None:
    if history_only:
        for idx, payload in enumerate(payloads):
            if idx:
                print("\n\n" + ("=" * 80) + "\n\n")
            print(payload["conversation_history"]["markdown"])
        return

    if len(payloads) == 1:
        print(json.dumps(payloads[0], ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payloads, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export OpenCode SQLite sessions into HappyTrace JSON cache")
    parser.add_argument("--db", default=str(Path.home() / ".local/share/opencode/opencode-local.db"))
    parser.add_argument("--output-dir", default=str(Path.home() / ".local/share/opencode/happytrace-cache"))
    parser.add_argument("--history-output-dir", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--session-id", action="append", default=[])
    parser.add_argument("--slug", default="", help="Filter session by slug or title substring")
    parser.add_argument("--stdout", action="store_true", help="Print exported payload(s) to stdout instead of only writing files")
    parser.add_argument("--history-only", action="store_true", help="Print reconstructed full conversation history markdown to stdout")
    return parser.parse_args()


def main():
    args = parse_args()

    db_path = Path(args.db).expanduser()
    out_dir = Path(args.output_dir).expanduser()
    history_output_dir = Path(args.history_output_dir).expanduser() if args.history_output_dir else None

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    sessions = select_sessions(cur, set(args.session_id), args.slug, args.limit)
    payloads = [export_session(conn, sess) for sess in sessions]

    if not payloads:
        raise SystemExit("No OpenCode sessions matched the given filters.")

    written = write_exports(payloads, out_dir, history_output_dir)
    for path in written:
        print(path, file=sys.stderr)

    if args.stdout or args.history_only:
        emit_stdout(payloads, history_only=args.history_only)


if __name__ == "__main__":
    main()

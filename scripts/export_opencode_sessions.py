#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from collections import defaultdict


def read_json(text: str):
    try:
        return json.loads(text)
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="Export OpenCode SQLite sessions into HappyTrace JSON cache")
    parser.add_argument("--db", default=str(Path.home() / ".local/share/opencode/opencode-local.db"))
    parser.add_argument("--output-dir", default=str(Path.home() / ".local/share/opencode/happytrace-cache"))
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    db_path = Path(args.db).expanduser()
    out_dir = Path(args.output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    sessions = cur.execute(
        "select id, slug, project_id, directory, title, version, time_created, time_updated from session order by time_updated desc"
    ).fetchall()
    if args.limit > 0:
        sessions = sessions[: args.limit]

    for sess in sessions:
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
            parts_by_message[row["message_id"]].append({
                "time_created": row["time_created"],
                "time_updated": row["time_updated"],
                "data": parsed if parsed is not None else row["data"],
            })

        exported_messages = []
        for row in messages:
            parsed = read_json(row["data"])
            exported_messages.append({
                "id": row["id"],
                "time_created": row["time_created"],
                "time_updated": row["time_updated"],
                "data": parsed if parsed is not None else row["data"],
                "parts": parts_by_message.get(row["id"], []),
            })

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

        out_path = out_dir / f"opencode-session-{session_id}.json"
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(out_path)


if __name__ == "__main__":
    main()

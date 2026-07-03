#!/usr/bin/env python3
"""
Claude Code session token usage reporter.
Recursively scans a directory for .jsonl session files and outputs a JSON report
grouped by project (subfolder) -> session (filename stem).

Usage:
    python3 claude_token_report.py <root_dir> [--out <output_file>]
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict

IST = timezone(timedelta(hours=5, minutes=30))


def parse_args():
    parser = argparse.ArgumentParser(description="Claude Code token usage reporter")
    parser.add_argument("root", help="Root directory to scan for .jsonl files")
    parser.add_argument(
        "--out",
        help="Output JSON file path (default: timestamped file in cwd)",
        default=None,
    )
    return parser.parse_args()


def empty_usage():
    return {
        "input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_creation_5m_tokens": 0,
        "cache_creation_1h_tokens": 0,
        "cache_read_input_tokens": 0,
        "output_tokens": 0,
        "turns": 0,
    }


def add_usage(acc, u):
    acc["input_tokens"] += u.get("input_tokens", 0)
    acc["cache_creation_input_tokens"] += u.get("cache_creation_input_tokens", 0)
    cc = u.get("cache_creation", {})
    acc["cache_creation_5m_tokens"] += cc.get("ephemeral_5m_input_tokens", 0)
    acc["cache_creation_1h_tokens"] += cc.get("ephemeral_1h_input_tokens", 0)
    acc["cache_read_input_tokens"] += u.get("cache_read_input_tokens", 0)
    acc["output_tokens"] += u.get("output_tokens", 0)
    acc["turns"] += 1


def sum_usage(usages):
    acc = empty_usage()
    for u in usages:
        for k in acc:
            acc[k] += u[k]
    return acc


def scan_directory(root: Path):
    data = defaultdict(dict)

    for filepath in sorted(root.rglob("*.jsonl")):
        rel = filepath.relative_to(root)
        parts = rel.parts

        project_name = str(Path(*parts[:-1])) if len(parts) > 1 else "(root)"
        session_id = filepath.stem

        usage = empty_usage()
        first_ts = None
        last_ts = None
        models = set()

        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg = obj.get("message", {})
                u = msg.get("usage")
                if not u:
                    continue

                add_usage(usage, u)

                ts = obj.get("timestamp")
                if ts:
                    if first_ts is None or ts < first_ts:
                        first_ts = ts
                    if last_ts is None or ts > last_ts:
                        last_ts = ts

                model = msg.get("model")
                if model:
                    models.add(model)

        if usage["turns"] == 0:
            continue

        data[project_name][session_id] = {
            "usage": usage,
            "first_turn_at": first_ts,
            "last_turn_at": last_ts,
            "models": sorted(models),
        }

    return data


def build_report(data, root: Path):
    projects = []

    for project_name in sorted(data.keys()):
        sessions_raw = data[project_name]
        sessions = []

        for session_id in sorted(sessions_raw.keys()):
            s = sessions_raw[session_id]
            sessions.append({
                "session_id": session_id,
                "first_turn_at": s["first_turn_at"],
                "last_turn_at": s["last_turn_at"],
                "models": s["models"],
                "usage": s["usage"],
            })

        project_usage = sum_usage([s["usage"] for s in sessions])

        projects.append({
            "project": project_name,
            "session_count": len(sessions),
            "usage": project_usage,
            "sessions": sessions,
        })

    totals = sum_usage([p["usage"] for p in projects])

    return {
        "meta": {
            "root": str(root),
            "generated_at": datetime.now(IST).isoformat(),
            "project_count": len(projects),
            "session_count": sum(p["session_count"] for p in projects),
        },
        "totals": totals,
        "projects": projects,
    }


def main():
    args = parse_args()
    root = Path(args.root).expanduser().resolve()

    if not root.is_dir():
        print(f"Error: {root} is not a directory", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning {root} ...", file=sys.stderr)
    data = scan_directory(root)

    if not data:
        print("No sessions with usage data found.", file=sys.stderr)
        sys.exit(1)

    report = build_report(data, root)
    print(
        f"Found {report['meta']['project_count']} project(s), "
        f"{report['meta']['session_count']} session(s)",
        file=sys.stderr,
    )

    if args.out:
        out_path = Path(args.out)
    else:
        ts = datetime.now(IST).strftime("%Y_%m_%d_%H%M")
        out_path = Path.cwd() / f"{ts}-claude-token-report.json"

    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Report written to: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()

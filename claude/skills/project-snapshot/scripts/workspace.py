#!/usr/bin/env python3
"""
Workspace helper shared by the project-snapshot and actuals-snapshot skills.
Run from the workspace folder (the folder holding config.json and people.csv).
Uses only the standard library and works on Windows, macOS and Linux.

Usage:
    python3 workspace.py check
    python3 workspace.py init --pm NAME [--pm NAME ...]
                              --projects-folder LINK_OR_ID --allocations-folder LINK_OR_ID
                              [--timesheets-folder LINK_OR_ID] [--root-folder LINK_OR_ID]
    python3 workspace.py settings-block
    python3 workspace.py count-projects RESPONSE_FILE
    python3 workspace.py clean FILE [FILE ...]
    python3 workspace.py clean --all

check           Prints JSON: whether both skills are installed side by side, and
                what config.json / people.csv are missing.
init            Creates or completes config.json (merging into an existing one)
                and creates people.csv with only its header row if it is missing.
                Then prints the Settings paste block.
settings-block  Prints the tab-separated Settings rows for the planning sheet.
count-projects  Prints the number of projects in a saved get_projects_list page.
clean           Deletes the given files under tmp/ (globs allowed) and removes
                tmp/ if it is then empty. --all removes tmp/ entirely.
"""

import argparse
import csv
import glob
import json
import os
import re
import shutil
import sys

CONFIG = "config.json"
PEOPLE = "people.csv"
TMP = "tmp"
PEOPLE_FIELDS = ["person_name", "person_zpuid", "person_email", "team"]
REQUIRED_PEOPLE = ["person_name", "person_zpuid", "team"]

# Both skills are installed as siblings: <skills_root>/project-snapshot and
# <skills_root>/actuals-snapshot. Resolve them relative to this file so any
# install location and OS works.
HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS_ROOT = os.path.dirname(os.path.dirname(HERE))
SKILL_SCRIPTS = {
    "project-snapshot": ["build_projects.py", "workspace.py"],
    "actuals-snapshot": ["process_actuals.py"],
}

# Settings rows in the planning sheet, in the order "Planning → Set up sheet" writes them.
SETTINGS_ROWS = [
    ("projects_folder", "projects_folder_id"),
    ("allocations_folder", "allocations_folder_id"),
    ("timesheets_folder", "timesheets_folder_id"),
]


def folder_id(value):
    """Accepts a Drive folder link or a bare ID."""
    value = value.strip()
    m = re.search(r"folders/([\w-]+)", value) or re.search(r"[?&]id=([\w-]+)", value)
    return m.group(1) if m else value


def folder_link(fid):
    return f"https://drive.google.com/drive/folders/{fid}"


def read_config():
    if not os.path.exists(CONFIG):
        return None
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


def cmd_check(_args):
    skills = {}
    for name, scripts in SKILL_SCRIPTS.items():
        d = os.path.join(SKILLS_ROOT, name)
        missing = [s for s in scripts if not os.path.isfile(os.path.join(d, "scripts", s))]
        skills[name] = {"installed": not missing, "path": d.replace("\\", "/"), "missing_scripts": missing}

    cfg = read_config()
    config = {"exists": cfg is not None, "missing": []}
    if cfg is not None:
        drive = cfg.get("drive") or {}
        if not cfg.get("pm_filter"):
            config["missing"].append("pm_filter")
        for key in ("projects_folder_id", "allocations_folder_id"):
            if not drive.get(key):
                config["missing"].append(f"drive.{key}")
    else:
        config["missing"] = ["pm_filter", "drive.projects_folder_id", "drive.allocations_folder_id"]

    people = {"exists": os.path.exists(PEOPLE), "missing_columns": []}
    if people["exists"]:
        with open(PEOPLE, encoding="utf-8", newline="") as f:
            header = next(csv.reader(f), [])
        people["missing_columns"] = [c for c in REQUIRED_PEOPLE if c not in header]

    print(json.dumps({
        "workspace": os.getcwd().replace("\\", "/"),
        "skills": skills,
        "config": config,
        "people": people,
        "ready": all(s["installed"] for s in skills.values())
                 and not config["missing"] and people["exists"] and not people["missing_columns"],
    }, indent=2))


def print_settings_block(cfg):
    drive = cfg.get("drive") or {}
    rows = [(name, drive.get(key)) for name, key in SETTINGS_ROWS]
    print("SETTINGS BLOCK (tab-separated, paste at Settings!A2):")
    for name, fid in rows:
        print(f"{name}\t{folder_link(fid) if fid else ''}")


def cmd_init(args):
    cfg = read_config() or {}
    if args.pm:
        cfg["pm_filter"] = [n.strip() for n in args.pm if n.strip()]
    drive = cfg.setdefault("drive", {})
    for opt, key in (("root_folder", "root_folder_id"), ("projects_folder", "projects_folder_id"),
                     ("allocations_folder", "allocations_folder_id"),
                     ("timesheets_folder", "timesheets_folder_id")):
        value = getattr(args, opt)
        if value:
            drive[key] = folder_id(value)

    if not cfg.get("pm_filter"):
        print("ERROR: pm_filter is empty — pass at least one --pm name.")
        raise SystemExit(1)
    with open(CONFIG, "w", encoding="utf-8", newline="\n") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Wrote {CONFIG}")

    if not os.path.exists(PEOPLE):
        with open(PEOPLE, "w", encoding="utf-8", newline="") as f:
            csv.writer(f, lineterminator="\n").writerow(PEOPLE_FIELDS)
        print(f"Created {PEOPLE} (header only)")

    print_settings_block(cfg)


def cmd_settings_block(_args):
    cfg = read_config()
    if cfg is None:
        print(f"ERROR: {CONFIG} not found.")
        raise SystemExit(1)
    print_settings_block(cfg)


def cmd_count_projects(args):
    sys.path.insert(0, HERE)
    from build_projects import extract_projects
    with open(args.file, encoding="utf-8") as f:
        print(len(extract_projects(json.load(f))))


def cmd_clean(args):
    if args.all:
        shutil.rmtree(TMP, ignore_errors=True)
        print(f"Removed {TMP}/")
        return
    for pattern in args.files:
        for path in glob.glob(os.path.join(TMP, os.path.basename(pattern))):
            os.remove(path)
            print(f"Deleted {path.replace(os.sep, '/')}")
    if os.path.isdir(TMP) and not os.listdir(TMP):
        os.rmdir(TMP)
        print(f"Removed empty {TMP}/")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows pipes default to cp1252

    parser = argparse.ArgumentParser(description="Workspace helper for the Zoho snapshot skills.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check").set_defaults(func=cmd_check)

    p = sub.add_parser("init")
    p.add_argument("--pm", action="append", default=[], help="PM name for pm_filter (repeatable)")
    p.add_argument("--root-folder")
    p.add_argument("--projects-folder")
    p.add_argument("--allocations-folder")
    p.add_argument("--timesheets-folder")
    p.set_defaults(func=cmd_init)

    sub.add_parser("settings-block").set_defaults(func=cmd_settings_block)

    p = sub.add_parser("count-projects")
    p.add_argument("file")
    p.set_defaults(func=cmd_count_projects)

    p = sub.add_parser("clean")
    p.add_argument("files", nargs="*", help="File names or globs inside tmp/")
    p.add_argument("--all", action="store_true", help="Remove tmp/ entirely")
    p.set_defaults(func=cmd_clean)

    args = parser.parse_args()
    if args.cmd == "clean" and not args.all and not args.files:
        parser.error("clean needs file names or --all")
    args.func(args)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Build tmp/YYYY_MM_DD_HHMM_projects.csv from saved get_projects_list
responses. The CSV is transient: the skill uploads it to Drive, then deletes it. The list response carries every field the CSV
needs, so no per-project detail calls are made.

Usage:
    python3 scripts/build_projects.py --month YYYY-MM RESPONSE_FILE [RESPONSE_FILE ...]

RESPONSE_FILE is a get_projects_list response saved by Claude Code (or written
out by hand): the bare API body, or MCP content wrapping it as text. Pass one
file per page. Run from the repo root; reads config.json for pm_filter.
The last line printed is the CSV path.
"""

import argparse
import csv
import html
import json
import os
import re
import subprocess
from calendar import monthrange
from datetime import date


# ── constants ─────────────────────────────────────────────────────────────────

CONFIG = "config.json"
OUT_DIR = "tmp"  # transient; Drive holds the exports
ACTIVE_STATUSES = {"In Progress", "UAT", "Warranty", "On Hold"}
COMPLETED_STATUSES = {"complete", "completed"}  # always excluded, whatever else matches

COLUMNS = [
    "project_id", "project_name", "project_key", "status", "status_label", "stage",
    "engagement_model", "skills_required", "client_name", "account_manager",
    "invoicing_type", "priced_by_finance", "start_date", "end_date", "estimated_hours",
    "ballpark_hours", "monthly_budget", "percent_complete", "csat", "assigned_to",
    "project_folder", "url_live", "url_staging", "git_hub", "project_manager",
    "description", "risk_category", "seo", "sold_hours", "contract", "delivery_tier",
    "roas", "quality", "design_adherence", "sm_engagement", "uat_report",
    "re_allocation_note", "internal_delivery_date", "uat_date", "designers",
    "completed_time", "hsid",
]


# ── helpers ───────────────────────────────────────────────────────────────────

def extract_projects(data):
    """Return the project array from a get_projects_list response in any of
    the shapes it arrives in: the bare API body, or MCP content wrapping it."""
    if isinstance(data, list):
        out = []
        for item in data:
            if isinstance(item, dict) and item.get("type") == "text":
                out.extend(extract_projects(json.loads(item["text"])))
            elif isinstance(item, dict) and "id" in item:
                out.append(item)
        return out
    if "content" in data:
        return extract_projects(data["content"])
    if "data" in data:
        inner = data["data"]
        if isinstance(inner, list):
            return extract_projects(inner)
        return inner.get("result") or inner.get("projects") or []
    return data.get("result") or data.get("projects") or []


def text(v):
    return "" if v is None else str(v)


def joined(v, key=None):
    if v is None:
        return ""
    if isinstance(v, list):
        return ";".join(text(x.get(key) if key and isinstance(x, dict) else x) for x in v)
    return text(v)


def url(v):
    v = text(v)
    return "" if v.strip() in ("https://", "http://") else v


def strip_html(h):
    if not h:
        return ""
    t = re.sub(r"<br\s*/?>|</(p|div|li|tr|h\d)>", "\n", h, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t).replace("\xa0", " ")
    return "\n".join(line.strip() for line in t.splitlines() if line.strip())


def owner_name(p):
    o = p.get("owner")
    return text(o.get("name") if isinstance(o, dict) else o)


def user_text(v):
    """Searchable text for a user field (manager_2_0, assigned_to): a user object
    ({full_name, name, email, ...}) or a list of them. `name` is sometimes a
    username such as "first.last", so all three are matched."""
    users = v if isinstance(v, list) else [v] if isinstance(v, dict) else []
    return " ".join(f"{text(u.get('full_name'))} {text(u.get('name'))} {text(u.get('email'))}" for u in users)


def matches_pm(p, names):
    pm = p.get("project_manager")
    haystack = " ".join([
        owner_name(p),
        pm if isinstance(pm, str) else "",
        user_text(p.get("manager_2_0")),
        user_text(p.get("assigned_to")),
    ]).lower()
    return any(n.lower() in haystack for n in names)


def monthly_budget(p, month_start, month_end):
    sd, ed, est = p.get("start_date"), p.get("end_date"), p.get("estimated_hours")
    if not sd or not ed or est is None:
        return ""
    sd, ed = date.fromisoformat(sd[:10]), date.fromisoformat(ed[:10])
    overlap = max(0, (min(ed, month_end) - max(sd, month_start)).days + 1)
    duration = max(1, (ed - sd).days + 1)
    return 0.0 if overlap == 0 else round(float(est) * overlap / duration, 2)


def row(p, month_start, month_end):
    return {
        "project_id":             text(p.get("id")),
        "project_name":           text(p.get("name")),
        "project_key":            text(p.get("key")),
        "status":                 text(p.get("project_status")),
        "status_label":           text((p.get("status") or {}).get("name")),
        "stage":                  text(p.get("stage")),
        "engagement_model":       text(p.get("engagement_model")),
        "skills_required":        joined(p.get("skill")),
        "client_name":            text(p.get("client_name")),
        "account_manager":        joined(p.get("account_manager")),
        "invoicing_type":         text(p.get("invoicing_type")),
        "priced_by_finance":      text(p.get("priced_by_finance")),
        "start_date":             text(p.get("start_date")),
        "end_date":               text(p.get("end_date")),
        "estimated_hours":        text(p.get("estimated_hours")),
        "ballpark_hours":         text(p.get("ballpark_hours_2_0")),
        "monthly_budget":         monthly_budget(p, month_start, month_end),
        "percent_complete":       text(p.get("percent_complete")),
        "csat":                   joined(p.get("csat")),
        "assigned_to":            text((p.get("assigned_to") or {}).get("full_name")),
        "project_folder":         text(p.get("project_folder")),
        "url_live":               url(p.get("url_live")),
        "url_staging":            url(p.get("url_staging")),
        "git_hub":                text(p.get("git_hub")),
        "project_manager":        text(p.get("project_manager")),
        "description":            strip_html(p.get("description")),
        "risk_category":          joined(p.get("risk_category")),
        "seo":                    text(p.get("seo")),
        "sold_hours":             text(p.get("sold_hours_2_0")),
        "contract":               text(p.get("contract")),
        "delivery_tier":          text(p.get("delivery_tier")),
        "roas":                   text(p.get("roas")),
        "quality":                text(p.get("quality")),
        "design_adherence":       text(p.get("design_adherence")),
        "sm_engagement":          text(p.get("sm_engagement")),
        "uat_report":             text(p.get("uat_report")),
        "re_allocation_note":     text(p.get("re_allocation_note")),
        "internal_delivery_date": text(p.get("internal_delivery_date")),
        "uat_date":               text(p.get("uat_date")),
        "designers":              joined(p.get("designers"), "full_name"),
        "completed_time":         text(p.get("completed_time")),
        "hsid":                   text(p.get("hsid")),
    }


def ist(fmt_args):
    return subprocess.check_output(["bash", "-c", f"TZ='Asia/Kolkata' date {fmt_args}"]).decode().strip()


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Build the projects CSV from saved list responses.")
    parser.add_argument("--month", metavar="YYYY-MM", required=True, help="Target month")
    parser.add_argument("files", nargs="+", help="Saved get_projects_list response file(s), one per page")
    args = parser.parse_args()

    year, mon = map(int, args.month.split("-"))
    month_start = date(year, mon, 1)
    month_end = date(year, mon, monthrange(year, mon)[1])

    with open(CONFIG) as f:
        pm_filter = json.load(f).get("pm_filter") or []
    if not pm_filter:
        print(f"ERROR: {CONFIG} has no pm_filter names.")
        raise SystemExit(1)

    projects = {}
    for path in args.files:
        with open(path) as f:
            for p in extract_projects(json.load(f)):
                projects[str(p.get("id"))] = p  # pages can overlap; keep one per id
    if not projects:
        print("ERROR: no projects found in the response file(s).")
        raise SystemExit(1)

    kept = [
        p for p in projects.values()
        if p.get("project_type") == "active"
        and p.get("project_status") in ACTIVE_STATUSES
        and text(p.get("project_status")).strip().lower() not in COMPLETED_STATUSES
        and not p.get("is_completed")
        and matches_pm(p, pm_filter)  # presales projects are kept when they match
    ]
    if not kept:
        print(f"ERROR: no projects pass the filters (pm_filter: {', '.join(pm_filter)}).")
        raise SystemExit(1)

    rows = sorted((row(p, month_start, month_end) for p in kept), key=lambda r: r["project_name"])

    os.makedirs(OUT_DIR, exist_ok=True)
    ts = ist("'+%Y_%m_%d_%H%M'")
    csv_path = os.path.join(OUT_DIR, f"{ts}_projects.csv")

    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    null_hours = [r["project_name"] for r in rows if r["estimated_hours"] == ""]
    missing_budget = [r["project_name"] for r in rows if r["estimated_hours"] != "" and r["monthly_budget"] == ""]

    print(f"Run complete — {args.month}")
    print(f"Projects in list:         {len(projects)}")
    print(f"Projects exported:        {len(rows)}")
    print(f"Missing budget (has hrs): {len(missing_budget)}"
          + (f" — {', '.join(missing_budget)}" if missing_budget else ""))
    print(f"Null estimated_hours:     {len(null_hours)}"
          + (f" — {', '.join(null_hours)}" if null_hours else ""))
    print(csv_path)


if __name__ == "__main__":
    main()

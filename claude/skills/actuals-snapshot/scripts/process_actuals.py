#!/usr/bin/env python3
"""
Aggregate allocated hours from tmp/actuals_partial.ndjson and write
tmp/YYYY_MM_DD_HHMM_allocations.csv. The CSV is transient: the skill uploads
it to Drive, then deletes tmp/.

Logged hours are not computed here — they come from the weekly Zoho timesheet
xlsx, which the planning sheet's Apps Script reads directly.

Also backfills person_email in people.csv from task owner data.

Usage:
    python3 scripts/process_actuals.py [--month YYYY-MM]
    python3 scripts/process_actuals.py [--month YYYY-MM] --check-people

--check-people prints owners of in-month tasks that are missing from
people.csv as a JSON list of {zpuid, name, email} and writes nothing.

--month defaults to the current calendar month.
Run from the workspace folder. The last line printed is the CSV path.
"""

import argparse
import csv
import glob
import html
import json
import os
import sys
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone


# ── constants ─────────────────────────────────────────────────────────────────

PARTIAL  = "tmp/actuals_partial.ndjson"
PEOPLE   = "people.csv"
OUT_DIR  = "tmp"  # transient; Drive holds the exports
EXCLUDE  = {"0", "282451000000055461"}  # unassigned placeholder owners (same for every PM: one portal)
IST      = timezone(timedelta(hours=5, minutes=30))  # fixed offset: no DST, no tzdata needed on Windows

PEOPLE_FIELDS = ["person_name", "person_zpuid", "person_email", "team"]


# ── helpers ───────────────────────────────────────────────────────────────────

def hhmm_to_decimal(s):
    if s is None or s == "0":
        return 0.0
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).strip()
    if not s:
        return 0.0
    if ":" in s:
        h, m = s.split(":", 1)
        return int(h) + int(m) / 60.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_date(s):
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def overlaps_month(task, month_start, month_end):
    sd = parse_date(task.get("start_date"))
    ed = parse_date(task.get("end_date"))
    if sd is None and ed is None:
        return True  # undated → assumed active
    if sd is None:
        return ed >= month_start
    if ed is None:
        return sd <= month_end
    return sd <= month_end and ed >= month_start


def flexible_work_value(entries, month_start, month_end):
    """Sum a flexible-owner's date-keyed work_values, restricted to entries
    whose date falls within the target month (entries keyed by relative
    'day' offset instead of 'date' are included as-is — cannot resolve the
    offset without the task start_date, which is not preserved here)."""
    total = 0.0
    for entry in entries:
        d = parse_date(entry.get("date")) if isinstance(entry, dict) else None
        if d is not None and not (month_start <= d <= month_end):
            continue
        total += hhmm_to_decimal(entry.get("value") if isinstance(entry, dict) else entry)
    return total


def owner_raw_value(owner, month_start, month_end):
    """Each owner's own recorded work value, decimal hours.
    Handles both a plain 'HH:MM' string (unit=hours / hours_per_day / %_per_day —
    all are just numbers at this point) and a flexible date-keyed list."""
    wv = owner.get("work_values", "0")
    if isinstance(wv, list):
        return flexible_work_value(wv, month_start, month_end)
    return hhmm_to_decimal(wv)


def slim(tasks):
    """Extract only the fields needed for aggregation from raw API task objects."""
    out = []
    for t in tasks:
        ow = t.get("owners_and_work", {})
        rec = {
            "owners_and_work": {
                "work_type":  ow.get("work_type", "standard"),
                "total_work": ow.get("total_work", "00:00"),
                "owners": [
                    {
                        "zpuid":       str(o.get("zpuid", "")),
                        "name":        o.get("name", ""),
                        "email":       o.get("email", ""),
                        "work_values": o.get("work_values", "0"),
                    }
                    for o in ow.get("owners", [])
                ],
            },
        }
        if t.get("start_date"):
            rec["start_date"] = t["start_date"]
        if t.get("end_date"):
            rec["end_date"] = t["end_date"]
        out.append(rec)
    return out


def extract_tasks(data):
    """Return the task array from a get_tasks_by_project response in any of the
    shapes it arrives in: the bare API body, or MCP content wrapping it as text."""
    if isinstance(data, list):
        tasks = []
        for item in data:
            if isinstance(item, dict) and item.get("type") == "text":
                tasks.extend(extract_tasks(json.loads(item["text"])))
        return tasks
    if "content" in data:
        return extract_tasks(data["content"])
    if "data" in data:
        inner = data["data"]
        if isinstance(inner, list):
            return extract_tasks(inner)
        return inner.get("tasks", [])
    return data.get("tasks", [])


def load_tasks_from_file(path):
    with open(path, encoding="utf-8") as f:
        return slim(extract_tasks(json.load(f)))


def record_tasks(rec):
    """Tasks for one partial-file record: inline, or from saved response file(s)."""
    files = rec.get("tasks_files") or ([rec["tasks_file"]] if rec.get("tasks_file") else [])
    if files:
        return [t for path in files for t in load_tasks_from_file(path)]
    return slim(rec.get("tasks", []))


def iter_partial():
    with open(PARTIAL, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def unknown_people(people, month_start, month_end):
    """Owners of in-month tasks whose zpuid is not in people.csv. When a zpuid
    appears under several names, prefer one containing a space (a full name)
    over a username-style string."""
    seen = {}
    for rec in iter_partial():
        for task in record_tasks(rec):
            if not overlaps_month(task, month_start, month_end):
                continue
            for o in task["owners_and_work"].get("owners", []):
                zpuid = str(o.get("zpuid", ""))
                if zpuid in EXCLUDE or zpuid in people:
                    continue
                name = (o.get("name") or "").strip()
                cur = seen.setdefault(zpuid, {"zpuid": zpuid, "name": name, "email": ""})
                if " " in name and " " not in cur["name"]:
                    cur["name"] = name
                if o.get("email"):
                    cur["email"] = o["email"].strip().lower()
    return sorted(seen.values(), key=lambda p: p["name"].lower())


def read_people():
    with open(PEOPLE, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row.setdefault("person_email", "")
        for k in PEOPLE_FIELDS:
            row[k] = (row.get(k) or "").strip()
    return rows


def write_people(rows):
    with open(PEOPLE, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=PEOPLE_FIELDS, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows pipes default to cp1252

    parser = argparse.ArgumentParser(description="Aggregate Zoho allocated hours for a given month.")
    parser.add_argument(
        "--month",
        metavar="YYYY-MM",
        help="Target month (default: current calendar month)",
    )
    parser.add_argument(
        "--check-people",
        action="store_true",
        help="List in-month task owners missing from people.csv as JSON, then exit",
    )
    parser.add_argument(
        "--skip",
        metavar="ZPUID[,ZPUID...]",
        default="",
        help="Comma-separated zpuids to leave out of this run (people marked 'skip')",
    )
    args = parser.parse_args()

    # Resolve target month
    if args.month:
        year, mon = map(int, args.month.split("-"))
    else:
        today = date.today()
        year, mon = today.year, today.month

    month_start = date(year, mon, 1)
    month_end   = date(year, mon, monthrange(year, mon)[1])
    target_month = f"{year:04d}-{mon:02d}"

    if not args.check_people:
        print(f"Target month: {target_month}  ({month_start} → {month_end})")

    # Validate inputs
    if not os.path.exists(PARTIAL):
        print(f"ERROR: {PARTIAL} not found. Run the fetch phase first.")
        raise SystemExit(1)
    if not os.path.exists(PEOPLE):
        print(f"ERROR: {PEOPLE} not found.")
        raise SystemExit(1)

    skip = {z.strip() for z in args.skip.split(",") if z.strip()}
    people_rows = read_people()
    people = {r["person_zpuid"]: r for r in people_rows}

    if args.check_people:
        print(json.dumps(unknown_people(people, month_start, month_end), indent=2))
        return

    agg = {}            # (project_id, zpuid) → {"allocated": float, "project_name": str}
    seen_email = {}     # zpuid → email from task owner data
    projects_processed = 0
    fetch_failed = []

    for rec in iter_partial():
            projects_processed += 1
            pid   = rec["project_id"]
            pname = html.unescape(rec["project_name"])
            if rec.get("fetch_failed"):
                fetch_failed.append(pname)

            for task in record_tasks(rec):
                ow = task["owners_and_work"]

                # Skip tasks outside target month (unless undated)
                if not overlaps_month(task, month_start, month_end):
                    continue

                total_work = hhmm_to_decimal(ow.get("total_work", "00:00"))
                owners     = ow.get("owners", [])

                # Each owner's own raw value (their `work_values`, decimal hours).
                # Zoho's `unit` field (Total hours / Work hours per day / Work % per
                # day) is irrelevant here: whichever unit was used, `total_work` is
                # always the task-level total, and owners' raw values only equal
                # that total when the task has a single owner AND unit is "hours".
                # For hours_per_day/%_per_day (or any multi-owner split), each
                # owner's raw value is a *rate*, not a total — so we redistribute
                # total_work proportional to each owner's raw-value share. This
                # self-corrects for the "hours" case too, where the ratio is 1:1.
                raw_values = {
                    str(o.get("zpuid", "")): owner_raw_value(o, month_start, month_end)
                    for o in owners
                }
                raw_sum = sum(raw_values.values())
                is_flexible = any(isinstance(o.get("work_values"), list) for o in owners)

                for o in owners:
                    zpuid = str(o.get("zpuid", ""))
                    if zpuid in EXCLUDE or zpuid in skip:
                        continue
                    if o.get("email"):
                        seen_email[zpuid] = o["email"].strip().lower()

                    if is_flexible:
                        # Date-keyed entries are already resolved to the target
                        # month in owner_raw_value — use directly, no redistribution.
                        allocated = raw_values[zpuid]
                    elif raw_sum > 0:
                        allocated = raw_values[zpuid] * total_work / raw_sum
                    else:
                        allocated = 0.0

                    key = (pid, zpuid)
                    if key not in agg:
                        agg[key] = {"allocated": 0.0, "project_name": pname}
                    agg[key]["allocated"] += allocated

    # Backfill missing emails in people.csv from what Zoho returned
    emails_added = []
    for zpuid, email in seen_email.items():
        row = people.get(zpuid)
        if row and not row["person_email"]:
            row["person_email"] = email
            emails_added.append(row["person_name"])
    # Always rewrite: also migrates an older people.csv that lacks person_email.
    write_people(people_rows)

    # Build CSV rows
    rows = []
    for (pid, zpuid), vals in agg.items():
        person = people.get(zpuid)
        rows.append({
            "project_id":      pid,
            "project_name":    vals["project_name"],
            "person_name":     person["person_name"] if person else f"UNKNOWN({zpuid})",
            "person_zpuid":    zpuid,
            "person_email":    (person and person["person_email"]) or seen_email.get(zpuid, ""),
            "allocated_hours": round(vals["allocated"], 2),
            "export_month":    target_month,
        })

    rows.sort(key=lambda r: (r["project_name"], r["person_name"]))

    # Source snapshot: the projects CSV this run built in tmp/. Filenames start
    # with a YYYY_MM_DD_HHMM timestamp, so name order is run order.
    snapshots = sorted(glob.glob(os.path.join(OUT_DIR, "*_projects.csv")))
    source_snapshot = os.path.basename(snapshots[-1]) if snapshots else ""

    # Write outputs
    os.makedirs(OUT_DIR, exist_ok=True)
    ts = datetime.now(IST).strftime("%Y_%m_%d_%H%M")

    csv_path  = os.path.join(OUT_DIR, f"{ts}_allocations.csv")

    fields = [
        "project_id", "project_name", "person_name", "person_zpuid",
        "person_email", "allocated_hours", "export_month",
    ]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    zero_alloc = sorted(set(
        r["project_name"] for r in rows if r["allocated_hours"] == 0.0
    ))
    unique_people = len(set(r["person_zpuid"] for r in rows))
    missing_email = sorted(set(r["person_name"] for r in rows if not r["person_email"]))

    # Summary
    print(f"\nRun complete — {target_month}")
    print(f"Source snapshot:          {source_snapshot}")
    print(f"Projects processed:       {projects_processed}")
    print(f"Unique people:            {unique_people}")
    print(f"Emails backfilled:        {len(emails_added)}")
    print(f"People missing email:     {len(missing_email)}"
          + (f" — {', '.join(missing_email)}" if missing_email else ""))
    print(f"Zero allocated hours:     {len(zero_alloc)}"
          + (f" — {', '.join(zero_alloc)}" if zero_alloc else ""))
    print(f"Fetch failed:             {len(fetch_failed)}"
          + (f" — {', '.join(fetch_failed)}" if fetch_failed else ""))
    print(csv_path)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate a weekly status report for any GitHub Project V2."""

import argparse
import csv
import subprocess
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------

def parse_project_url(url):
    """Return (owner_type, login, project_number) from a GitHub project URL."""
    m = re.match(r'https://github\.com/(orgs|users)/([^/]+)/projects/(\d+)', url)
    if m:
        return m.group(1), m.group(2), int(m.group(3))
    m = re.match(r'https://github\.com/([^/]+)/projects/(\d+)', url)
    if m:
        return 'orgs', m.group(1), int(m.group(2))
    raise ValueError(f"Cannot parse GitHub project URL: {url!r}")


# ---------------------------------------------------------------------------
# GraphQL
# ---------------------------------------------------------------------------

def build_items_query(owner_type, login, number):
    entity = 'organization' if owner_type == 'orgs' else 'user'
    return f"""
query($cursor: String) {{
  {entity}(login: "{login}") {{
    projectV2(number: {number}) {{
      items(first: 100, after: $cursor) {{
        pageInfo {{ hasNextPage endCursor }}
        nodes {{
          content {{
            ... on Issue {{
              number
              title
              state
              createdAt
              closedAt
              url
              repository {{ name }}
              assignees(first: 10) {{ nodes {{ login name }} }}
              labels(first: 20) {{ nodes {{ name }} }}
              milestone {{ title dueOn }}
            }}
          }}
          fieldValues(first: 30) {{
            nodes {{
              ... on ProjectV2ItemFieldSingleSelectValue {{
                name
                field {{ ... on ProjectV2SingleSelectField {{ name }} }}
              }}
              ... on ProjectV2ItemFieldDateValue {{
                date
                field {{ ... on ProjectV2Field {{ name }} }}
              }}
              ... on ProjectV2ItemFieldTextValue {{
                text
                field {{ ... on ProjectV2Field {{ name }} }}
              }}
              ... on ProjectV2ItemFieldNumberValue {{
                number
                field {{ ... on ProjectV2Field {{ name }} }}
              }}
              ... on ProjectV2ItemFieldIterationValue {{
                title
                startDate
                duration
                field {{ ... on ProjectV2IterationField {{ name }} }}
              }}
              ... on ProjectV2ItemFieldUserValue {{
                users(first: 5) {{ nodes {{ login name }} }}
                field {{ ... on ProjectV2Field {{ name }} }}
              }}
              ... on ProjectV2ItemFieldRepositoryValue {{
                repository {{ name nameWithOwner }}
                field {{ ... on ProjectV2Field {{ name }} }}
              }}
              ... on ProjectV2ItemFieldMilestoneValue {{
                milestone {{ title dueOn }}
                field {{ ... on ProjectV2Field {{ name }} }}
              }}
              ... on ProjectV2ItemFieldLabelValue {{
                labels(first: 10) {{ nodes {{ name }} }}
                field {{ ... on ProjectV2Field {{ name }} }}
              }}
              ... on ProjectV2ItemFieldPullRequestValue {{
                pullRequests(first: 5) {{ nodes {{ number title url }} }}
                field {{ ... on ProjectV2Field {{ name }} }}
              }}
            }}
          }}
        }}
      }}
    }}
  }}
}}
"""


def build_meta_query(owner_type, login, number):
    entity = 'organization' if owner_type == 'orgs' else 'user'
    return f"""
{{
  {entity}(login: "{login}") {{
    projectV2(number: {number}) {{
      title
      shortDescription
      statusUpdates(first: 1, orderBy: {{field: CREATED_AT, direction: DESC}}) {{
        nodes {{
          body
          createdAt
          status
        }}
      }}
    }}
  }}
}}
"""


def gh_graphql(query, **variables):
    cmd = ["gh", "api", "graphql", "-f", f"query={query}"]
    for k, v in variables.items():
        cmd += ["-f", f"{k}={v}"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def fetch_all_items(owner_type, login, number):
    query = build_items_query(owner_type, login, number)
    entity = 'organization' if owner_type == 'orgs' else 'user'
    items, cursor = [], None
    while True:
        kwargs = {"cursor": cursor} if cursor else {}
        data = gh_graphql(query, **kwargs)
        page = data["data"][entity]["projectV2"]["items"]
        items.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]
    return items


def fetch_project_meta(owner_type, login, number):
    query = build_meta_query(owner_type, login, number)
    entity = 'organization' if owner_type == 'orgs' else 'user'
    try:
        data = gh_graphql(query)
        proj = data["data"][entity]["projectV2"]
        title = proj.get("title", login)
        desc  = proj.get("shortDescription") or ""
        nodes = proj.get("statusUpdates", {}).get("nodes", [])
        return title, desc, (nodes[0] if nodes else None)
    except Exception:
        return login, "", None


# ---------------------------------------------------------------------------
# Data processing
# ---------------------------------------------------------------------------

PRIORITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
STATUS_ORDER   = {"In progress": 0, "To be Tested": 1, "Ready": 2, "Backlog": 3, "Done": 4}


def _extract_field_value(fv):
    """Return (field_name, value_str) from a fieldValue node, or (None, None)."""
    if not fv:
        return None, None
    fname = fv.get("field", {}).get("name", "")
    if not fname:
        return None, None
    if "name" in fv:
        return fname, fv["name"]
    if "date" in fv:
        return fname, fv["date"]
    if "text" in fv:
        return fname, fv["text"]
    if "number" in fv:
        val = fv["number"]
        return fname, str(int(val)) if val == int(val) else str(val)
    if "title" in fv and "startDate" in fv:
        # Iteration field
        return fname, fv["title"]
    if "users" in fv:
        users = fv["users"].get("nodes", [])
        return fname, ", ".join(u.get("name") or u.get("login", "") for u in users)
    if "repository" in fv and isinstance(fv.get("repository"), dict):
        return fname, fv["repository"].get("nameWithOwner") or fv["repository"].get("name", "")
    if "milestone" in fv and isinstance(fv.get("milestone"), dict):
        return fname, fv["milestone"].get("title", "")
    if "labels" in fv and isinstance(fv.get("labels"), dict):
        return fname, ", ".join(l["name"] for l in fv["labels"].get("nodes", []))
    if "pullRequests" in fv:
        prs = fv["pullRequests"].get("nodes", [])
        return fname, ", ".join(f"#{pr['number']}" for pr in prs)
    return fname, None


def parse_item(raw):
    content = raw.get("content") or {}
    if "number" not in content:
        return None

    all_fields = {}
    for fv in raw.get("fieldValues", {}).get("nodes", []):
        fname, value = _extract_field_value(fv)
        if fname and value is not None:
            all_fields[fname] = value

    status     = all_fields.get("Status")
    priority   = all_fields.get("Priority")
    start_date = all_fields.get("Start date") or all_fields.get("Start Date")
    target_date = all_fields.get("Target date") or all_fields.get("Target Date")
    item_type  = all_fields.get("Type")

    assignees = [
        a.get("name") or a.get("login", "")
        for a in content.get("assignees", {}).get("nodes", [])
    ]
    milestone = content.get("milestone") or {}

    return {
        "number":      content["number"],
        "title":       content["title"],
        "state":       content["state"],
        "status":      status,
        "priority":    priority,
        "start_date":  start_date,
        "target_date": target_date,
        "type":        item_type,
        "created_at":  content["createdAt"],
        "closed_at":   content.get("closedAt"),
        "url":         content["url"],
        "repo":        content.get("repository", {}).get("name", ""),
        "labels":      [l["name"] for l in content.get("labels", {}).get("nodes", [])],
        "assignees":   assignees,
        "milestone":   milestone.get("title", ""),
        "all_fields":  all_fields,
    }


def closed_this_week(item):
    if not item.get("closed_at"):
        return False
    closed = datetime.fromisoformat(item["closed_at"].replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - closed).days < 7


def priority_key(item):
    return (
        PRIORITY_ORDER.get(item.get("priority"), 9),
        STATUS_ORDER.get(item.get("status"), 9),
        item.get("created_at", ""),
    )


def fmt_date(iso):
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%-d %b %Y")
    except Exception:
        return iso


def fmt_date_dash(iso):
    """Return '—' for missing dates (used in HTML display)."""
    result = fmt_date(iso)
    return result if result else "—"


def majority_has_field(issues, field):
    """Return True if more than half of issues have a non-empty value for field."""
    if not issues:
        return False
    count = sum(1 for i in issues if i.get(field))
    return count > len(issues) / 2


def build_sections(items):
    closed_week  = sorted([i for i in items if closed_this_week(i)],
                          key=lambda x: x["closed_at"] or "", reverse=True)
    in_progress  = [i for i in items if i["status"] == "In progress"]
    to_be_tested = [i for i in items if i["status"] == "To be Tested"]
    active       = in_progress + to_be_tested
    next_tasks   = sorted([i for i in items if i["status"] == "Ready"], key=priority_key)
    return closed_week, active, next_tasks


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

# Fixed core fields always present in CSV (in order, no duplicates)
_CSV_CORE_FIELDS = [
    "number", "title", "url", "repo", "state", "status", "priority", "type",
    "labels", "assignees", "milestone", "start_date", "target_date",
    "created_at", "closed_at",
]

# Known project field names that map to core fields (skip them from extras)
_COVERED_PROJECT_FIELDS = {
    "Status", "Priority", "Type",
    "Start date", "Start Date", "Target date", "Target Date",
}


def _collect_extra_field_names(issues):
    """Return ordered list of project field names not already covered by core fields."""
    seen = set(_COVERED_PROJECT_FIELDS)
    extras = []
    for i in issues:
        for k in (i.get("all_fields") or {}):
            if k not in seen:
                seen.add(k)
                extras.append(k)
    return extras


def _build_csv_row(i, extra_fields):
    row = {
        "number":     i["number"],
        "title":      i["title"],
        "url":        i["url"],
        "repo":       i.get("repo", ""),
        "state":      i.get("state", ""),
        "status":     i.get("status") or "",
        "priority":   i.get("priority") or "",
        "type":       i.get("type") or "",
        "labels":     ", ".join(i.get("labels") or []),
        "assignees":  ", ".join(i.get("assignees") or []),
        "milestone":  i.get("milestone") or "",
        "start_date": fmt_date(i.get("start_date")),
        "target_date": fmt_date(i.get("target_date")),
        "created_at": fmt_date(i.get("created_at")),
        "closed_at":  fmt_date(i.get("closed_at")),
    }
    all_fields = i.get("all_fields") or {}
    for f in extra_fields:
        row[f] = all_fields.get(f, "")
    return row


def export_csv(closed_week, active, next_tasks, output_dir, date_str):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    sections = [
        (f"weekly-{date_str}-closed-this-week.csv", closed_week),
        (f"weekly-{date_str}-in-progress.csv",      active),
        (f"weekly-{date_str}-next-tasks.csv",        next_tasks),
    ]

    paths = []
    for filename, issues in sections:
        extra_fields = _collect_extra_field_names(issues)
        headers = _CSV_CORE_FIELDS + extra_fields
        path = output_dir / filename
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers, quoting=csv.QUOTE_NONNUMERIC)
            writer.writeheader()
            for i in issues:
                writer.writerow(_build_csv_row(i, extra_fields))
        paths.append(path)
        print(f"  → {path} ({len(issues)} rows)", flush=True)

    return paths


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------

STATUS_COLORS = {
    "In progress":  ("#E4022D", "#FCE5EA"),
    "To be Tested": ("#1F3CFF", "#E8EBFF"),
    "Done":         ("#0B7B3E", "#E6F4ED"),
    "Ready":        ("#5B6573", "#F0EFED"),
    "Backlog":      ("#5B6573", "#F0EFED"),
}

PROJECT_STATUS_DISPLAY = {
    "ON_TRACK":  ("On Track",  "#0B7B3E", "#E6F4ED"),
    "AT_RISK":   ("At Risk",   "#B84200", "#FEF0E7"),
    "OFF_TRACK": ("Off Track", "#E4022D", "#FCE5EA"),
    "COMPLETE":  ("Complete",  "#0B7B3E", "#E6F4ED"),
    "INACTIVE":  ("Inactive",  "#5B6573", "#F0EFED"),
}


def project_status_chip(status):
    key = status.upper().replace(" ", "_")
    label, fg, bg = PROJECT_STATUS_DISPLAY.get(key, (status, "#5B6573", "#F0EFED"))
    return f'<span class="chip" style="color:{fg};background:{bg}">{label}</span>'

LABEL_PALETTE = [
    ("#FCE5EA", "#8A021B"),
    ("#E8EBFF", "#1A2F99"),
    ("#FEF0E7", "#B84200"),
    ("#E6F4ED", "#0B5C30"),
    ("#EDE8F5", "#4A2280"),
    ("#FEF9E7", "#7A5500"),
    ("#E7F2F5", "#0A4A5C"),
    ("#F5E8EE", "#6B2B4E"),
    ("#EAEEE8", "#2E3E1A"),
    ("#F0F0F8", "#2B2B5C"),
]


def label_color(name):
    return LABEL_PALETTE[hash(name) % len(LABEL_PALETTE)]


def status_chip(status):
    if not status:
        return "—"
    fg, bg = STATUS_COLORS.get(status, ("#5B6573", "#F0EFED"))
    return f'<span class="chip" style="color:{fg};background:{bg}">{status}</span>'


def label_chip(name):
    bg, fg = label_color(name)
    return f'<span class="label-chip" style="background:{bg};color:{fg}">{name}</span>'


DATE_FIELD_LABELS = {
    "start_date":  "Start",
    "target_date": "Target",
    "created_at":  "Created",
    "closed_at":   "Closed",
}


def issue_rows(issues, project_url, show_status=True,
               date_field="created_at", date_field2=None, max_rows=10):
    col_count = 2 + int(show_status) + 1 + int(date_field2 is not None)
    if not issues:
        return f'<tr><td colspan="{col_count}" class="empty">None this period.</td></tr>'

    visible  = issues[:max_rows]
    overflow = len(issues) - max_rows
    rows = []

    for i in visible:
        labels    = "".join(label_chip(l) for l in i["labels"]) if i["labels"] else ""
        status_td = f"<td class='st'>{status_chip(i['status'])}</td>" if show_status else ""
        date1_val = fmt_date_dash(i.get(date_field))
        date1_td  = f"<td class='dt'>{date1_val}</td>"
        date2_td  = ""
        if date_field2:
            date2_val = fmt_date_dash(i.get(date_field2))
            date2_td  = f"<td class='dt'>{date2_val}</td>"
        rows.append(f"""
        <tr>
          <td class="num"><a href="{i['url']}">#{i['number']}</a></td>
          <td class="ttl">{i['title']}<div class="chips">{labels}</div></td>
          {status_td}
          {date1_td}
          {date2_td}
        </tr>""")

    if overflow > 0:
        rows.append(f"""
        <tr class="more-row">
          <td colspan="{col_count}">
            <a href="{project_url}">+{overflow} more — view all on GitHub →</a>
          </td>
        </tr>""")

    return "\n".join(rows)


def issue_table(issues, project_url, show_status=True,
                date_field="created_at", date_field2=None, max_rows=10):
    date1_label  = DATE_FIELD_LABELS.get(date_field, date_field.replace("_", " ").title())
    status_th    = "<th class='st'>Status</th>" if show_status else ""
    status_col   = "<col class='col-st'>"       if show_status else ""
    date1_th     = f"<th class='th-dt'>{date1_label}</th>"
    date1_col    = "<col class='col-dt'>"
    date2_th = date2_col = ""
    if date_field2:
        date2_label = DATE_FIELD_LABELS.get(date_field2, date_field2.replace("_", " ").title())
        date2_th  = f"<th class='th-dt'>{date2_label}</th>"
        date2_col = "<col class='col-dt'>"
    return f"""
    <table>
      <colgroup>
        <col class="col-num"><col class="col-ttl">{status_col}{date1_col}{date2_col}
      </colgroup>
      <thead>
        <tr>
          <th class="th-num">#</th>
          <th class="th-ttl">Task</th>
          {status_th}
          {date1_th}
          {date2_th}
        </tr>
      </thead>
      <tbody>
        {issue_rows(issues, project_url, show_status, date_field, date_field2, max_rows)}
      </tbody>
    </table>"""


# ---------------------------------------------------------------------------
# HTML/PDF generation
# ---------------------------------------------------------------------------

def generate_html(all_items, proj_title, proj_desc, status_update, project_url,
                  manual_status_label=None, manual_status_body=None,
                  extra_questions=None, notes=None):

    today = datetime.now()
    d = today.day
    if 11 <= d % 100 <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(d % 10, "th")
    today_str = f"{d}{suffix} {today.strftime('%B %Y')}"

    items = [p for p in (parse_item(r) for r in all_items) if p]

    closed_week, active, next_tasks = build_sections(items)
    next_10 = next_tasks[:10]

    # ── Date column decisions ──────────────────────────────────────────────
    # Closed This Week: col1 = start_date or created_at; col2 = target_date or closed_at
    closed_date1 = "start_date"  if majority_has_field(closed_week, "start_date")  else "created_at"
    closed_date2 = "target_date" if majority_has_field(closed_week, "target_date") else "closed_at"

    # In Progress / To Be Tested and Next 10: col1 = target_date or created_at
    active_date1    = "target_date" if majority_has_field(active,    "target_date") else "created_at"
    next_date1      = "target_date" if majority_has_field(next_tasks, "target_date") else "created_at"

    # ── Overview description: status chip + body ──────────────────────────
    desc_parts = []
    if status_update:
        su_status = status_update.get("status", "")
        su_body   = status_update.get("body", "")
        if su_status:
            desc_parts.append(project_status_chip(su_status))
        if su_body:
            desc_parts.append(f'<p class="su-body">{su_body.replace(chr(10), "<br>")}</p>')
    elif manual_status_label or manual_status_body:
        if manual_status_label:
            desc_parts.append(project_status_chip(manual_status_label))
        if manual_status_body:
            desc_parts.append(f'<p class="su-body">{manual_status_body.replace(chr(10), "<br>")}</p>')

    desc_html = f'<div class="proj-desc">{"".join(desc_parts)}</div>' if desc_parts else ""

    overview_html = f"""
    <div class="overview-block">
      <div class="proj-name">{proj_title}</div>
      {desc_html}
    </div>
    <div class="three-col-stats">
      <div class="stat-card">
        <div class="s-n">{len(closed_week)}</div>
        <div class="s-l">Closed this week</div>
      </div>
      <div class="stat-card">
        <div class="s-n">{len(active)}</div>
        <div class="s-l">In progress</div>
      </div>
      <div class="stat-card">
        <div class="s-n">{len(next_tasks)}</div>
        <div class="s-l">Next tasks</div>
      </div>
    </div>"""

    if extra_questions:
        lines    = [l.strip() for l in extra_questions.strip().splitlines() if l.strip()]
        items_li = "".join(f"<li>{l}</li>" for l in lines)
        questions_section = f"""
        <div class="section-block">
          <div class="section-header">
            <h2 class="section-title">Open Questions &amp; Client Actions</h2>
          </div>
          <div class="section">
            <div class="extra-block">
              <ul class="extra-list">{items_li}</ul>
            </div>
          </div>
        </div>"""
    else:
        questions_section = ""

    if notes and notes.strip():
        notes_section = f"""
        <div class="section-block">
          <div class="section-header">
            <h2 class="section-title">Notes</h2>
          </div>
          <div class="notes-area">{notes.strip().replace(chr(10), "<br>")}</div>
        </div>"""
    else:
        notes_section = ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{proj_title} Weekly Status — {today_str}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,300;0,6..72,400;0,6..72,500;1,6..72,300;1,6..72,400&family=DM+Sans:wght@400;500&display=swap" rel="stylesheet">
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

@page {{
  size: A4;
  margin: 16mm 22mm 16mm 22mm;
}}

:root {{
  --ink:      #0B0F14;
  --ink-2:    #1A2230;
  --ink-3:    #2B3544;
  --paper:    #FFFFFF;
  --paper-2:  #F6F4F0;
  --paper-3:  #EDEAE3;
  --red:      #E4022D;
  --red-soft: #FCE5EA;
  --rule:     #D6D1C8;
  --muted:    #5B6573;
  --serif:    'Newsreader', Georgia, serif;
  --sans:     'DM Sans', system-ui, sans-serif;
  --radius:   3px;
}}

html, body {{
  background: var(--paper);
  color: var(--ink);
  font-family: var(--sans);
  font-size: 9.5pt;
  line-height: 1.55;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}}

a {{ color: var(--ink-2); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}

.overview-block {{
  margin-bottom: 20px;
  padding: 16px 20px;
  background: var(--paper-2);
  border-left: 3px solid var(--red);
  border-radius: 0 var(--radius) var(--radius) 0;
}}

.proj-name {{
  font-family: var(--serif);
  font-size: 15pt;
  font-weight: 400;
  color: var(--ink);
  margin-bottom: 4px;
}}

.proj-desc {{
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}}

.su-body {{ font-size: 9.5pt; color: var(--ink-2); line-height: 1.6; margin: 0; }}

.section-block {{
  margin-top: 28px;
  page-break-inside: avoid;
}}

.section-block:first-of-type {{ margin-top: 4px; }}

.section {{
  margin-bottom: 4px;
}}

.section-header {{
  margin-bottom: 10px;
}}

.section-title {{
  font-family: var(--serif);
  font-size: 14pt;
  font-weight: 400;
  letter-spacing: -0.01em;
  color: var(--ink);
  line-height: 1.2;
}}

.three-col-stats {{
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 10px;
  margin-bottom: 0;
}}

.stat-card {{
  background: var(--paper-2);
  border-radius: var(--radius);
  padding: 10px 14px;
  border-top: 2px solid var(--rule);
}}

.stat-card.accent {{ border-top-color: var(--red); }}

.stat-card .s-n {{
  font-family: var(--serif);
  font-size: 20pt;
  font-weight: 300;
  color: var(--ink);
  line-height: 1;
}}

.stat-card .s-l {{
  font-size: 7.5pt;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-top: 3px;
}}

table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 8.5pt;
  table-layout: fixed;
}}

col.col-num {{ width: 44px; }}
col.col-ttl {{ width: auto; }}
col.col-st  {{ width: 100px; }}
col.col-dt  {{ width: 72px; }}

thead tr {{
  border-bottom: 1.5px solid var(--ink);
}}

thead th {{
  font-family: var(--sans);
  font-size: 7pt;
  font-weight: 500;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--muted);
  padding: 4px 8px 6px;
  text-align: left;
}}

tbody tr {{
  border-bottom: 1px solid var(--rule);
}}

tbody tr:last-child {{ border-bottom: none; }}

tbody td {{
  padding: 6px 8px;
  vertical-align: top;
  color: var(--ink-2);
}}

tbody tr:nth-child(even) {{ background: var(--paper-2); }}

td.num {{
  font-size: 8pt;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
}}

td.num a {{
  font-weight: 500;
  color: var(--red-ink, #8A021B);
}}

td.ttl {{
  font-size: 8.5pt;
  color: var(--ink);
  overflow-wrap: break-word;
}}

td.st {{
  vertical-align: middle;
}}

td.dt {{
  font-size: 7.5pt;
  color: var(--muted);
  white-space: nowrap;
}}

td.empty {{
  color: var(--muted);
  font-style: italic;
  padding: 10px 8px;
}}

tr.more-row td {{
  padding: 6px 8px;
  font-size: 8pt;
  color: var(--muted);
  border-top: 1px dashed var(--rule);
}}

tr.more-row a {{
  color: var(--red);
  font-weight: 500;
}}

.chip {{
  display: inline-block;
  font-size: 7pt;
  font-weight: 500;
  padding: 2px 7px;
  border-radius: 10px;
  line-height: 1.4;
  white-space: nowrap;
}}

.label-chip {{
  display: inline-block;
  font-size: 6.5pt;
  font-weight: 500;
  padding: 1px 5px;
  border-radius: 3px;
  margin-right: 3px;
  margin-top: 3px;
}}

.chips {{ margin-top: 3px; }}

.extra-block {{
  margin-top: 12px;
  background: var(--paper-2);
  border-left: 3px solid var(--ink-3);
  padding: 10px 14px;
  border-radius: 0 var(--radius) var(--radius) 0;
}}

.extra-label {{
  font-size: 7pt;
  font-weight: 500;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 6px;
}}

.extra-list {{
  padding-left: 14px;
  font-size: 9pt;
  color: var(--ink-2);
  line-height: 1.7;
}}

.notes-area {{
  border: 1px solid var(--rule);
  border-radius: var(--radius);
  padding: 12px 16px;
  color: var(--ink-2);
  font-size: 9pt;
  line-height: 1.6;
}}

.muted {{ color: var(--muted); font-style: italic; }}

@media screen {{
  body {{
    max-width: 860px;
    margin: 32px auto;
    padding: 0 32px 48px;
  }}
}}
</style>
</head>
<body>

  <div class="section-header" style="margin-top:0">
    <h2 class="section-title">{today_str} — Overview</h2>
  </div>
  {overview_html}

  {questions_section}

  <div class="section-block">
    <div class="section-header">
      <h2 class="section-title">Closed This Week</h2>
    </div>
    <div class="section">
      {issue_table(closed_week, project_url, show_status=False,
                   date_field=closed_date1, date_field2=closed_date2)}
    </div>
  </div>

  <div class="section-block">
    <div class="section-header">
      <h2 class="section-title">In Progress &amp; To Be Tested</h2>
    </div>
    <div class="section">
      {issue_table(active, project_url, date_field=active_date1)}
    </div>
  </div>

  <div class="section-block">
    <div class="section-header">
      <h2 class="section-title">Next 10 Tasks</h2>
    </div>
    <div class="section">
      {issue_table(next_10, project_url, date_field=next_date1)}
    </div>
  </div>

  {notes_section}

</body>
</html>"""


# ---------------------------------------------------------------------------
# PDF export
# ---------------------------------------------------------------------------

def export_pdf(html_content, out_path):
    html_path = out_path.with_suffix(".html")
    html_path.write_text(html_content, encoding="utf-8")

    chrome = next((c for c in [
        "google-chrome", "google-chrome-stable", "chromium-browser", "chromium",
    ] if subprocess.run(["which", c], capture_output=True).returncode == 0), None)

    if not chrome:
        print(f"[WARN] No Chrome found. HTML saved to: {html_path}", file=sys.stderr)
        return html_path

    result = subprocess.run([
        chrome,
        "--headless=new", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
        f"--print-to-pdf={out_path}",
        "--print-to-pdf-no-header",
        "--no-pdf-header-footer",
        str(html_path),
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"[WARN] Chrome error: {result.stderr}", file=sys.stderr)
        return html_path

    html_path.unlink(missing_ok=True)
    return out_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate a weekly status report for a GitHub Project V2")
    parser.add_argument("--project-url",  required=True, metavar="URL",
                        help="GitHub project URL, e.g. https://github.com/orgs/myorg/projects/1")
    parser.add_argument("--format",       choices=["pdf", "html", "csv"], default="pdf",
                        help="Output format (default: pdf)")
    parser.add_argument("--output-dir",   metavar="DIR",
                        help="Directory to write output files (default: ./reports)")
    parser.add_argument("--questions",    metavar="TEXT",
                        help="Open questions for the client (one per line; PDF/HTML only)")
    parser.add_argument("--notes",        metavar="TEXT",
                        help="Notes section content (PDF/HTML only)")
    parser.add_argument("--status",       metavar="LABEL",
                        help="Project status label (e.g. ON_TRACK, AT_RISK); overrides GitHub status")
    parser.add_argument("--status-body",  metavar="TEXT",
                        help="Project status body text; overrides GitHub status body")
    parser.add_argument("--check-status", action="store_true",
                        help="Check if a GitHub project status exists, then exit")
    args = parser.parse_args()

    owner_type, login, number = parse_project_url(args.project_url)

    if args.check_status:
        _, _, su = fetch_project_meta(owner_type, login, number)
        if su and su.get("status"):
            print("STATUS_FOUND")
        else:
            print("STATUS_NOT_FOUND")
        return

    output_dir = Path(args.output_dir) if args.output_dir else Path.cwd() / "reports"
    date_str   = datetime.now().strftime("%Y-%m-%d")

    print("Fetching project metadata…", flush=True)
    proj_title, proj_desc, status_update = fetch_project_meta(owner_type, login, number)
    print(f"  → Project: {proj_title}", flush=True)

    print("Fetching project items…", flush=True)
    raw_items = fetch_all_items(owner_type, login, number)
    print(f"  → {len(raw_items)} items fetched", flush=True)

    items = [p for p in (parse_item(r) for r in raw_items) if p]
    closed_week, active, next_tasks = build_sections(items)

    print("Generating report…", flush=True)

    if args.format == "csv":
        paths = export_csv(closed_week, active, next_tasks, output_dir, date_str)
        print(f"\n✓ {len(paths)} CSV files saved to: {output_dir}", flush=True)

    else:
        html = generate_html(
            raw_items, proj_title, proj_desc, status_update, args.project_url,
            manual_status_label=args.status,
            manual_status_body=args.status_body,
            extra_questions=args.questions,
            notes=args.notes,
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r'[^a-z0-9]+', '-', proj_title.lower()).strip('-')
        out_path = output_dir / f"{slug}-weekly-{date_str}.{'pdf' if args.format == 'pdf' else 'html'}"

        if args.format == "html":
            out_path.write_text(html, encoding="utf-8")
            print(f"\n✓ Report saved to: {out_path}", flush=True)
        else:
            final = export_pdf(html, out_path)
            print(f"\n✓ Report saved to: {final}", flush=True)


if __name__ == "__main__":
    main()

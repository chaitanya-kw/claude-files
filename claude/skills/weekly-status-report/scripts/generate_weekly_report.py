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
          updatedAt
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
              issueFieldValues(first: 30) {{
                nodes {{
                  __typename
                  ... on IssueFieldSingleSelectValue {{
                    value
                    field {{ ... on IssueFieldSingleSelect {{ name }} }}
                  }}
                  ... on IssueFieldDateValue {{
                    value
                    field {{ ... on IssueFieldDate {{ name }} }}
                  }}
                  ... on IssueFieldTextValue {{
                    value
                    field {{ ... on IssueFieldText {{ name }} }}
                  }}
                  ... on IssueFieldNumberValue {{
                    value
                    field {{ ... on IssueFieldNumber {{ name }} }}
                  }}
                  ... on IssueFieldMultiSelectValue {{
                    value
                    options {{ ... on IssueFieldSingleSelectOption {{ name }} }}
                    field {{ ... on IssueFieldMultiSelect {{ name }} }}
                  }}
                }}
              }}
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


def build_status_field_query(owner_type, login, number):
    entity = 'organization' if owner_type == 'orgs' else 'user'
    return f"""
{{
  {entity}(login: "{login}") {{
    projectV2(number: {number}) {{
      field(name: "Status") {{
        ... on ProjectV2SingleSelectField {{
          options {{ name }}
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


def fetch_status_options(owner_type, login, number):
    """Return the ordered list of option names for the project's 'Status' field."""
    query = build_status_field_query(owner_type, login, number)
    entity = 'organization' if owner_type == 'orgs' else 'user'
    data = gh_graphql(query)
    field = data["data"][entity]["projectV2"].get("field") or {}
    return [o["name"] for o in field.get("options", [])]


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

PRIORITY_ORDER = {"Critical": 0, "Urgent": 1, "High": 2, "Medium": 3, "Low": 4}


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


def _extract_issue_field_value(fv):
    """Return (field_name, value_str) from an issue-level custom field node (IssueFieldValue union)."""
    if not fv:
        return None, None
    fname = (fv.get("field") or {}).get("name", "")
    if not fname:
        return None, None
    value = fv.get("value")
    if value is not None:
        return fname, str(value)
    options = fv.get("options")
    if options is not None:
        names = [o.get("name", "") for o in options if o]
        return fname, ", ".join(n for n in names if n)
    return fname, None


def parse_item(raw):
    content = raw.get("content") or {}
    if "number" not in content:
        return None

    # Project-level fields (from the ProjectV2Item), e.g. Status, Size, Assignees.
    project_fields = {}
    for fv in raw.get("fieldValues", {}).get("nodes", []):
        fname, value = _extract_field_value(fv)
        if fname and value is not None:
            project_fields[fname] = value

    # Issue-level custom fields (from the Issue itself), e.g. Priority, Start date,
    # Target date, Effort. These live outside ProjectV2 entirely, so they must be
    # fetched and merged separately. Where a name exists at both levels, the
    # issue-level value wins since it's the one users actually set in practice.
    issue_fields = {}
    for fv in content.get("issueFieldValues", {}).get("nodes", []):
        fname, value = _extract_issue_field_value(fv)
        if fname and value is not None:
            issue_fields[fname] = value

    all_fields = {**project_fields, **issue_fields}

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
        "updated_at":  raw.get("updatedAt"),
        "url":         content["url"],
        "repo":        content.get("repository", {}).get("name", ""),
        "labels":      [l["name"] for l in content.get("labels", {}).get("nodes", [])],
        "assignees":   assignees,
        "milestone":   milestone.get("title", ""),
        "all_fields":  all_fields,
    }


def _recently_touched(item, days=7):
    """True if the item's status was set/changed within the last `days` days.

    Uses the project item's updatedAt as a proxy for "when the status last
    changed" (falling back to closedAt), since GitHub doesn't expose a
    per-field-change timestamp for Status.
    """
    ts = item.get("updated_at") or item.get("closed_at")
    if not ts:
        return False
    changed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - changed).days < days


def priority_key(item):
    return (
        PRIORITY_ORDER.get(item.get("priority"), 9),
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


def build_sections(items, closed_statuses, progress_statuses, next_statuses):
    """Split items into the three report sections using user-configured status groups.

    No status name is hardcoded here — `closed_statuses`, `progress_statuses`, and
    `next_statuses` are sets of Status option names supplied by the caller (collected
    from the user by the skill, based on the project's actual Status field options).

    All three sections sort by priority_key: highest priority first, then oldest
    (earliest created_at) first as the secondary tiebreaker.
    """
    closed_week = sorted(
        [i for i in items if i.get("status") in closed_statuses and _recently_touched(i)],
        key=priority_key,
    )
    active     = sorted([i for i in items if i.get("status") in progress_statuses], key=priority_key)
    next_tasks = sorted([i for i in items if i.get("status") in next_statuses], key=priority_key)
    return closed_week, active, next_tasks


# ---------------------------------------------------------------------------
# Markdown helpers (GitHub status update bodies are markdown)
# ---------------------------------------------------------------------------

def _inline_markdown_to_html(text):
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', text)
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    return text


def markdown_to_html(text):
    """Render a small, common subset of markdown (headers, bullet/numbered lists,
    bold/italic/code, paragraphs) to HTML. Status update bodies come from GitHub
    as markdown, so this is needed for them to display as more than raw text."""
    if not text:
        return ""

    lines = text.replace("\r\n", "\n").split("\n")
    html_parts = []
    list_buffer = []
    list_tag = None

    def flush_list():
        nonlocal list_buffer, list_tag
        if list_buffer:
            items = "".join(f"<li>{item}</li>" for item in list_buffer)
            html_parts.append(f"<{list_tag}>{items}</{list_tag}>")
            list_buffer = []
            list_tag = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            flush_list()
            continue

        header_match = re.match(r'^(#{1,6})\s+(.*)$', line)
        bullet_match = re.match(r'^[-*]\s+(.*)$', line)
        numbered_match = re.match(r'^\d+\.\s+(.*)$', line)

        if header_match:
            flush_list()
            level = len(header_match.group(1))
            html_parts.append(f"<h{level}>{_inline_markdown_to_html(header_match.group(2))}</h{level}>")
        elif bullet_match:
            if list_tag != "ul":
                flush_list()
                list_tag = "ul"
            list_buffer.append(_inline_markdown_to_html(bullet_match.group(1)))
        elif numbered_match:
            if list_tag != "ol":
                flush_list()
                list_tag = "ol"
            list_buffer.append(_inline_markdown_to_html(numbered_match.group(1)))
        else:
            flush_list()
            html_parts.append(f"<p>{_inline_markdown_to_html(line)}</p>")

    flush_list()
    return "\n".join(html_parts)


def strip_markdown(text):
    """Return plain text with common markdown syntax removed (for CSV export)."""
    if not text:
        return ""
    lines = text.replace("\r\n", "\n").split("\n")
    out = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r'^#{1,6}\s+', '', line)
        line = re.sub(r'^[-*]\s+', '', line)
        line = re.sub(r'^\d+\.\s+', '', line)
        line = re.sub(r'\*\*(.+?)\*\*', r'\1', line)
        line = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1', line)
        line = re.sub(r'`(.+?)`', r'\1', line)
        out.append(line)
    return " ".join(out)


def status_label_display(status):
    """Convert a status code like 'ON_TRACK' to a display label like 'On Track'."""
    if not status:
        return ""
    key = status.upper().replace(" ", "_")
    display = PROJECT_STATUS_DISPLAY.get(key)
    if display:
        return display[0]
    return status.replace("_", " ").title()


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


def export_status_csv(status_update, output_dir, date_str):
    """Write a single-row status.csv: Status, Summary, Date. Header-only if no
    status update exists on GitHub."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"weekly-{date_str}-status.csv"

    headers = ["Status", "Summary", "Date"]
    row = None
    if status_update:
        row = {
            "Status":  status_label_display(status_update.get("status", "")),
            "Summary": strip_markdown(status_update.get("body", "")),
            "Date":    fmt_date(status_update.get("createdAt")),
        }

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers, quoting=csv.QUOTE_NONNUMERIC)
        writer.writeheader()
        if row:
            writer.writerow(row)

    print(f"  → {path} ({1 if row else 0} rows)", flush=True)
    return path


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------

# Statuses are user-configured, not hardcoded — GitHub's project status enum
# (ON_TRACK/AT_RISK/...) is the one fixed vocabulary worth color-coding, since it
# always means the same thing regardless of the project.
PROJECT_STATUS_DISPLAY = {
    "ON_TRACK":  ("On Track",  "#0B0F14"),
    "AT_RISK":   ("At Risk",   "#E4022D"),
    "OFF_TRACK": ("Off Track", "#E4022D"),
    "COMPLETE":  ("Complete",  "#0B0F14"),
    "INACTIVE":  ("Inactive",  "#5B6573"),
}


def project_status_chip(status):
    key = status.upper().replace(" ", "_")
    label, fg = PROJECT_STATUS_DISPLAY.get(key, (status, "#5B6573"))
    # Box shape (border/padding/display) is inlined, not left to the .status-pill
    # class, so the pill still renders correctly if the <style> block is dropped
    # entirely (e.g. Gmail strips it from sent mail).
    style = (
        "display:inline-block;font-size:11px;font-weight:600;letter-spacing:0.06em;"
        f"text-transform:uppercase;padding:3px 10px;border:1px solid {fg};border-radius:2px;color:{fg};"
    )
    return f'<span class="status-pill" style="{style}">{label}</span>'

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
    return f'<span class="status-badge">{status}</span>'


PRIORITY_COLORS = {
    "Critical": "#E4022D",
    "Urgent":   "#E4022D",
    "High":     "#B84200",
    "Medium":   "#5B6573",
    "Low":      "#5B6573",
}


def priority_chip(priority):
    if not priority:
        return "—"
    color = PRIORITY_COLORS.get(priority, "#5B6573")
    return f'<span class="priority-badge" style="color:{color};border-color:{color}">{priority}</span>'


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
    col_count = 2 + 1 + int(show_status) + 1 + int(date_field2 is not None)
    if not issues:
        return f'<tr><td colspan="{col_count}" class="empty">None this period.</td></tr>'

    visible  = issues[:max_rows]
    overflow = len(issues) - max_rows
    rows = []

    for i in visible:
        labels    = "".join(label_chip(l) for l in i["labels"]) if i["labels"] else ""
        priority_td = f"<td class='pr'>{priority_chip(i.get('priority'))}</td>"
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
          {priority_td}
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
    <div class="table-scroll">
    <table>
      <colgroup>
        <col class="col-num"><col class="col-ttl"><col class="col-pr">{status_col}{date1_col}{date2_col}
      </colgroup>
      <thead>
        <tr>
          <th class="th-num">#</th>
          <th class="th-ttl">Task</th>
          <th class="st">Priority</th>
          {status_th}
          {date1_th}
          {date2_th}
        </tr>
      </thead>
      <tbody>
        {issue_rows(issues, project_url, show_status, date_field, date_field2, max_rows)}
      </tbody>
    </table>
    </div>"""


# ---------------------------------------------------------------------------
# HTML/PDF generation
# ---------------------------------------------------------------------------

def generate_html(all_items, proj_title, proj_desc, status_update, project_url,
                  closed_statuses, progress_statuses, next_statuses,
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

    closed_week, active, next_tasks = build_sections(items, closed_statuses, progress_statuses, next_statuses)
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
            desc_parts.append(f'<div class="su-body">{markdown_to_html(su_body)}</div>')
    elif manual_status_label or manual_status_body:
        if manual_status_label:
            desc_parts.append(project_status_chip(manual_status_label))
        if manual_status_body:
            desc_parts.append(f'<div class="su-body">{markdown_to_html(manual_status_body)}</div>')

    desc_html = f'<div class="proj-desc">{"".join(desc_parts)}</div>' if desc_parts else ""

    # A <table>, not a div grid — with inline cell styles as a fallback for
    # when the <style> block itself is stripped (e.g. Gmail on sent mail),
    # so the three counts stay side-by-side instead of stacking.
    def stat_cell(n, label, border_right):
        border = "border-right:1px solid #E2DED6;" if border_right else ""
        return f"""
      <td class="stat-card" style="width:33.33%;vertical-align:top;background:#FFFFFF;padding:14px 16px;{border}">
        <div class="s-n" style="font-family:Georgia,'Times New Roman',serif;font-style:italic;font-size:26px;color:#0B0F14;line-height:1;">{n}</div>
        <div class="s-l" style="font-size:10px;color:#5B6573;text-transform:uppercase;letter-spacing:0.08em;margin-top:4px;">{label}</div>
      </td>"""

    overview_content = f"""
    {desc_html}
    <table class="three-col-stats" role="presentation" cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse;border:1px solid #E2DED6;">
      <tr>
        {stat_cell(len(closed_week), "Closed this week", True)}
        {stat_cell(len(active), "In progress", True)}
        {stat_cell(len(next_tasks), "Next tasks", False)}
      </tr>
    </table>"""

    questions_content = None
    if extra_questions:
        lines    = [l.strip() for l in extra_questions.strip().splitlines() if l.strip()]
        items_li = "".join(f"<li>{l}</li>" for l in lines)
        questions_content = f'<ul class="extra-list">{items_li}</ul>'

    notes_content = None
    if notes and notes.strip():
        notes_content = f'<div class="notes-area">{notes.strip().replace(chr(10), "<br>")}</div>'

    closed_table = issue_table(closed_week, project_url, show_status=False,
                                date_field=closed_date1, date_field2=closed_date2)
    active_table = issue_table(active, project_url, date_field=active_date1)
    next_table   = issue_table(next_10, project_url, date_field=next_date1)

    # ── Numbered sections, in order; empty/optional ones are skipped ───────
    sections = [
        ("Status", overview_content),
        ("Open Questions & Client Actions", questions_content),
        ("Closed This Week", closed_table),
        ("In Progress & To Be Tested", active_table),
        ("Next 10 Tasks", next_table),
        ("Notes", notes_content),
    ]

    section_html = ""
    n = 0
    for title, content in sections:
        if not content:
            continue
        n += 1
        section_html += f"""
    <div class="section-block">
      <div class="section-header">
        <p class="sec-label">{n:02d}&nbsp;&nbsp;{title.upper()}</p>
      </div>
      <div class="section-body">
        {content}
      </div>
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{proj_title} — Weekly Status — {today_str}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

:root {{
  --ink:     #0B0F14;
  --muted:   #5B6573;
  --red:     #E4022D;
  --paper:   #F0EDE8;
  --card:    #FFFFFF;
  --rule:    #E2DED6;
  --rule-2:  #F0EDE8;
  --sans:    'DM Sans', Arial, sans-serif;
  --mono:    'Courier New', Courier, monospace;
  --serif:   Georgia, 'Times New Roman', serif;
}}

/* Real page margins (not div padding) so every printed page — not just the
   first — gets consistent top/bottom space; div padding only applies once,
   at the very start/end of the flowed content. */
@page {{ size: A4; margin: 18mm 16mm; }}

html, body {{
  background: var(--paper);
  color: var(--ink);
  font-family: var(--sans);
  line-height: 1.55;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}}

a {{ color: var(--ink); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}

.wrap {{ padding: 32px 16px 48px; }}
.card {{ max-width: 820px; width: 100%; margin: 0 auto; background: var(--card); padding: 40px; }}

.wordmark {{
  font-size: 13px; font-weight: 700; letter-spacing: 0.14em;
  text-transform: uppercase; color: var(--ink);
}}
.wordmark-rule {{ margin-top: 6px; padding-top: 22px; border-bottom: 2px solid var(--red); }}

.eyebrow {{
  margin-top: 24px;
  font-size: 11px; font-weight: 600; letter-spacing: 0.16em;
  text-transform: uppercase; color: var(--muted);
}}

.proj-name {{
  margin-top: 4px; margin-bottom: 32px;
  font-family: var(--serif); font-size: 32px; font-style: italic; font-weight: 400;
  color: var(--ink); line-height: 1.2;
}}

.sec-label {{
  font-family: var(--mono); font-size: 10px; font-weight: 700;
  letter-spacing: 0.18em; text-transform: uppercase; color: var(--muted);
}}

.section-block {{ margin-bottom: 32px; }}
.section-header {{ margin-bottom: 20px; }}
.section-body {{ font-size: 13px; line-height: 1.6; color: var(--ink); }}

/* Plain block flow, not flexbox — this survives having its <style> block
   stripped (e.g. Gmail strips <style> from sent mail), whereas flex/grid
   silently collapse to something worse than a simple top-to-bottom stack. */
.proj-desc {{ margin-bottom: 20px; }}

.status-pill {{
  display: inline-block;
  font-size: 11px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase;
  padding: 3px 10px; border: 1px solid; border-radius: 2px;
}}

.su-body p {{ margin: 4px 0; }}
.su-body h1, .su-body h2, .su-body h3, .su-body h4, .su-body h5, .su-body h6 {{
  font-size: 13px; font-weight: 700; color: var(--ink); margin: 8px 0 2px;
}}
.su-body ul, .su-body ol {{ margin: 4px 0; padding-left: 18px; }}
.su-body li {{ margin: 3px 0; }}
.su-body code {{
  font-family: var(--mono); font-size: 12px; background: var(--rule-2);
  padding: 1px 4px; border-radius: 2px;
}}

/* A <table>, not CSS grid — grid collapses (stats stack vertically instead
   of three across) once Gmail strips the <style> block from sent mail. */
.three-col-stats {{ width: 100%; border-collapse: collapse; border: 1px solid var(--rule); }}
.stat-card {{ background: var(--card); padding: 14px 16px; width: 33.33%; vertical-align: top; border-right: 1px solid var(--rule); }}
.stat-card:last-child {{ border-right: none; }}
.stat-card .s-n {{ font-family: var(--serif); font-style: italic; font-size: 26px; color: var(--ink); line-height: 1; }}
.stat-card .s-l {{ font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; margin-top: 4px; }}

.table-scroll {{ overflow-x: auto; -webkit-overflow-scrolling: touch; }}

/* min-width matches the widest issue table (5 columns, incl. Status) so every
   table shares one floor — narrower ones (e.g. Closed This Week, no Status
   column) just get a roomier title column instead of a different breakpoint.
   Below that width the .table-scroll wrapper scrolls instead of the table
   squishing its columns unreadably thin. */
table {{ width: 100%; min-width: 640px; border-collapse: collapse; table-layout: fixed; }}

col.col-num {{ width: 60px; }}
col.col-ttl {{ width: auto; }}
col.col-pr  {{ width: 90px; }}
col.col-st  {{ width: 120px; }}
col.col-dt  {{ width: 84px; }}

thead tr {{ border-bottom: 2px solid var(--ink); }}
thead th {{
  font-family: var(--sans); font-size: 11px; font-weight: 600; letter-spacing: 0.06em;
  text-transform: uppercase; color: var(--ink); padding: 0 8px 8px 0; text-align: left;
}}

tbody tr {{ border-bottom: 1px solid var(--rule); }}
tbody tr:last-child {{ border-bottom: none; }}
tbody td {{ padding: 10px 8px 10px 0; vertical-align: top; font-size: 13px; color: var(--ink); }}

td.num {{ font-family: var(--mono); font-size: 12px; font-weight: 600; color: var(--muted); white-space: nowrap; }}
td.num a {{ color: var(--muted); }}
td.ttl {{ overflow-wrap: break-word; line-height: 1.5; }}
td.st  {{ vertical-align: middle; }}
td.dt  {{ font-size: 12px; color: var(--muted); white-space: nowrap; }}

td.empty {{ color: var(--muted); font-style: italic; padding: 10px 0; }}

tr.more-row td {{ padding: 10px 0; font-size: 12px; color: var(--muted); border-top: 1px dashed var(--rule); }}
tr.more-row a {{ color: var(--red); font-weight: 600; }}

.status-badge {{
  display: inline-block; font-size: 11px; font-weight: 600; color: var(--ink);
  background: var(--rule-2); border-radius: 2px; padding: 2px 8px; letter-spacing: 0.04em;
  white-space: nowrap;
}}

.priority-badge {{
  display: inline-block; font-size: 11px; font-weight: 600; letter-spacing: 0.04em;
  padding: 2px 8px; border: 1px solid; border-radius: 2px; white-space: nowrap;
}}

.label-chip {{
  display: inline-block; font-size: 10px; font-weight: 500; padding: 1px 6px;
  border-radius: 2px; margin-right: 4px; margin-top: 4px; background: var(--rule-2); color: var(--muted);
}}

.chips {{ margin-top: 4px; }}

.extra-list {{ padding-left: 18px; font-size: 13px; color: var(--ink); line-height: 1.7; }}

.notes-area {{
  border: 1px solid var(--rule); border-radius: 2px; padding: 14px 16px;
  color: var(--ink); font-size: 13px; line-height: 1.6;
}}

.footer {{ border-top: 1px solid var(--ink); padding-top: 16px; margin-top: 8px; }}
.footer-left  {{ font-size: 12px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink); }}
.footer-right {{ font-size: 12px; color: var(--muted); text-align: right; }}

/* Must come last: at equal specificity the later rule wins, and print needs to
   override the screen .wrap/.card padding above with the @page margin instead. */
@media print {{
  html, body {{ background: var(--card); }}
  thead {{ display: table-header-group; }}
  tr {{ break-inside: avoid; }}
  .section-block {{ page-break-inside: avoid; }}
  .wrap {{ padding: 0; }}
  .card {{ padding: 0; }}
}}
</style>
</head>
<body>
<div class="wrap">
  <div class="card">

    <div>
      <div class="wordmark">KILOWOTT</div>
      <div class="wordmark-rule"></div>
    </div>

    <p class="eyebrow">WEEKLY STATUS &middot; {today_str.upper()}</p>
    <h1 class="proj-name">{proj_title}</h1>

    {section_html}

    <div class="footer">
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td class="footer-left">{proj_title}</td>
          <td align="right" class="footer-right">{today_str} &nbsp;&middot;&nbsp; Generated by Kilowott</td>
        </tr>
      </table>
    </div>

  </div>
</div>
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
    parser.add_argument("--list-statuses", action="store_true",
                        help="Print the project's Status field options (one per line), then exit")
    parser.add_argument("--closed-statuses",   metavar="LIST",
                        help="Comma-separated Status option names for the 'Closed This Week' section")
    parser.add_argument("--progress-statuses", metavar="LIST",
                        help="Comma-separated Status option names for the 'In Progress' section")
    parser.add_argument("--next-statuses",     metavar="LIST",
                        help="Comma-separated Status option names for the 'Next Tasks' section")
    args = parser.parse_args()

    owner_type, login, number = parse_project_url(args.project_url)

    if args.check_status:
        _, _, su = fetch_project_meta(owner_type, login, number)
        if su and su.get("status"):
            print("STATUS_FOUND")
        else:
            print("STATUS_NOT_FOUND")
        return

    if args.list_statuses:
        for name in fetch_status_options(owner_type, login, number):
            print(name)
        return

    missing = [flag for flag, val in [
        ("--closed-statuses", args.closed_statuses),
        ("--progress-statuses", args.progress_statuses),
        ("--next-statuses", args.next_statuses),
    ] if not val]
    if missing:
        parser.error(f"{', '.join(missing)} required (use --list-statuses to see available options)")

    closed_statuses   = {s.strip() for s in args.closed_statuses.split(",") if s.strip()}
    progress_statuses = {s.strip() for s in args.progress_statuses.split(",") if s.strip()}
    next_statuses     = {s.strip() for s in args.next_statuses.split(",") if s.strip()}

    output_dir = Path(args.output_dir) if args.output_dir else Path.cwd() / "reports"
    date_str   = datetime.now().strftime("%Y-%m-%d")

    print("Fetching project metadata…", flush=True)
    proj_title, proj_desc, status_update = fetch_project_meta(owner_type, login, number)
    print(f"  → Project: {proj_title}", flush=True)

    print("Fetching project items…", flush=True)
    raw_items = fetch_all_items(owner_type, login, number)
    print(f"  → {len(raw_items)} items fetched", flush=True)

    items = [p for p in (parse_item(r) for r in raw_items) if p]
    closed_week, active, next_tasks = build_sections(items, closed_statuses, progress_statuses, next_statuses)

    print("Generating report…", flush=True)

    if args.format == "csv":
        paths = export_csv(closed_week, active, next_tasks, output_dir, date_str)
        status_path = export_status_csv(status_update, output_dir, date_str)
        paths.append(status_path)
        print(f"\n✓ {len(paths)} CSV files saved to: {output_dir}", flush=True)

    else:
        html = generate_html(
            raw_items, proj_title, proj_desc, status_update, args.project_url,
            closed_statuses, progress_statuses, next_statuses,
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

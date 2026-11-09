# Pulls dev time-log comments ("<date>: did X. Time spent: 1.5 hours") from the configured repos into <work dir>/github_*.csv
# Usage: gh_hours.py <start YYYY-MM-DD> <end YYYY-MM-DD> <work dir>   (run from the project folder; reads report.config.json)
import csv, datetime as dt, json, os, re, subprocess, sys
from zoneinfo import ZoneInfo
import cfg

C = cfg.load()
OWNER = C["github"]["owner"]
REPOS = C["github"]["repos"]
DEVS = {d["github"]: d["short"] for d in C["devs"] if d.get("github")}
TZ = ZoneInfo(C["timezone"])  # the zone devs log in; Zoho dates use it too
PROJECT = C["github"].get("project")
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

# "- 9 Oct: did X. Time spent: 1.5 hours" or "Oct 9 - ..."; the date prefix is optional
DATE_RE = re.compile(r"^\s*[-*]?\s*(?:\*\*)?(?:(\d{1,2})\s+([A-Za-z]{3})[a-z]*|([A-Za-z]{3})[a-z]*\s+(\d{1,2}))\b(?:\*\*)?\s*[:\-–]")
DUR_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(hours?|hrs?|h|minutes?|mins?|m)\b", re.I)
SPENT_RE = re.compile(r"(?:time\s*spent|time\s*log(?:ged)?|spent|time)\s*[:\-]?\s*((?:\d+(?:\.\d+)?\s*(?:hours?|hrs?|h|minutes?|mins?|m)\b\s*(?:and\s*)?)+)", re.I)
HOURISH_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:hours?|hrs?|minutes?|mins?)\b", re.I)

def duration(text):
    h = 0.0
    for n, unit in DUR_RE.findall(text):
        h += float(n) / 60 if unit.lower().startswith("m") else float(n)
    return round(h, 2)

def line_date(line, posted):
    m = DATE_RE.match(line)
    if not m:
        return None
    day, mon = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
    mon = MONTHS.get(mon.lower())
    if not mon:
        return None
    year = posted.year - (1 if mon > posted.month else 0)  # a Dec entry posted in Jan belongs to last year
    return dt.date(year, mon, int(day))

def parse(body, posted):
    # Returns (entries, unparsed lines). An entry is (work_date, hours, text, date_source)
    entries, unparsed = [], []
    lines = [l for l in body.splitlines() if l.strip()]
    for line in lines:
        m = SPENT_RE.search(line)
        if not m:
            if HOURISH_RE.search(line) and re.search(r"(?i)spent|worked|logged|time", line):
                unparsed.append(line.strip())
            continue
        d = line_date(line, posted)
        text = DATE_RE.sub("", line[:m.start()]).strip(" -*.:") or None
        entries.append((d or posted, duration(m.group(1)), text, "line" if d else "comment"))
    # A short comment that is only a duration ("2 hours", "45 min")
    if not entries and len(body.strip()) < 25 and DUR_RE.fullmatch(body.strip().rstrip(".")):
        entries.append((posted, duration(body), None, "comment"))
    return entries, unparsed

ISSUE_Q = """query($o:String!,$r:String!,$n:Int!){ repository(owner:$o,name:$r){ issueOrPullRequest(number:$n){ __typename
  ... on Issue{ title parent{ number title repository{name} } projectItems(first:10){ nodes{ project{ number } } } }
  ... on PullRequest{ title projectItems(first:10){ nodes{ project{ number } } } } } } }"""

def issue_meta(repo, number, cache={}):
    if (repo, number) not in cache:
        d = json.loads(subprocess.check_output(["gh", "api", "graphql", "-f", f"query={ISSUE_Q}", "-f", f"o={OWNER}",
                                                "-f", f"r={repo}", "-F", f"n={number}"]))["data"]["repository"]["issueOrPullRequest"]
        cache[(repo, number)] = d
    return cache[(repo, number)]

def main():
    start, end = (dt.date.fromisoformat(a) for a in sys.argv[1:3])
    out = sys.argv[3]
    rows, unparsed, activity = [], [], []
    since = dt.datetime.combine(start, dt.time(), TZ).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for repo in REPOS:
        out_lines = subprocess.check_output(["gh", "api", "--paginate", "--jq", ".[] | tojson",
                                             f"repos/{OWNER}/{repo}/issues/comments?since={since}&per_page=100"])
        for c in map(json.loads, out_lines.splitlines()):
            dev = DEVS.get(c["user"]["login"])
            if not dev:
                continue
            number = int(c["issue_url"].rsplit("/", 1)[1])
            posted = dt.datetime.fromisoformat(c["created_at"].replace("Z", "+00:00")).astimezone(TZ).date()
            entries, bad = parse(c["body"], posted)
            meta = issue_meta(repo, number)
            base = {"dev": dev, "repo": repo, "issue": number, "title": meta["title"],
                    "in_project": any(i["project"]["number"] == PROJECT for i in meta["projectItems"]["nodes"]),
                    "kind": meta["__typename"],
                    "parent": f'{meta["parent"]["repository"]["name"]}#{meta["parent"]["number"]} {meta["parent"]["title"]}' if meta.get("parent") else "",
                    "posted": posted.isoformat(), "comment_url": c["html_url"]}
            for d, h, text, src in entries:
                if start <= d <= end:
                    rows.append({**base, "work_date": d.isoformat(), "hours": h, "date_source": src,
                                 "days_late": (posted - d).days, "text": text or ""})
            for line in bad:
                unparsed.append({**base, "line": line})
            if start <= posted <= end and not entries:
                activity.append({**base, "first_line": c["body"].strip().splitlines()[0][:150]})
    for name, data in [("github_hours.csv", rows), ("github_unparsed.csv", unparsed), ("github_activity_no_hours.csv", activity)]:
        with open(os.path.join(out, name), "w", newline="") as fh:
            if data:
                w = csv.DictWriter(fh, fieldnames=data[0].keys()); w.writeheader(); w.writerows(data)
    print(f"{len(rows)} hour entries, {len(unparsed)} unparsed lines, {len(activity)} comments without hours", file=sys.stderr)

main()

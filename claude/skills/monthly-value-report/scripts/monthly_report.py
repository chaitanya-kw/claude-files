# Monthly value report: what was delivered, the value it brought, and where the dev hours went (by priority).
# Usage (from the project folder): monthly_report.py <YYYY-MM> <work dir> <--gaps | --preview | out.pdf | out.html> [more outputs]
#   --gaps     per dev and day: Zoho hours vs GitHub-logged hours, with the Zoho note, to write allocations.csv from
#   --preview  hour placement summary and the report content as bullets, for approval
# Reads from <work dir>: zoho.csv (zoho_hours.py), github_hours.csv (gh_hours.py), delivered_issues.csv and
# merged_prs.csv (delivered.py), allocations.csv (optional: dev,date,epic,hours,source,description; date may be blank
# for a month-level placement) and content.json (intro, highlights, per-priority delivered/value text).
# Zoho projects listed in config zoho.sm_projects (support & maintenance agreements) are kept out of the priority
# placement and shown as their own task table, from content.json "sm_tasks". A person with "fixed_epic" in the config
# (e.g. the project manager) has all their non-S&M hours placed on that one line, with no GitHub lookup.
# An allocation row with source=override replaces the GitHub logs for that dev and day. One with source=zoho-total
# adds billable hours the export is missing (the user's confirmed Zoho total minus the export); blank date = month level.
# Hours basis is Zoho billable. Per dev and day, GitHub hours are scaled down to the Zoho total when they exceed it;
# Zoho hours left over after GitHub logs and allocations are spread over that dev's month mix and reported as estimated.
import collections, csv, datetime as dt, html, json, os, sys
import cfg, kw_report as kw

C = cfg.load()
DEVS = [d["short"] for d in C["devs"]]
FIXED = {d["short"]: d["fixed_epic"] for d in C["devs"] if d.get("fixed_epic")}
SM = set(C["zoho"].get("sm_projects", []))
esc = html.escape

def rows(work, name):
    p = os.path.join(work, name)
    return list(csv.DictReader(open(p))) if os.path.exists(p) and os.path.getsize(p) else []

def place(work, verbose=False):
    zoho, gh, alloc = rows(work, "zoho.csv"), rows(work, "github_hours.csv"), rows(work, "allocations.csv")
    # replaced.csv (start,end,source): windows whose hours come from an already-sent weekly report instead of Zoho,
    # e.g. when the Zoho export is incomplete. Zoho, GitHub and dated allocations in the window are ignored; the
    # window's allocation rows with source=weekly-report stand in for both the Zoho hours and their placement.
    win = [(r["start"], r["end"], r.get("dev") or "") for r in rows(work, "replaced.csv")]
    inwin = lambda dev, d: any(a <= d <= b and (not w or w == dev) for a, b, w in win)
    zoho = [r for r in zoho if not inwin(r["dev"], r["date"]) and r["project"] not in SM]
    gh = [r for r in gh if not inwin(r["dev"], r["work_date"])]
    alloc = [r for r in alloc if not (r["date"] and inwin(r["dev"], r["date"])) or r["source"] == "weekly-report"]
    z = collections.defaultdict(float)
    notes = collections.defaultdict(list)
    for r in zoho:
        z[(r["dev"], r["date"])] += float(r["hours"])
        if r["note"] and r["note"] != "-":
            notes[(r["dev"], r["date"])].append(f'{float(r["hours"]):g} h: {r["note"]}')
    day = collections.defaultdict(lambda: collections.defaultdict(float))  # (dev,date) -> epic -> h
    items = collections.defaultdict(lambda: collections.defaultdict(float))  # epic -> work item -> h (raw)
    over = {(r["dev"], r["date"]) for r in alloc if r["source"] == "override"}
    for r in zoho:
        if r["dev"] in FIXED:
            day[(r["dev"], r["date"])][FIXED[r["dev"]]] += float(r["hours"])
            items[FIXED[r["dev"]]][r["task"]] += float(r["hours"])
    for r in gh:
        if r["dev"] not in DEVS or r["dev"] in FIXED or (r["dev"], r["work_date"]) in over:
            continue
        e = cfg.epic_of(C, f'{r["repo"]}#{r["issue"]}')
        day[(r["dev"], r["work_date"])][e] += float(r["hours"])
        items[e][f'{r["title"]} ({r["repo"]}#{r["issue"]})'] += float(r["hours"])
    month_alloc = collections.defaultdict(lambda: collections.defaultdict(float))
    for r in alloc:
        # weekly-report / zoho-total rows are billable hours missing from the export (confirmed by the user), so they
        # count as Zoho hours as well as being placed
        if r["source"] in ("weekly-report", "zoho-total"):
            z[(r["dev"], r["date"])] += float(r["hours"])
        if r["date"]:
            day[(r["dev"], r["date"])][r["epic"]] += float(r["hours"])
        else:
            month_alloc[r["dev"]][r["epic"]] += float(r["hours"])
        items[r["epic"]][r["description"]] += float(r["hours"])
    if verbose:
        for k in sorted(set(z) | set(day)):
            got = sum(day[k].values())
            if abs(z[k] - got) > 0.05:
                print(f"{k[0]} {k[1]}: Zoho {z[k]:.2f} h, logged {got:.2f} h, gap {z[k] - got:+.2f} h"
                      + (f" | GitHub: " + ", ".join(f"{e} {h:g}" for e, h in day[k].items()) if day[k] else "")
                      + "".join(f"\n    note {n[:600]}" for n in notes[k]))
        return
    hours = collections.defaultdict(collections.Counter)  # epic -> dev -> h
    left, orphan, scaled = collections.Counter(), collections.defaultdict(collections.Counter), collections.Counter()
    for (dev, d) in set(z) | set(day):
        zh, logged = z.get((dev, d), 0.0), day.get((dev, d), {})
        tot = sum(logged.values())
        if not zh:
            for e, h in logged.items():
                orphan[dev][e] += h
            continue
        f = min(1.0, zh / tot) if tot else 0
        scaled[dev] += tot - tot * f
        for e, h in logged.items():
            hours[e][dev] += h * f
        left[dev] += zh - tot * f
    est = collections.defaultdict(collections.Counter)
    for dev in DEVS:
        # Leftover Zoho hours: month-level allocations first, then the dev's own month mix. GitHub logs on days with no
        # billable Zoho time are ignored: those days are usually unbilled (training, other clients)
        for i, mix in enumerate((month_alloc[dev], {}, {e: hours[e][dev] for e in hours if hours[e][dev]})):
            if left[dev] <= 0.05 or not mix:
                continue
            mt = sum(mix.values())
            take = left[dev] if i == 2 else min(left[dev], mt)
            for e, h in mix.items():
                est[e][dev] += take * h / mt
            left[dev] -= take
    for e in est:
        hours[e].update(est[e])
    return hours, est, left, scaled, z, items

def name(e):
    return C.get("labels", {}).get(e) or cfg.epic_name(C, e)

def li(items, size=11):
    return (f'<ul style="margin:4px 0 0 0;padding-left:16px;font-family:{kw.SANS};font-size:{size}px;line-height:1.45;color:{kw.INK};">'
            + "".join(f'<li style="margin:0 0 1px 0;">{esc(i)}</li>' for i in items) + "</ul>")

def value_cell(title, value, delivered):
    return (f'<div style="font-weight:600;font-size:12.5px;">{esc(title)}</div>'
            + (f'<div style="font-size:11px;color:#4a5263;line-height:1.4;margin-top:2px;"><b style="color:{kw.INK};">Value: </b>{esc(value)}</div>' if value else "")
            + (li(delivered) if delivered else ""))

def main():
    month, work = sys.argv[1:3]
    outs = sys.argv[3:]
    if outs == ["--gaps"]:
        place(work, verbose=True)
        return
    unknown = sorted({r["dev"] for r in rows(work, "zoho.csv")} - set(DEVS))
    if unknown:
        sys.exit("People with billable time who aren't in report.config.json devs: " + ", ".join(unknown)
                 + ". Ask the user what each does on the project, then add them (github login, or fixed_epic for a role line).")
    hours, est, left, scaled, z, items = place(work)
    smz = [r for r in rows(work, "zoho.csv") if r["project"] in SM]
    win = [(r["start"], r["end"], r.get("dev") or "", r["source"]) for r in rows(work, "replaced.csv")]
    content = json.load(open(os.path.join(work, "content.json")))
    pc = content.get("priorities", {})
    order = sorted(hours, key=lambda e: -sum(hours[e].values()))
    missing = [e for e in order if e not in pc and sum(hours[e].values()) >= 0.5]
    if missing:
        sys.exit("content.json has no entry under 'priorities' for: " + ", ".join(missing) + "\nWork items:\n" + "\n".join(
            f"{e} ({name(e)}): " + "; ".join(f"{k} [{v:.1f} h]" for k, v in sorted(items[e].items(), key=lambda x: -x[1])) for e in missing))
    acc = collections.Counter()
    for e in hours:
        acc.update(hours[e])
    total = sum(acc.values())
    sm_tasks = content.get("sm_tasks", [])
    smt, smz_dev, smt_dev = sum(float(r["hours"]) for r in smz), collections.Counter(), collections.Counter()
    for r in smz:
        smz_dev[r["dev"]] += float(r["hours"])
    for t in sm_tasks:
        smt_dev[t["dev"]] += float(t["hours"])
    if smz and any(abs(smz_dev[d] - smt_dev[d]) > 0.05 for d in set(smz_dev) | set(smt_dev)):
        sys.exit("content.json sm_tasks ({date, dev, task, hours}) don't add up to the S&M Zoho hours per person: "
                 + ", ".join(f"{d} Zoho {smz_dev[d]:g} vs tasks {smt_dev[d]:g}" for d in sorted(set(smz_dev) | set(smt_dev)))
                 + "\nS&M Zoho rows:\n" + "\n".join(f'{r["date"]} {r["dev"]} {r["hours"]} h: {r["note"]}' for r in smz))
    sm_label = C["zoho"].get("sm_label", "Support & maintenance")
    sm_devs = [d for d in DEVS if smz_dev[d]]
    issues, prs = rows(work, "delivered_issues.csv"), rows(work, "merged_prs.csv")
    closed = [i for i in issues if i["is_parent"] != "True"]
    zt = collections.Counter()
    for (dev, _), h in z.items():
        zt[dev] += h
    m0 = dt.date.fromisoformat(month + "-01")
    label = f"{m0:%B %Y}"

    if outs == ["--preview"]:
        print("Hour placement (Zoho billable is the basis):")
        for a, b, w, src in win:
            print(f"- {a} to {b}{' for ' + w if w else ''} taken from {src}")
        for dev in DEVS:
            e_dev = sum(est[e][dev] for e in est)
            print(f"- {dev}: Zoho {zt[dev]:.1f} h, placed {acc[dev]:.1f} h (estimated spread {e_dev:.1f} h; GitHub hours trimmed to Zoho {scaled[dev]:.1f} h)"
                  + (f"; UNPLACED {left[dev]:.1f} h" if left[dev] > 0.05 else ""))
        # Weekdays with no billable log usually mean a stale export or late logging: check before trusting the totals
        last = (m0.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)
        wd = [m0 + dt.timedelta(i) for i in range((last - m0).days + 1) if (m0 + dt.timedelta(i)).weekday() < 5
              and (m0 + dt.timedelta(i)).isoformat() not in C.get("holidays", [])]
        print("Weekdays with no billable Zoho log (stale export, leave or late logging? check before building):")
        smday = {(r["dev"], r["date"]) for r in smz}
        for dev in [d for d in DEVS if d not in FIXED]:
            miss = [f"{d:%a %d}" for d in wd if not z.get((dev, d.isoformat())) and (dev, d.isoformat()) not in smday and not any(a <= d.isoformat() <= b and (not w or w == dev) for a, b, w, _ in win)]
            print(f"- {dev}: {len(miss)} days" + (f" ({', '.join(miss)})" if miss else ""))
        print(f"\n{label}: {total + smt:.1f} h in total · development {total:.1f} h · {sm_label} {smt:.1f} h")
        print(f"Development: {total:.1f} h · " + " · ".join(f"{d} {acc[d]:.1f} h" for d in DEVS)
              + (f" · {len(closed)} tasks completed" if content.get("show_tasks_completed", True) else "")
              + f" · {len(prs)} changes shipped\n")
        print("Highlights:")
        for h in content.get("highlights", []):
            print(f"- {h}")
        print("\nDelivered and value, by priority:")
        for e in order:
            p = pc.get(e, {})
            split = ", ".join(f"{d} {hours[e][d]:.1f}" for d in DEVS if hours[e][d] >= 0.05)
            print(f"- **{p.get('title') or name(e)}: {sum(hours[e].values()):.1f} h** ({split}; {sum(est[e].values()):.1f} h estimated)")
            if p.get("value"):
                print(f"  Value: {p['value']}")
            for d in p.get("delivered", []):
                print(f"    - {d}")
        if smz:
            print(f"\n{sm_label}: {smt:.1f} h (" + ", ".join(f"{d} {smz_dev[d]:.1f}" for d in sm_devs) + ")")
            if content.get("sm_intro"):
                print(f"  {content['sm_intro']}")
            for t in sm_tasks:
                print(f"- {dt.date.fromisoformat(t['date']):%d %b} · {t['dev']} · {t['task']} · {float(t['hours']):.1f} h")
        return

    glance = [(f"{total + smt:.0f}", "Total hours"), (f"{total:.0f}", "Development")] + ([(f"{smt:.0f}", sm_label)] if smz else [])
    # content.json "show_tasks_completed": false drops the closed-issue count (e.g. when a bulk board cleanup inflates it)
    tasks = [(str(len(closed)), "Tasks completed")] if content.get("show_tasks_completed", True) else []
    sections = [("The month at a glance", kw.cards(glance + tasks + [(str(len(prs)), "Changes shipped")]))]
    if content.get("intro"):
        sections[0] = (sections[0][0], kw.para(content["intro"]) + '<div style="height:10px"></div>' + sections[0][1])
    if content.get("highlights"):
        sections.append(("Highlights", kw.bullets(content["highlights"])))
    cols = [("Priority, what we delivered and why it matters", "left", None), ("Effort (Hr)", "right", "76px")]
    vrows = [[value_cell(pc.get(e, {}).get("title") or name(e), pc.get(e, {}).get("value", ""), pc.get(e, {}).get("delivered", [])),
              f"<b>{sum(hours[e].values()):.1f}</b>"] for e in order if sum(hours[e].values()) >= 0.5]
    dev_title = content.get("dev_title", "What we delivered")
    sections.append((dev_title, kw.table(cols, vrows, ["Total", f"{total:.1f}"])))
    tcols = [("Priority", "left", None)] + [(d, "right", "46px") for d in DEVS] + [("Total", "right", "56px"), ("Share", "right", "50px")]
    trows = [[esc(pc.get(e, {}).get("title") or name(e))] + [f"{hours[e][d]:.1f}" if hours[e][d] >= 0.05 else "–" for d in DEVS]
             + [f"<b>{sum(hours[e].values()):.1f}</b>", f"{100 * sum(hours[e].values()) / total:.0f}%"] for e in order if sum(hours[e].values()) >= 0.05]
    foot = ["Total"] + [f"{acc[d]:.1f}" for d in DEVS] + [f"{total:.1f}", "100%"]
    # No footnote on how hours were placed: that's internal and stays off the client report
    sections.append(("Where the time went", kw.table(tcols, trows, foot), True))
    if smz:
        scols = [("Date", "left", "54px"), ("Task", "left", None), ("By", "left", "70px"), ("Effort (Hr)", "right", "76px")]
        srows = [[f"{dt.date.fromisoformat(t['date']):%d %b}", esc(t["task"]), esc(t["dev"]), f"{float(t['hours']):.1f}"] for t in sm_tasks]
        intro = (kw.para(content["sm_intro"]) + '<div style="height:8px"></div>') if content.get("sm_intro") else ""
        sections.append((sm_label, intro + kw.table(scols, srows, ["", "Total", "", f"{smt:.1f}"]), len(srows) <= 15))
    doc = kw.page(C.get("title", f'{C["client"]} development'), f"Monthly report · {label}", sections, C["client"], label)
    for out in outs:
        kw.write(doc, out, work, max_pages=content.get("max_pages", 3))

main()

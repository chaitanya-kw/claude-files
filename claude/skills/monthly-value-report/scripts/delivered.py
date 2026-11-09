# Lists what shipped in the window: issues closed as completed and PRs merged into each repo's deploy branch,
# each rolled up to its priority. Writes <work dir>/delivered_issues.csv and <work dir>/merged_prs.csv.
# Usage: delivered.py <start> <end> <work dir>
import csv, os, re, sys
import cfg

C = cfg.load()
OWNER, REPOS = C["github"]["owner"], C["github"]["repos"]
BRANCH = C["github"].get("deploy_branches", {})

def write(path, rows, fields):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields); w.writeheader(); w.writerows(rows)

def main():
    start, end, work = sys.argv[1:4]
    issues, prs = [], []
    for r in REPOS:
        for i in cfg.gh_json(["issue", "list", "-R", f"{OWNER}/{r}", "--state", "closed", "--limit", "500",
                              "--search", f"closed:{start}..{end} reason:completed",
                              "--json", "number,title,closedAt,labels,assignees,url"]):
            key = f"{r}#{i['number']}"
            labels = [l["name"] for l in i["labels"]]
            issues.append({"epic": cfg.epic_of(C, key), "issue": key, "title": i["title"], "closed": i["closedAt"][:10],
                           "is_parent": C["github"].get("parent_label", "parent") in labels,
                           "assignees": " ".join(a["login"] for a in i["assignees"]), "url": i["url"]})
        branch = BRANCH.get(r, "main")
        for p in cfg.gh_json(["pr", "list", "-R", f"{OWNER}/{r}", "--state", "merged", "--base", branch, "--limit", "500",
                              "--search", f"merged:{start}..{end}",
                              "--json", "number,title,body,mergedAt,author,url"]):
            # Issues named with a closing keyword in the body, else any #n in the title (same-repo references only)
            refs = re.findall(r"(?i)\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)", p["body"] or "") or re.findall(r"#(\d+)", p["title"])
            linked = list(dict.fromkeys(f"{r}#{n}" for n in refs if n != str(p["number"])))
            prs.append({"epic": cfg.epic_of(C, linked[0]) if linked else "", "pr": f"{r}#{p['number']}", "branch": branch,
                        "title": p["title"], "merged": p["mergedAt"][:10], "author": p["author"]["login"],
                        "issues": " ".join(linked), "url": p["url"]})
    issues.sort(key=lambda x: (x["epic"], x["closed"]))
    prs.sort(key=lambda x: (x["epic"], x["merged"]))
    write(os.path.join(work, "delivered_issues.csv"), issues, ["epic", "issue", "title", "closed", "is_parent", "assignees", "url"])
    write(os.path.join(work, "merged_prs.csv"), prs, ["epic", "pr", "branch", "title", "merged", "author", "issues", "url"])
    print(f"{len(issues)} issues closed as completed, {len(prs)} PRs merged into deploy branches")
    by = {}
    for i in issues:
        by.setdefault(i["epic"], 0)
        by[i["epic"]] += 1
    for e, n in sorted(by.items(), key=lambda x: -x[1]):
        print(f"- {cfg.epic_name(C, e)} [{e}]: {n} closed")

main()

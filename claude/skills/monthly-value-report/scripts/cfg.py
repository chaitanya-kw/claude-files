# Shared helpers for the monthly value report: loads report.config.json from the project folder (cwd),
# resolves priorities and walks GitHub sub-issue chains up to a priority.
import json, os, re, subprocess, sys

CONFIG = os.environ.get("REPORT_CONFIG", "report.config.json")

def load():
    if not os.path.exists(CONFIG):
        sys.exit(f"No {CONFIG} in {os.getcwd()}. Copy config.example.json from the skill folder and fill it in.")
    c = json.load(open(CONFIG))
    c.setdefault("timezone", "Asia/Kolkata")
    c.setdefault("output_dir", "monthly-reports")
    c.setdefault("epic_overrides", {})
    return c

def gh_json(args):
    return json.loads(subprocess.check_output(["gh"] + args))

def priorities(c, cache={}):
    # {"repo#n": "Priority name"} from a markdown file of [repo #n] links (one table row per priority),
    # or from open+closed issues carrying the parent label in each repo
    if "p" in cache:
        return cache["p"]
    p = {}
    pf = c.get("priorities_file")
    if pf and os.path.exists(pf):
        repos = "|".join(re.escape(r) for r in c["github"]["repos"])
        for name, r, n in re.findall(r"\|\s*(?:\d+\s*\|)?\s*([^|]+?)\s*\|\s*\[(" + repos + r") #(\d+)\]", open(pf).read()):
            p[f"{r}#{n}"] = re.sub(r"\s+[—-]\s+\*\*.*?\*\*", "", name).replace("**", "").strip()
    elif c["github"].get("parent_label"):
        for r in c["github"]["repos"]:
            for i in gh_json(["issue", "list", "-R", f'{c["github"]["owner"]}/{r}', "--label", c["github"]["parent_label"],
                              "--state", "all", "--limit", "200", "--json", "number,title"]):
                p[f"{r}#{i['number']}"] = i["title"]
    cache["p"] = p
    return p

PARENT_Q = """query($o:String!,$r:String!,$n:Int!){ repository(owner:$o,name:$r){ issueOrPullRequest(number:$n){
  ... on Issue{ parent{ number repository{name} } } } } }"""

def epic_of(c, key, cache={}):
    # Follows epic_overrides and the sub-issue chain until a listed priority; returns the top issue reached otherwise
    prio, ov = priorities(c), c["epic_overrides"]
    seen = set()
    while key not in prio and key not in seen:
        seen.add(key)
        if key in ov:
            key = ov[key]
            continue
        if key not in cache:
            repo, n = key.split("#")
            try:
                d = gh_json(["api", "graphql", "-f", f"query={PARENT_Q}", "-f", f'o={c["github"]["owner"]}', "-f", f"r={repo}", "-F", f"n={n}"])
                p = (d["data"]["repository"]["issueOrPullRequest"] or {}).get("parent")
            except subprocess.CalledProcessError:  # a reference to a number that doesn't exist in that repo
                p = None
            cache[key] = f'{p["repository"]["name"]}#{p["number"]}' if p else None
        if not cache[key]:
            break
        key = cache[key]
    return key

def epic_name(c, e):
    prio = priorities(c)
    if e in prio:
        return prio[e]
    if e in c.get("labels", {}):
        return c["labels"][e]
    return f"Not under a priority yet ({e})" if "#" in e else e

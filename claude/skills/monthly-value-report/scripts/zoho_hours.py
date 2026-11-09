# Extracts the month's billable Zoho time logs of everyone on the configured projects into <work dir>/zoho.csv.
# People not in the config are kept under their Zoho name and listed, so the user can say what they do.
# Usage: zoho_hours.py <start> <end> <timesheet.xlsx[,more.xlsx]> <work dir>
# Overlapping exports are fine: identical rows are counted once.
import csv, os, sys
import openpyxl, warnings
import cfg

warnings.filterwarnings("ignore")
C = cfg.load()
DEVS = {d["zoho"]: d["short"] for d in C["devs"]}
PROJECTS = set(C["zoho"]["projects"])

def main():
    start, end, files, work = sys.argv[1:5]
    out, seen, alldates = [], set(), []
    for xlsx in files.split(","):
        rows = openpyxl.load_workbook(xlsx, read_only=True).worksheets[0].iter_rows(values_only=True)
        hdr = next(r for r in rows if r and "User" in r and "Date" in r)
        ix = {k: i for i, k in enumerate(hdr)}
        dates = []
        for r in rows:
            if not r or not r[ix["Date"]]:
                continue
            d = str(r[ix["Date"]])
            d = f"{d[6:10]}-{d[3:5]}-{d[0:2]}"  # Zoho exports DD-MM-YYYY
            dates.append(d)
            if r in seen or r[ix["Project ID"]] not in PROJECTS or r[ix["Billing Type"]] != "Billable":
                continue
            seen.add(r)
            if start <= d <= end:
                out.append({"dev": DEVS.get(r[ix["User"]], r[ix["User"]]), "date": d, "project": r[ix["Project ID"]],
                            "task": r[ix["Task/General/Bugs"]] or "", "hours": float(r[ix["Hours(For Calculation)"]] or 0),
                            "note": " | ".join(l.strip() for l in str(r[ix["Notes"]] or "").splitlines() if l.strip())})
        alldates += dates
        print(f"Timesheet {os.path.basename(xlsx)}: " + (f"{min(dates)} to {max(dates)}" if dates else "no dated rows"))
    if not alldates or min(alldates) > start or max(alldates) < end:
        print(f"WARNING: the timesheets don't cover the whole window {start} to {end}")
    out.sort(key=lambda x: (x["dev"], x["date"]))
    with open(os.path.join(work, "zoho.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["dev", "date", "project", "task", "hours", "note"])
        w.writeheader(); w.writerows(out)
    tot = {}
    for r in out:
        tot[r["dev"]] = tot.get(r["dev"], 0) + r["hours"]
    unknown = sorted({r["dev"] for r in out} - set(DEVS.values()))
    if unknown:
        print("NOT IN CONFIG (ask the user what each does on the project, then add them to devs): "
              + ", ".join(f"{u} {tot[u]:.1f} h" for u in unknown))
    print("Zoho billable: " + ", ".join(f"{d} {h:.1f} h" for d, h in tot.items()) + f"; total {sum(tot.values()):.1f} h")

main()

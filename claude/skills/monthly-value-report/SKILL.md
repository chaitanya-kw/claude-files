---
name: monthly-value-report
description: Monthly client report (PDF and/or Gmail-paste HTML, Kilowott weekly-report house style) showing the value the dev team delivered in a month — highlights, what shipped under each priority and why it matters, and where the billable hours went. Zoho billable hours from the month's timesheet xlsx, placed on priorities from GitHub issue time logs and Zoho notes; delivered work from issues closed and PRs merged to deploy branches. Works in any project folder that has a report.config.json. Use when the user asks for the monthly report, monthly value report, or month's dev summary for a client.
---

# Monthly value report

The goal is to show the client **what was delivered and the value it brought**, with hours as supporting
evidence at priority level. It is not an hour-by-hour attribution: don't chase single hours, and keep the effort on
the delivered and value wording.

Run from the project folder (it holds `report.config.json`). Scripts are in this skill's `scripts/` folder:
`S=~/.claude/skills/monthly-value-report/scripts`. Use a Python that has openpyxl (create a venv with
`python3 -m venv .venv && .venv/bin/pip install openpyxl` in the project if none exists). `gh` must be logged in.

Outputs: `<output_dir>/<YYYY-MM>/<client-slug>-monthly-report-<YYYY-MM>.pdf` and/or `.html` (Gmail paste).
Working files: `<output_dir>/<YYYY-MM>/.source/` (`W`), kept so the report can be rebuilt.

## First run in a project

If there's no `report.config.json`, copy `config.example.json` from the skill folder and fill it in with the user:
GitHub owner, repos, project number and deploy branch per repo; people (short name, Zoho user name exactly as in the
timesheet, and either a GitHub login (plus `github_aliases` if they post under more than one) or a `fixed_epic`: one report line that takes all their hours, for roles such as
project management or senior oversight); Zoho project IDs for this client, with any support & maintenance projects
also listed in `zoho.sm_projects` (plus `sm_label`); the priorities source
(`priorities_file`, a markdown table with `[repo #n]` links, or else `github.parent_label`); `holidays` (dates the
missing-days check skips; add any the user confirms during a run). Ask only for what
can't be found in the folder (CLAUDE.md, a PRIORITIES file, existing weekly-report scripts).

## Steps

1. **Window and folder.** Month `M=YYYY-MM` (default: the previous month). `W=<output_dir>/$M/.source; mkdir -p $W`.
2. **Timesheet.** The month's final Zoho timesheet xlsx (from the config's Drive folder if set, newest file covering
   the month; use the copy in `~/Downloads`, don't pull it through the Drive tool). It must be exported **after** the
   devs finished logging the month: an export taken in the first days of the next month often misses the last week.
   `python $S/zoho_hours.py <start> <end> <xlsx[,xlsx2]> $W`.
   **Everyone's billable time on the client's projects counts**, not just the devs (unlike the weekly reports): project
   managers, senior staff, QA and anyone else. When it prints `NOT IN CONFIG`, or you aren't sure what someone does on
   the project, **ask the user** what their role was and how to show it, then add them to `devs` (a GitHub login if
   they log work on issues, else a `fixed_epic` line named for the role). Don't guess roles.
   If the user gives a Zoho total that differs from the export (a late log), add the difference as an allocation row
   with `source` = `zoho-total` (blank date = month level, placed on the person's line or mix).
3. **GitHub.** `python3 $S/gh_hours.py <start> <end> $W` (time-log comments) and
   `python3 $S/delivered.py <start> <end> $W` (issues closed as completed, PRs merged into deploy branches, each rolled
   up to a priority). Look at `delivered_issues.csv` for issues that land on "Not under a priority yet": map them in
   `epic_overrides` in the config (the report only, not GitHub), and list them for the user as parent-link suggestions.
4. **Fill gaps.** `python3 $S/monthly_report.py $M $W --gaps` prints each dev-day where Zoho and GitHub hours differ,
   with the Zoho note. Write `$W/allocations.csv` (`dev,date,epic,hours,source,description`) from the notes: `epic` is a
   priority key (`repo#n`) or a plain label for work with no issue (give it a client-friendly name under `labels`).
   Quote descriptions that contain commas. Mark estimated splits `(est. split)`. Don't guess where a note is empty:
   leftover hours are spread over that dev's month mix automatically and shown as "estimated" in the preview.
   Keep placements consistent with what the weekly reports already told the client for the same days. Where a dev's
   GitHub log for a day belongs to the S&M project rather than development, add `override` rows for that day
   (`source` = `override`): they replace that day's GitHub logs.
   GitHub logs on days with no billable Zoho time are ignored: those days are unbilled (training, other clients), and
   unbilled time stays off the report.
   **If the Zoho export is incomplete** for a dev (check the Drive folder for a newer export first, then ask the user
   for the dev's real Zoho total), write `$W/replaced.csv` (`start,end,dev,source`; blank `dev` = everyone) and
   allocation rows for that dev and window, dated the window's start, with `source` = `weekly-report`. Their hours make
   up the missing time (Zoho total minus what the export has), split as in the weekly report already sent for those
   days. Zoho, GitHub and dated allocations for that dev inside the window are then ignored.
5. **Content.** Write `$W/content.json`:
   - `intro`: two sentences on the month.
   - `highlights`: 3–5 bullets, the most valuable outcomes, each a concrete result plus why it matters.
   - `priorities`: `{epic: {"value": "...", "delivered": ["...", ...], "title": optional display name}}` for every
     epic with hours. `value` is one sentence on the business benefit (revenue protected, less manual work, fewer
     errors, safer releases, better data for decisions). `delivered` has 1–6 bullets of finished outcomes, not
     activity. Base them on closed issues, merged PRs and notes. Only claim what is shipped; say "built and tested"
     or "started" otherwise.
   - `sm_tasks` when the config has `sm_projects` with hours this month: `[{date, dev, task, hours}]`, one row per
     S&M Zoho entry, `task` in client language from its note. Per person they must add up to the S&M Zoho hours (the
     script stops and lists the S&M rows otherwise). Optional `sm_intro` (one sentence above the S&M table).
   - each `fixed_epic` line needs an entry under `priorities` too: what that role delivered in the month. Ask the user
     when the evidence doesn't show it.
   - optional: `dev_title` (heading of the delivered section), `hours_note` (footnote under the hours table),
     `max_pages` (default 3), `show_tasks_completed: false` (drops the closed-issue count, e.g. when a bulk board
     cleanup inflates it).
   Keep the report to the month in question: what was done and delivered in it. No plans, next steps or upcoming
   work.
   Back the main value claims with **2–3 hard numbers** from the project's own data (read-only queries through the
   project's database tooling or skill, e.g. before/after rates around a fix). Use a like-for-like comparison, give the
   period, and show each query and result to the user. Drop a number that doesn't clearly support the claim.
   Write for the client: plain language, no plugin/class/API names, no issue numbers, no customer personal data,
   no fault, apology or credit language. Verify any number you state (counts, dates) from the data.
6. **Preview.** `python3 $S/monthly_report.py $M $W --preview`. Show the user, as bullets (not tables):
   - the report content: totals, intro, highlights, each priority with hours (per dev), value and delivered bullets;
   - only problems that need the user: a dev whose placed hours don't match Zoho or who has UNPLACED hours,
     **weekdays with no billable Zoho log** (skip the config's `holidays`; many missing days at the month end usually
     mean a stale export), and unparented issues with suggested parents (link them only after approval, via the
     project's triage rules if it has them).
   Don't add a section explaining how the hours were placed.
   Show the draft **in the conversation**: don't write a PDF or HTML yet, not even a test build. Then **stop for
   approval**. Apply changes and show the draft again until the user approves.
6b. **Adversarial review**, **once per report**, after the user approves the draft and before the first build. Once
   its points are settled, don't review the report again (later changes and rebuilds go straight through) unless
   the user asks for another review. Take the role of a disputatious client
   trying to poke holes in the report, check each suspicion against the data, and list the biggest weak spots, ranked:
   - mismatches with reports already sent (weekly reports for the same days, earlier monthly reports);
   - headline counts that don't hold up (what's counted, reverts, bulk closures, test-only merges);
   - rework presented as value, and claims that go beyond the records ("every", "all", unquantified "fewer");
   - hours with thin evidence (blank notes, estimated splits, role lines, days over 8 h, totals not in the export);
   - overlaps between lines (e.g. S&M vs development maintenance) and sensitive items (incidents, disputes).
   For each: the client's likely challenge, our exposure, and a suggested fix. The user settles each point (fix,
   reword, or keep as is). Apply the decisions, show what changed, and only then ask which output: **PDF**,
   **Gmail HTML**, or **both**. Don't build until every point is settled. Record in `$W/review-done` that the
   review happened, so a later session on the same month doesn't repeat it.
7. **Build** once the review points are settled. Delete the previous outputs for the month first: `python3 $S/monthly_report.py $M $W <out.pdf> <out.html>` (the PDF is always built, in
   `$W` if only HTML was asked for, to check length). It prints `PAGES: n`. Render with
   `pdftoppm -r 60 -png <pdf> $W/page` and look at every page: no table split awkwardly, no orphaned headings.
   If it runs over `max_pages`, suggest specific trims to the user rather than trimming yourself.
8. **Reply** with the output paths. For Gmail: open the `.html` in Chrome, Ctrl+A, Ctrl+C, paste into the compose window.

## Rules

- Hours basis is Zoho billable for everyone on the configured projects; S&M projects are reported in their own task
  table, apart from development. GitHub only says what the time was spent on.
- Never add made-up hours. Estimated placement of real hours is fine if the preview shows it.
- PDF and Gmail-paste HTML only (no .docx/.xlsx). Styling comes from `scripts/kw_report.py` (Kilowott house style,
  the same as the weekly reports). Everything is inline-styled so it survives a Gmail paste.
- Leave project-specific rules (who is out of scope, deploy branches, report wording conventions) to the project's
  CLAUDE.md and config; follow them when present.

---
name: snm-tnm-monthly-report-generator
description: >
  Generates a Kilowott monthly client report HTML file combining S&M (Support & Maintenance)
  and T&M (Time & Materials) sections. Trigger ONLY when the user is working on an S&M or T&M
  project — for example: "generate the S&M report", "create the T&M report", "make the monthly
  report for the S&M project", "build the S&M/T&M report for [month]", or any phrasing that
  explicitly references an S&M or T&M project and implies producing a formatted HTML delivery
  report. Also trigger when the user provides an S&M or T&M task list and asks to turn it into
  a report. Do NOT trigger for general monthly summaries, plain text reports, internal status
  updates, or reports for projects that are not explicitly S&M or T&M.
---

# S&M / T&M Monthly Report Generator

Produces a branded Kilowott HTML report file. Structure:
- **Summary**, **Blockers**, **Value Add** — narrative sections
- **Support Overview** — category table (Functional Bugs / Performance Issues / Security Issues / Content Changes / Enhancement / Integration Error)
- **Maintenance Overview** — category table (Core Updates / Plugin & Package Updates / Security Scan / Uptime Scan / Accessibility Scan)
- **Support & Maintenance Updates** — flat task table with effort, totalled
- **Core Framework Updates** and **Plugin & Package Updates** — optional, each omitted when there's no data
- **Scan findings** — one standalone section per scan category in the Maintenance Overview (e.g. "Security Scan Findings"), top 10 findings each
- **Time & Materials Updates** — flat T&M task table with effort, totalled
- **Footer**

Terminology is unified throughout: hours are always called **effort**; anything the team did is a **task**.

**Client-facing tone:** this report is read by the client, not written about them internally. Never use "the client" or "they" to refer to the client anywhere in the document — narrative sections, table notes, everywhere. Use **{{CLIENT_NAME}}** directly, or rephrase so no pronoun is needed (passive voice, or naming the platform/site instead of the org). For example, write "This reduces load times across the site" rather than "This reduces load times for the client" or "...for them."

---

## Step 1 — Confirm project, client name, and month

1. Check whether the conversation is running inside a Claude Project.
   - If yes, read the project name from context and confirm it with the user: "This looks like the **{{PROJECT_NAME}}** project — is that right?"
   - If not in a Project context, ask directly: "What's the project name for this report?"
2. This report is client-facing, so it must never refer to the client as "the client" or "they" (see the tone rule below). Check the conversation and memory for the client's name.
   - If found, present it back for approval: "I'll refer to the client as **{{CLIENT_NAME}}** in the report — is that right?"
   - If not found, or if it's ambiguous whether the client name matches the project name, ask directly rather than guessing.
3. Suggest the current calendar month/year as the reporting period. If the user overrides it, use whatever they specify. Never assume a different month without being told.

---

## Step 2 — Gather S&M / T&M task data

Ask for data if not already provided. Accept **any** of the following, and mixed input across multiple messages is fine:

- CSV (header row required, columns in any order)
- Google Doc link (fetch with the Google Drive tool available: `google_drive_fetch` on claude.ai, the Google Drive connector's read tool in Claude Code)
- Screenshot of a project management tool (parse visually — read description, status, dates, effort, category/type directly off the image)
- `.md` file
- Typed directly in chat (freeform or table)

**Required fields per task:**

| Field | Notes |
|---|---|
| `description` | free text |
| `section` | `SM` or `TM`. Default to `SM` if unstated; ask if genuinely ambiguous |
| `type` | *(SM tasks only)* `Support` or `Maintenance` — infer from description if not given, ask if unclear |
| `category` | Depends on `type` — see inference rules below |
| `status` | One of `Open` / `In Progress` / `Resolved` / `Deployed`. Default `Deployed` if not stated |
| `priority` | High / Medium / Low |
| `effort_hr` | numeric, hours |
| `date` | any unambiguous format |

**Category inference:** see `references/category-inference.md` for both the Support category rules (unchanged 6 categories) and the new Maintenance category rules (5 categories). If a category can't be confidently inferred, ask the user — do not guess on a low-confidence match.

**Maintenance-only fields (category-level, not per-task):** `Frequency` and `Next Schedule` are properties of the maintenance category itself (e.g. "Security Scan runs monthly, next due 15 Jul"), not of individual tasks. These are usually not present in a task list. If missing, ask the user once per maintenance category that has at least one task this month. `Note` is optional free text per category — leave blank if not provided, don't fabricate one.

---

## Step 3 — Generate narrative sections

Draft these from the task data, holding a high confidence bar — if the task list doesn't clearly support a claim, ask rather than invent. Write every sentence per the client-facing tone rule above — use {{CLIENT_NAME}} or rephrase, never "the client" or "they".

- **Summary** — 2-4 sentences on what was done this reporting period.
- **Blockers** — blockers the team faced and resolved, and any still open. If nothing in the data indicates a blocker, ask the user whether there were any before writing this section as "No blockers this period" — don't assume none existed.
- **Value Add** — how the work benefited {{CLIENT_NAME}}. Ground this in the actual tasks completed; don't generate generic filler.

---

## Step 4 — Present for confirmation (chat, not artifact)

Before generating the HTML file, show the user in plain chat formatting (headers/lists/tables as normal markdown, no artifact):

- Project name, client name, and month/year
- Draft Summary / Blockers / Value Add text
- Support Overview table (computed)
- Maintenance Overview table (computed)
- Combined S&M task table
- T&M task table (if any)
- Core Framework and Plugin & Package Updates data (if available)
- Scan findings (if available)

Ask the user to confirm before producing the HTML file. Apply any corrections and re-confirm if they make changes.

---

## Step 5 — Compute aggregates

**Support Overview** (one row per Support category with ≥1 task this period; omit zero-task rows):
- `Open`, `In Progress`, `Resolved`, `Deployed` — count of tasks in that category currently in each status
- `Total` — total task count in that category
- `Effort (Hr)` — sum of effort
- Add a **Total** row summing all columns across categories.

**Maintenance Overview** (one row per Maintenance category with ≥1 task this period; omit zero-task rows; no Note column):
- `Frequency` — as provided/confirmed with user
- `Previous` — most recent task date in that category this period
- `Next` — as provided/confirmed with user
- `Effort (Hr)` — sum of effort for that category this period
- Add a **Total** row summing only the `Effort (Hr)` column.

**Support & Maintenance Updates** — every SM task (Support + Maintenance combined), in order: Task ID (`SM1`, `SM2`, …), Description, Status, Priority, Effort (Hr), Date Deployed. Add a **Total** row summing effort.

**Time & Materials Updates** — every TM task: Task ID (`TM1`, `TM2`, …), Description, Status, Priority, Effort (Hr), Date Deployed. Add a **Total** row summing effort. Omit the entire section if there are no T&M tasks.

**Date Deployed column (sections 06 and 10):** show the task's date only when its `status` is `Deployed`. For every other status (`Open`, `In Progress`, `Resolved`), show `-` instead — the column tracks deployment date specifically, not general task date.

**Scan Findings** — for every Maintenance category in the Maintenance Overview whose name contains "Scan" (Security Scan / Uptime Scan / Accessibility Scan), render its own standalone section titled "{{Category}} Findings" (e.g. "Security Scan Findings") with its top 10 findings. There is no overarching "Scan Findings" section — each qualifying category is its own numbered section.
- If findings aren't provided, ask the user for them.
- If the user declines to provide findings for a scan category that's already in the Maintenance Overview table, tell them: "I'd normally leave a scan out of the Maintenance Overview if there are no findings to show for it here — do you want me to include it anyway without findings?" Only proceed without findings if they explicitly confirm.

---

## Step 6 — Core Framework Updates and Plugin & Package Updates sections

1. Look for a `package.json` (or equivalent — `composer.json`, plugin export, etc.) in uploaded files first.
2. If none found, ask the user for the current framework version and a plugin/package list.
3. If the user has nothing to add, **skip both sections** silently — do not render an empty section. They can also be skipped independently (e.g. framework info available but no package list, or vice versa).

When available:
- **Core Framework Updates** — name the current version of the core framework/CMS (WordPress, Node, React, Next.js, Astro, etc.) and state plainly whether it needs updating.
- **Plugin & Package Updates** — table of Package, Installed Version, Latest Version, Status (`Updated` / `Stable` / `Requires Update`).

---

## Step 7 — Generate the HTML file

Use `references/report-template.md`. Key substitutions:

| Placeholder | Value |
|---|---|
| `{{PROJECT_NAME}}` | Project name (HTML-escaped) |
| `{{CLIENT_NAME}}` | Client name, confirmed in Step 1 (HTML-escaped) |
| `{{MONTH_YEAR}}` | E.g. `JUNE 2026` (uppercase, eyebrow) |
| `{{MONTH_YEAR_TITLE}}` | E.g. `June 2026` (title case, footer) |
| `{{SUMMARY_TEXT}}` | Confirmed summary paragraph |
| `{{BLOCKERS_TEXT}}` | Confirmed blockers paragraph |
| `{{VALUE_ADD_TEXT}}` | Confirmed value add paragraph |
| Support Overview rows | Generated from aggregates, zero-task rows omitted |
| Maintenance Overview rows | Generated from aggregates, zero-task rows omitted, no Note column |
| S&M Updates rows + total | Generated from task list; Date Deployed shows `-` unless status is Deployed |
| Core Framework Updates block | Omit entirely if no data |
| Plugin & Package Updates block | Omit entirely if no data |
| Scan Findings sections | One standalone numbered section per qualifying scan category — no overarching label |
| T&M Updates rows + total | Omit entire section if no T&M tasks; same Date Deployed rule as S&M |

**Priority rendering:** High → `font-weight:700; color:#e4022d`. Medium/Low → `font-weight:600; color:#5b6573`.

**Date rendering:** Normalise to `DD Mon YYYY`. If year is missing, use the report year.

**Every effort column header** reads exactly `Effort (Hr)` — Support Overview, Maintenance Overview, S&M Updates, and T&M Updates all use this identical wording.

**Table width:** the card's max-width is generous enough that tables render without a scrollbar on any reasonably sized screen. Every table still sits in a `.table-scroll` wrapper with its own `min-width` as a fallback for narrow viewports only.

**Gmail-safe rendering:** this report is meant to be opened in a browser, copied, and pasted into a Gmail compose window. Gmail's paste sanitizer strips `<style>` blocks and CSS classes, keeping only inline styles. The template already bakes every layout-critical rule (margins on `<h1>`/`<p>`, card width/centering, wrap padding, table-scroll overflow) into inline `style` attributes for exactly this reason — never remove or "clean up" these inline duplicates in favor of the `<style>` block, and if you add new sections, give them the same treatment. See `references/report-template.md` for the full rationale.

---

## Step 8 — Save and present

File naming: `YYYY_MM_DD_HHMM-monthly-report-<project-slug>.html`, timestamped in IST (UTC+5:30).

Where to save depends on where the skill is running:
- **claude.ai** (`/mnt/user-data/outputs/` exists): save there and call `present_files`.
- **Claude Code**: save in the working directory's `reports/` folder (create it if needed). If the working directory is
  the home folder or isn't a project, ask where to save. Then give the user the full path.

Tell the user how to share it: open the file in a browser and print to PDF, or select all, copy and paste into a Gmail
compose window (the inline styles survive the paste).

---

## References

- `references/report-template.md` — Full annotated HTML template with all styling
- `references/category-inference.md` — Rules for inferring Support category and Maintenance category from a task description

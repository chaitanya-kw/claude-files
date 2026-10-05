# planning-sheet

Google Apps Script that turns a Google Sheet into the capacity planning sheet: project budgets, per-person allocations, logged hours from timesheets, and a what-if plan on top. It reads the CSVs that the [`project-snapshot`](../../claude/skills/project-snapshot/) and [`actuals-snapshot`](../../claude/skills/actuals-snapshot/) skills upload to Google Drive, plus the weekly Zoho timesheet xlsx.

The script adds a **Planning** menu with three actions:

| Menu item                     | What it does                                                                                                   |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Set up sheet                  | Creates the tabs and headers it needs. Safe to re-run: it adds what is missing and never overwrites data       |
| Sync allocation               | Loads the newest CSVs and unread timesheets from Drive, then updates the Allocation grid and Summary           |
| Prune gone projects/people…   | Removes project rows and person columns that are no longer in the imports, after showing what will be lost     |

---

## Installation

1. Create a new Google Sheet (or open the one you want to use).
2. **Extensions → Apps Script.** Replace the contents of `Code.gs` with [`allocation_sync.gs`](allocation_sync.gs) and save.
3. In the Apps Script editor: **Services (+) → Drive API → Add.** This is needed to read the timesheet xlsx files.
4. Reload the sheet. A **Planning** menu appears. The first time you run an item, Google asks you to authorise the script.
5. **Planning → Set up sheet.** This creates Summary, Settings, Projects import, Allocations import, Logged import and People, and removes the empty `Sheet1`.
6. On the **Settings** tab, paste the three Drive folder links (or IDs) in column B:

   | setting              | value                                         |
   | -------------------- | --------------------------------------------- |
   | `projects_folder`    | Folder `/project-snapshot` uploads to         |
   | `allocations_folder` | Folder `/actuals-snapshot` uploads to         |
   | `timesheets_folder`  | Folder you upload the weekly timesheet xlsx to |

   On first run the snapshot skills set these folders up and print a tab-separated block. Click **Settings!A2** and paste it; the names land in A2–A4 and the links in B2–B4.
7. On the **People** tab, list the people you plan for: `person_name` (as it appears in the allocations CSV), `person_email`, `monthly_capacity_hrs` and `leave_hr_mgmt_hrs_mtd`. `effective_capacity_hrs` is calculated for you.
8. **Planning → Sync allocation.**

### Sharing with other PMs

Set up a blank copy as a template. **File → Make a copy** duplicates the script and its Drive API setting, so each PM gets their own sheet and Planning menu. Each PM then fills in their own Settings folders and People.

---

## Weekly use

1. Run `/project-snapshot` and `/actuals-snapshot`. They upload their CSVs to the projects and allocations folders.
2. Upload the Monday timesheet xlsx to the timesheets folder. The file name doesn't matter.
3. **Planning → Sync allocation.**

The planning month is in **Summary!D1** (`YYYY-MM`). Change it to plan another month. When it changes, Sync asks before clearing the what-if values.

---

## Tabs

| Tab                  | Written by        | Contents                                                                         |
| -------------------- | ----------------- | -------------------------------------------------------------------------------- |
| Summary              | Setup, Sync       | Planning month (D1) and the capacity check block (C3:D12)                        |
| Settings             | You               | Drive folder links                                                               |
| Allocation           | Sync              | The planning grid (see below)                                                    |
| Projects import      | Sync              | Newest `*_projects.csv` from the projects folder                                 |
| Allocations import   | Sync              | Newest `*_allocations.csv` from the allocations folder                           |
| Logged import        | Sync              | Logged hours per project and person for the planning month, from timesheets      |
| People               | You               | The people you plan for and their capacity                                       |
| `_timesheet_log`     | Sync (hidden)     | Every timesheet entry read so far                                                |
| `_timesheet_files`   | Sync (hidden)     | Every timesheet file read and the dates it covered                               |

"Newest" CSV means the latest by file name; the skills name files with a `YYYY_MM_DD_HHMM` timestamp, so name order is run order. If a folder isn't set on Settings, that tab is left as it is, so you can still paste CSVs by hand.

### Allocation grid

- One row per project, one **Actual | What-if** column pair per person on People, then a totals block (other people, total actual, total what-if, budget, remaining).
- Rows are grouped — other projects, presales, T&M, then projects no longer in the import (`gone`, greyed out) — and sorted alphabetically within each group. Whole rows move, so what-if values stay with their project.
- Under the projects: a totals row, each person's effective capacity, and capacity remaining (red when over).
- New projects and people are inserted; nothing is rebuilt. Rows and columns are keyed by `project_id` and `person_name` in hidden row 1 and column A.

**What-if rule:** a blank What-if cell means "no change" (the Actual value is used). Type `0` to plan someone off a project.

**Actual cells are written by Sync, not formulas.** They only change when you run Sync.

To read planned totals from another tab (person name in A3):

```
What-if total: =INDEX(Allocation!$1:$2000, MATCH("__TOTAL__", Allocation!$A:$A, 0), MATCH($A3, Allocation!$1:$1, 0) + 1)
Actual total:  same formula with + 0 instead of + 1
```

### Summary capacity check

Total capacity, total budget (active projects), capacity − budget, team allocation (actual and what-if, excluding people not on People), spare capacity, hours allocated to people not on People, and active projects with no budget. T&M and presales projects often have no budget, so capacity − budget can look better than it is.

---

## Timesheets

- Each xlsx is read once. The script converts it to a temporary Google Sheet, reads it, then trashes the copy.
- Required columns: `Date` (DD-MM-YYYY), `Project ID`, `Log User Mailid`, `User`, `Hours(For Calculation)`. `Approval Status` is optional; entries containing "reject" are ignored.
- Files are combined by date, not by name: when two files cover the same day, that day comes from the most recent export (from the xlsx metadata, else the Drive upload time).
- Logged hours are matched to projects by `Project ID` → `project_key` on Projects import, and to people by email (People first, then Allocations import, else the timesheet's user name).
- To make Sync re-read a file, delete its row on `_timesheet_files`.

---

## Troubleshooting

| Message                                               | Fix                                                                                                                       |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `stores project_id as a number`                       | `project_id` is an 18-digit number and Sheets rounds it. When pasting a CSV by hand, untick "Convert text to numbers, dates, and formulas", or format the column as Plain text first. Drive imports handle this automatically |
| `needs the Drive API service`                         | Add the Drive API under Services in the Apps Script editor (Installation step 3), then run Sync again                    |
| `has no "<column>" column`                            | A tab or timesheet is missing a required header. Run Set up sheet, or check the xlsx export                              |
| `effective_capacity_hrs on People was not changed`    | Some typed capacities differ from monthly − deductions. Move the difference into `leave_hr_mgmt_hrs_mtd`, clear `effective_capacity_hrs` below the header, and Sync again |
| `named from the timesheet`                            | Add `person_email` on People so timesheet rows match the right person                                                     |
| Dates "may have day and month swapped"                | The xlsx stored dates as dates rather than DD-MM-YYYY text. Check them against the file                                   |

# snm-tnm-monthly-report-generator

Generates a branded Kilowott monthly client report as a self-contained HTML file, combining S&M (Support & Maintenance) and T&M (Time & Materials) sections.

## What it does

- Accepts task lists in any format (inline bullet list, markdown table, or CSV)
- Infers missing task categories from description keywords
- Computes per-section totals and S&M category breakdown
- Produces a print-ready HTML file matching the Kilowott report template

## Trigger phrases

Only triggers when the request explicitly references an S&M or T&M project:

- "generate the S&M report"
- "create the T&M report for June"
- "build the S&M/T&M report for [month]"
- "turn this S&M task list into a report"

Does **not** trigger for general monthly summaries, plain-text reports, internal status updates, or reports for projects that are not explicitly S&M or T&M.

## Inputs

| Field | Required | Notes |
|---|---|---|
| Client / project name | Yes | Appears in the report title |
| Month + year | Yes | e.g. "June 2026" |
| S&M task list | Yes | See formats below |
| T&M task list | No | Omit the T&M section entirely if empty |

### Accepted task list formats

```
# Inline bullets
- Fixed iOS PDF viewer issue (High, 2hr, completed 08/06, Enhancement)

# Markdown table
| Description | Priority | Effort | Date | Category |
|---|---|---|---|---|
| Fixed iOS PDF | High | 2 | 08/06 | Functional Bugs |

# CSV
description,priority,effort_hr,date,category
Fixed iOS PDF,High,2,08/06,Functional Bugs
```

**Required task fields:** `description`, `priority` (High/Medium/Low), `effort_hr`, `date`, `category`

- `category` is auto-inferred from the description if missing (see `references/category-inference.md`)
- `status` defaults to "Completed" if not provided
- `section` defaults to SM if not specified

## Output

A file named `YYYY_MM_DD_HHMM-monthly-report-<client-slug>.html` saved to `/mnt/user-data/outputs/` and presented via `present_files`.

## Install

```bash
mkdir -p ~/.claude/skills/snm-tnm-monthly-report-generator
# Unzip the .skill archive and copy SKILL.md
unzip snm-tnm-monthly-report-generator.skill -d /tmp/skill_extracted/
cp /tmp/skill_extracted/snm-tnm-monthly-report-generator/SKILL.md ~/.claude/skills/snm-tnm-monthly-report-generator/
cp -r /tmp/skill_extracted/snm-tnm-monthly-report-generator/references ~/.claude/skills/snm-tnm-monthly-report-generator/
```

## References

- `references/report-template.md` — annotated HTML template with all inline styling
- `references/category-inference.md` — keyword rules for auto-inferring task category

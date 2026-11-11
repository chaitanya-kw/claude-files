---
name: timesheet-summary
description: Write one short summary per working day (under 500 characters each) for the user's timesheet, covering a date range they give. Combines Google Calendar meetings, Claude Code session transcripts from every project folder, and any off-Claude work the user lists. Use when the user asks for timesheet summaries, daily work summaries, or "what did I do" for a date range.
---

# Timesheet summary

Gives the user one paste-ready summary per working day in a date range.

## Inputs

- **Date range** (required). Accept any form ("last week", "3–7 Nov") and turn it into explicit start and end dates. If the user gives no range, ask for one.
- **Other work** (optional): anything done outside Claude Code and the calendar, e.g. "Thu 2h code review for X". Put it in the right day's summary.

Working days are Monday to Friday. Skip weekends unless the sessions or calendar show work on them; if they do, ask whether to include those days.

## Steps

### 1. Calendar

Call `mcp__claude_ai_Google_Calendar__list_events` on the primary calendar with `startTime` = start date `T00:00:00`, `endTime` = the day after the end date `T00:00:00`, `orderBy: startTime`, `pageSize: 250`. Follow `nextPageToken` if one is returned. If the calendar tools fail or need auth, tell the user and ask them to reconnect the Google Calendar connector. Don't go on without the calendar unless they say to.

For each event, use your own attendee entry (`self: true`):
- `declined`: leave the event out.
- `needsAction` or `tentative`: include it, but list it in the "check" notes at the end.
- "On Leave" events and `OUT_OF_OFFICE` events: compare them with that day's session activity. If sessions or accepted meetings fall inside the leave window, flag the conflict.
- Leave out the recurring `FOCUS_TIME` block "Zoho, minutes, hours" (daily admin), unless the user asks for it.

Use meeting titles only. Never copy attendee emails, phone numbers, or Meet links into the output.

### 2. Claude Code sessions

```bash
python3 -I ~/.claude/skills/timesheet-summary/scripts/extract_sessions.py START END
```

This prints each day's user prompts with time, project folder and session ID. Long ranges produce a lot of output: redirect it to `/tmp/timesheet/prompts.txt` and read it in parts.

The prompts show what was asked, not always what got done. If what came out of a session is unclear and matters to the summary (was the PR raised? was the bug fixed?), read Claude's replies for that session:

```bash
python3 -I ~/.claude/skills/timesheet-summary/scripts/extract_sessions.py START END --session <8-char id>
```

Group the work by client/project. The project folder usually shows the client (`projects/norisma`, `projects/bomann`, `projects/prismatch`, `projects/bcomp`); the prompt text sometimes shows another (e.g. Betakaroten work run from the Norisma folder).

### 3. Write the summaries

One summary per working day, **under 500 characters including spaces**. Format:

1. Meetings first, as a comma-separated list of short titles ("Bomann and Norisma standups, Prismatch weekly call").
2. Then the work, grouped by client: `Norisma: did X; did Y. Bomann: did Z.`
3. Then any off-Claude work the user gave for that day.

Style:
- Past tense, outcome-focused verbs: built, fixed, reviewed, set up, raised PR, wrote, diagnosed.
- Name deliverables (report, PR, runbook, plan), not the back-and-forth.
- Leave out trivial prompts (session housekeeping, approvals, "close this session", tooling/config questions about Claude Code itself).
- **No customer PII**: no end-customer names, emails, order data, or credentials. Client company names and project names are fine. Avoid naming client staff; colleague names aren't needed either.
- If a day is over 500 characters, merge or drop the smallest items until it fits.

### 4. Check lengths and save

Write the summaries to `timesheet-summaries-START-to-END.md` in the current working directory (`## Day D Mon` heading, then the paragraph). Check the lengths:

```bash
awk '/^## /{if(t!="")print h": "length(t);h=$0;t="";next} NF{t=t $0} END{print h": "length(t)}' FILE
```

Fix any summary that is 500 or over.

### 5. Reply

Give the summaries in the chat as **plain text**: the day label on its own line, then the paragraph, then a blank line. No tables, code blocks, headings, bullets or bold, so the user can copy them straight into the timesheet.

After the summaries, add a short "Check before submitting" list covering only what applies: leave/activity conflicts, meetings you never replied to, days with no data, and anything left out on purpose.

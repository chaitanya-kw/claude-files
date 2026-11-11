# timesheet-summary

Writes one short summary per working day for your timesheet, covering a date range you give. Each summary is under
500 characters and is returned as plain text, ready to paste.

## Sources

- **Google Calendar**: meetings in the range. Meetings you declined are left out. Meetings you never replied to,
  and leave blocks that overlap with work, are flagged. The daily "Zoho, minutes, hours" focus block is left out.
- **Claude Code sessions**: `scripts/extract_sessions.py` reads the session transcripts in
  `~/.claude/projects/` (all project folders) and lists your prompts per day. With `--session <id>` it also prints
  Claude's replies, to confirm what got done.
- **Your input**: any work done outside Claude Code and the calendar, added to the right day.

## Output

- One paragraph per working day: meetings first, then work grouped by client, then your extra items.
- Saved to `timesheet-summaries-START-to-END.md` in the current directory and also given in chat as plain text
  (no tables or formatting).
- A short "Check before submitting" list: leave conflicts, meetings you never replied to, days with no data.
- No customer PII: no end-customer names, emails, order data or meeting links.

## Requirements

- Claude Code with the Google Calendar connector (claude.ai) connected.
- Python 3 (standard library only).

## Install

```bash
cp -r claude/skills/timesheet-summary ~/.claude/skills/
```

## Usage

- `/timesheet-summary 3–7 Nov`
- "Timesheet summaries for last week. Also Thu 2h code review for X."

## Script

```bash
python3 -I scripts/extract_sessions.py 2026-11-03 2026-11-07                 # prompts per day
python3 -I scripts/extract_sessions.py 2026-11-03 2026-11-07 --session 81feddb6  # plus Claude's replies
```

Dates are inclusive and use local time.

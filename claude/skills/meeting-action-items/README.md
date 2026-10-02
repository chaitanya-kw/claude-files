# meeting-action-items

A Claude Code skill that processes meeting transcripts and automatically creates action items as tasks in Asana.

---

## Installation

```bash
mkdir -p ~/.claude/skills/meeting-action-items
cp claude/skills/meeting-action-items/SKILL.md ~/.claude/skills/meeting-action-items/
```

Requires the Asana MCP connector to be configured in Claude Code.

**Before first use:** edit `SKILL.md` and replace the placeholder GIDs:
- `YOUR_USER_GID` — your Asana user GID
- `YOUR_INBOX_PROJECT_GID` — the GID of your Asana Inbox project
- `YOUR_WORKSPACE_GID` — your Asana workspace GID

---

## Usage

Trigger by uploading or pasting a meeting transcript and asking:

```
process these meeting notes
extract action items from this transcript
create Asana tasks from my meeting
```

Claude Code will:

1. Read the transcript and identify action items — explicit assignments, commitments, deliverables, and follow-ups
2. Extract assignee, recipient, deadline, project context, and a clear action description for each
3. Create one Asana task per action item in your Inbox project
4. Print a summary of all tasks created with a link to your Inbox

### Task creation rules

- One task per action item — no combining
- Tasks land in your Asana Inbox for you to triage
- Due dates and custom fields are never set — only name, notes, assignee, project, and workspace

### Output

```
✅ Created X tasks in your Asana Inbox
🔗 View tasks: https://app.asana.com/0/<YOUR_INBOX_PROJECT_GID>

Tasks created:
- [Task title 1]
- [Task title 2]
```

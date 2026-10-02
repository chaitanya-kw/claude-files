---
name: meeting-action-items
description: Process meeting transcripts and automatically create action items as Asana tasks. Use this skill when the user uploads a meeting transcript, discussion notes, or recorded conversation and asks to extract action items, create tasks, or add items to Asana. Also trigger when user asks to "process meeting notes" or "create tasks from meeting".
---

# Meeting Action Items Skill

Process meeting transcripts to identify and create action items as Asana tasks in the user's Inbox project.

## Quick Start

1. Read `references/asana_config.md` for Asana configuration
2. Analyze transcript to identify action items
3. Extract required information for each action item
4. Create tasks using Asana connector
5. Provide completion summary

## Action Item Identification

Extract action items from transcripts by looking for:

- Explicit task assignments ("Can you...", "Please...", "You should...")
- Commitments made during discussion ("I'll...", "We'll...")
- Deliverables mentioned ("Send...", "Prepare...", "Review...")
- Follow-up actions required
- Promises or agreements made

**Important:** Extract even if not explicitly labeled as "action items". Focus on deliverables and concrete actions, not discussions or decisions.

## Information Extraction

For each action item, extract:

1. **Assignee:** Who is responsible
   - If ambiguous, default to yourself (GID: YOUR_USER_GID)
2. **Recipient:** Who receives the deliverable (if applicable)
3. **Deadline:** When mentioned in discussion (write "Not specified" if none)
4. **Project:** Related project or client context (if applicable)
5. **Action:** Clear, actionable description of what needs to be done

## Task Creation

### Asana Parameters

Use `Asana:asana_create_task` with these exact parameters:

**Required:**
- `name`: Short action-oriented title (verb + object)
- `notes`: Formatted description (see format in `references/asana_config.md`)
- `assignee`: "YOUR_USER_GID"
- `project_id`: "YOUR_INBOX_PROJECT_GID"
- `workspace`: "YOUR_WORKSPACE_GID"

**Prohibited (NEVER include):**
- `due_on`, `due_at`
- `custom_fields`
- Priority or flag fields

### Task Granularity

Create **one task per action item**. Do not combine multiple actions into a single task.

## Example

**Transcript excerpt:**
> "[Name], can you send the deployment timeline to [Recipient] by Friday? We need to include the staging and production dates for the [Project Name] project."

**Create task:**
```
name: "Send deployment timeline to client"
notes: "Action item from meeting: Weekly [Project Name] Sync

Assignee: [Your Name]
Recipient: [Recipient Name]
Deadline: Friday (mentioned in meeting)
Project: [Project Name]

Prepare and send updated deployment timeline including staging and production dates."
assignee: "YOUR_USER_GID"
project_id: "YOUR_INBOX_PROJECT_GID"
workspace: "YOUR_WORKSPACE_GID"
```

## Completion Summary

After creating all tasks, provide:

```
✅ Created [X] tasks in your Asana Inbox
🔗 View tasks: https://app.asana.com/0/YOUR_INBOX_PROJECT_GID

Tasks created:
- [Task title 1]
- [Task title 2]
- [Task title 3]
```

**Do NOT:**
- Explain the extraction process in detail
- Repeat the task descriptions you created
- Ask if user wants to modify tasks (they're in Inbox for user to process)

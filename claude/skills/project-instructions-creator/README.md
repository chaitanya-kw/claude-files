# project-instructions-creator

A Claude Code skill that interviews you and produces ready-to-paste Claude Project instructions tailored to a specific engagement.

---

## Installation

```bash
mkdir -p ~/.claude/skills/project-instructions-creator
cp claude/skills/project-instructions-creator/SKILL.md ~/.claude/skills/project-instructions-creator/
```

No dependencies.

---

## Usage

Trigger from any Claude Code session:

```
create project instructions
set up a new Claude project
I'm starting a new project
help me configure a Claude project
```

Claude Code will run a structured interview across three stages, then generate instructions.

### Interview stages

1. **Project identity** — name, client vs internal, your role, domain
2. **Work context** — task types (planning, code, writing, etc.), platforms, deliverable formats, milestones
3. **Claude behaviour** — output format rules, persona, topics requiring check-in, reference documents

If you have an existing brief, SOW, or SRS, share it at the start — Claude will extract what it can and only ask follow-up questions for the gaps.

### Output

A single fenced markdown block ready to paste into the Claude Project instructions field. Sections included:

- **Project context** — what it is, client/internal, your role, domain
- **Tech stack / platforms** — only if relevant
- **Your tasks in this project** — confirmed work types
- **Output rules** — format defaults plus any project-specific rules
- **Behaviour rules** — constraints, persona, mandatory check-in topics
- **Key reference points** — critical facts extracted from any documents shared (only if documents were provided)

Generic boilerplate is omitted. Every line is specific to your project.

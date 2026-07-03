#!/usr/bin/env bash
set -euo pipefail

# Duplicates a GitHub ProjectV2 (fields + workflows) to a new owner.
# The source project is hardcoded (chaitanya-kw personal, project #2).
# Uses copyProjectV2 which copies all custom fields, views, and workflows.
# Note: GitHub's API does not expose a mutation to toggle workflow enabled state;
#       all workflows are enabled by default on a fresh copy, which matches the source.
#
# Usage:
#   ./duplicate-github-project.sh --owner <org-or-user> --title "New Project Name"
#   ./duplicate-github-project.sh --owner myorg --title "Q3 Board"
#   ./duplicate-github-project.sh --owner my-username --title "Personal Board" --user

SOURCE_USER="chaitanya-kw"
SOURCE_PROJECT_NUMBER=2

OWNER=""
TITLE=""
OWNER_TYPE="org"   # "org" or "user"

usage() {
  echo "Usage: $0 --owner <org-or-username> --title <title> [--user]"
  echo ""
  echo "  --owner   Target org or username to own the new project"
  echo "  --title   Title for the new project"
  echo "  --user    Treat --owner as a personal user account (default: org)"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --owner) OWNER="$2"; shift 2 ;;
    --title) TITLE="$2"; shift 2 ;;
    --user)  OWNER_TYPE="user"; shift ;;
    --help|-h) usage ;;
    *) echo "Unknown argument: $1"; usage ;;
  esac
done

[[ -z "$OWNER" ]] && { echo "Error: --owner is required"; usage; }
[[ -z "$TITLE" ]] && { echo "Error: --title is required"; usage; }

echo "Source:  $SOURCE_USER / project #$SOURCE_PROJECT_NUMBER"
echo "Target:  $OWNER ($OWNER_TYPE) / \"$TITLE\""
echo ""

# --- 1. Resolve source project ID ---
echo "Fetching source project ID..."
SOURCE_PROJECT_ID=$(gh api graphql -f query="
{
  user(login: \"$SOURCE_USER\") {
    projectV2(number: $SOURCE_PROJECT_NUMBER) { id }
  }
}" --jq '.data.user.projectV2.id')

echo "  Source project ID: $SOURCE_PROJECT_ID"

# --- 2. Resolve target owner ID ---
echo "Fetching target owner ID..."
if [[ "$OWNER_TYPE" == "user" ]]; then
  OWNER_ID=$(gh api graphql -f query="{ user(login: \"$OWNER\") { id } }" \
    --jq '.data.user.id')
else
  OWNER_ID=$(gh api graphql -f query="{ organization(login: \"$OWNER\") { id } }" \
    --jq '.data.organization.id')
fi

echo "  Owner ID: $OWNER_ID"

# --- 3. Copy the project ---
# copyProjectV2 duplicates all custom fields, views, and workflows from the source.
echo "Copying project..."
NEW_PROJECT=$(gh api graphql -f query="
mutation {
  copyProjectV2(input: {
    projectId: \"$SOURCE_PROJECT_ID\"
    ownerId: \"$OWNER_ID\"
    title: \"$TITLE\"
    includeDraftIssues: false
  }) {
    projectV2 {
      id
      number
      url
      workflows(first: 20) {
        nodes { name enabled }
      }
    }
  }
}")

NEW_PROJECT_URL=$(echo "$NEW_PROJECT" | jq -r '.data.copyProjectV2.projectV2.url')
NEW_PROJECT_NUMBER=$(echo "$NEW_PROJECT" | jq -r '.data.copyProjectV2.projectV2.number')
WORKFLOWS=$(echo "$NEW_PROJECT" | jq -r '.data.copyProjectV2.projectV2.workflows.nodes')

echo ""
echo "Done. New project #$NEW_PROJECT_NUMBER: $NEW_PROJECT_URL"
echo ""
echo "Workflows:"
echo "$WORKFLOWS" | jq -r '.[] | "  [\(if .enabled then "enabled" else "disabled" end)] \(.name)"'

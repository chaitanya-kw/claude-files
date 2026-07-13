#!/bin/bash

# -----------------------------------------------
# Configuration — edit these values before running
# -----------------------------------------------
export GH_TOKEN="<your-PAT>"
export GH_PAGER=""

OWNER="org-or-name"       # org name or personal account username
OWNER_TYPE="org"              # "org" or "user"
PROJECT_NUMBER=2
REPOS=(
  "repo-1"
  "repo-2"
)
# -----------------------------------------------

# Resolve project node ID based on owner type
if [ "$OWNER_TYPE" = "org" ]; then
  PROJECT_ID=$(gh api graphql -f query='
    query($owner: String!, $number: Int!) {
      organization(login: $owner) {
        projectV2(number: $number) { id }
      }
    }' -f owner="$OWNER" -F number="$PROJECT_NUMBER" \
    --jq '.data.organization.projectV2.id')
else
  PROJECT_ID=$(gh api graphql -f query='
    query($owner: String!, $number: Int!) {
      user(login: $owner) {
        projectV2(number: $number) { id }
      }
    }' -f owner="$OWNER" -F number="$PROJECT_NUMBER" \
    --jq '.data.user.projectV2.id')
fi

if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "null" ]; then
  echo "Error: could not resolve project ID. Check OWNER, OWNER_TYPE, and PROJECT_NUMBER."
  exit 1
fi

echo "Project ID: $PROJECT_ID"

add_item() {
  local REPO="$1" KIND="$2" NUMBER="$3" API_PATH="$4"
  NODE_ID=$(gh api "$API_PATH" --jq '.node_id')
  if [ -z "$NODE_ID" ] || [ "$NODE_ID" = "null" ]; then
    echo "  Skipping $KIND #$NUMBER — could not resolve node ID."
    return
  fi
  RESULT=$(gh api graphql -f query='
    mutation($project: ID!, $item: ID!) {
      addProjectV2ItemById(input: {projectId: $project, contentId: $item}) {
        item { id }
      }
    }' -f project="$PROJECT_ID" -f item="$NODE_ID" \
    --jq '.data.addProjectV2ItemById.item.id')
  echo "  Added $KIND #$NUMBER (item: $RESULT)"
}

# Add all issues and PRs from each repo
for REPO in "${REPOS[@]}"; do
  echo "Adding issues from $REPO..."
  gh issue list --repo "$OWNER/$REPO" --state all --limit 1000 --json number --jq '.[].number' | while read ISSUE_NUMBER; do
    add_item "$REPO" "issue" "$ISSUE_NUMBER" "/repos/$OWNER/$REPO/issues/$ISSUE_NUMBER"
  done

  echo "Adding pull requests from $REPO..."
  gh pr list --repo "$OWNER/$REPO" --state all --limit 1000 --json number --jq '.[].number' | while read PR_NUMBER; do
    add_item "$REPO" "PR" "$PR_NUMBER" "/repos/$OWNER/$REPO/pulls/$PR_NUMBER"
  done

  echo "Done with $REPO."
done

echo "Backfill complete."

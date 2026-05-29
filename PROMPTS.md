# PROMPTS.md

## First work session prompt

Use this after opening the repo in Codex.

```text
Continue the FPL retrospective project.

Before doing anything, read:
- AGENTS.md
- PLANS.md
- BACKLOG.md
- KANBAN.md
- SPRINTS.md
- STATUS.md
- TESTING.md

Then:
1. Confirm there is no story already In Progress.
2. Select the next Ready story from the current sprint.
3. Move it to In Progress in KANBAN.md and STATUS.md.
4. Break the story into tasks inside BACKLOG.md.
5. Implement only that story.
6. Run the relevant checks.
7. Update BACKLOG.md task checkboxes.
8. Move the story to In Review if complete.
9. Update KANBAN.md Epic Progress and Sprint Progress.
10. Update STATUS.md.
11. Update DECISION_LOG.md if a meaningful design choice was made.
12. Stop and summarise:
   - story worked on
   - files changed
   - checks run
   - outputs created
   - current board status
   - risks or blockers
   - recommended next action
```

## Continue within current sprint prompt

```text
Continue within the current sprint only.

Read:
- AGENTS.md
- BACKLOG.md
- KANBAN.md
- SPRINTS.md
- STATUS.md
- TESTING.md

Work on the next Ready story only.

Do not start the next sprint.

Stop after completing or blocking the story.
```

## Human review prompt

```text
Review the story currently marked In Review.

Read:
- BACKLOG.md
- KANBAN.md
- STATUS.md
- TESTING.md
- code_review.md

Check whether the story satisfies its acceptance criteria and Definition of Done.

Do not implement new features.

Report:
1. Pass/fail recommendation
2. Acceptance criteria status
3. Checks run
4. Issues found
5. Suggested fixes
6. Whether the story can move to Done
```

## Move story to Done prompt

```text
The story in review has passed human review.

Move it from In Review to Done in:
- BACKLOG.md
- KANBAN.md
- STATUS.md

Update:
- Sprint Progress
- Epic Progress
- Completed stories
- Next ready story

Do not implement code.
```

## Create next sprint prompt

```text
Prepare the next sprint.

Read:
- PLANS.md
- BACKLOG.md
- KANBAN.md
- SPRINTS.md
- STATUS.md

Identify the next logical sprint based on dependencies.

Move only the appropriate stories to Ready.

Update:
- SPRINTS.md
- KANBAN.md
- STATUS.md

Do not implement code.
```

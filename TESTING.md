# TESTING.md

## Testing philosophy

Every story must have evidence that it works.

The project does not need heavy formal unit testing at the start, but each story must include lightweight validation checks.

## Required checks by area

### API and cache

- Check response status.
- Check JSON is saved.
- Check cached JSON can be reloaded.
- Check expected top-level keys exist.

### DataFrames

- Print shape.
- Check expected columns exist.
- Check key columns are not fully null.
- Check duplicate keys where uniqueness is expected.

### Gameweek data

- Check gameweeks present.
- Check row counts look plausible.
- Check player IDs join to player metadata.

### Manager data

- Check manager ID is present.
- Check gameweek range is present.
- Check picks usually have 15 rows per manager per gameweek.
- Check each manager-gameweek has one captain and one vice-captain where data exists.

### Leakage checks

For features before gameweek `t`:

- Rolling features must use only gameweeks less than `t`.
- Team strength must use only fixtures before `t`.
- Current gameweek points must not appear in pre-gameweek features.

### Sampling checks

- Check rank bands.
- Check sample counts by band.
- Check min, median, and max rank.
- Warn if any rank band has fewer than 30 managers.

### Notebook checks

- Notebook section exists.
- Notebook cells run in order through completed sections.
- Notebook remains readable.
- Complex reusable code is moved to `src/fpl_retro/`.

## Completion rule

A story is not Done unless:

1. Code is implemented.
2. Relevant checks have been run.
3. Outputs are saved where required.
4. `STATUS.md` is updated.
5. `KANBAN.md` is updated.
6. Any important design choice is captured in `DECISION_LOG.md`.

# FPL Retrospective Codex Starter

This repo is a starter kit for building an FPL season retrospective notebook with Codex.

## Objective

Build a Jupyter Notebook and supporting Python modules that analyse FPL manager team ID `816200`, compare that manager against a representative rank-stratified sample of top-N overall managers, and generate evidence-based rules for next season.

## How to use this repo with Codex

1. Unzip this folder.
2. Open it as a project in Codex.
3. Ask Codex to read:
   - `AGENTS.md`
   - `PLANS.md`
   - `BACKLOG.md`
   - `KANBAN.md`
   - `SPRINTS.md`
   - `STATUS.md`
   - `TESTING.md`
4. Give Codex the prompt in `PROMPTS.md` under **First work session prompt**.
5. Let it work one story at a time.

## Main files

| File | Purpose |
|---|---|
| `AGENTS.md` | Permanent operating instructions for Codex |
| `PLANS.md` | End-to-end project plan and epic roadmap |
| `BACKLOG.md` | Story cards, tasks, acceptance criteria, checks |
| `KANBAN.md` | Lightweight story-level board |
| `SPRINTS.md` | Sprint grouping and review checkpoints |
| `STATUS.md` | Current project state |
| `TESTING.md` | Validation rules |
| `DECISION_LOG.md` | Design decision history |
| `PROMPTS.md` | Prompts to give Codex |
| `notebooks/fpl_season_retrospective.ipynb` | Starting notebook |
| `src/fpl_retro/` | Python helper modules |

## Important principle

The notebook should be the readable analysis/report layer. Reusable logic should live in `src/fpl_retro/`.

Generated on 2026-05-28.

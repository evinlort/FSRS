# AGENTS.md

## Project purpose
Build a small, maintainable Flask MVP for learning Czech vocabulary from CSV using FSRS-based scheduling.

## Instruction priority
Read and follow, in this order:
1. this file
2. docs/FSRS_SCOPE.md
3. PLANS/MAIN_PLAN.md
4. the current step file in PLANS/

## Planning rule
For any non-trivial feature, refactor, or architecture change:
- do planning first
- use PLANS/MAIN_PLAN.md as the ordered checklist
- create one markdown file per atomic step in PLANS/
- each step must solve exactly one problem

## Delivery rule
When implementing:
- work on exactly one atomic step at a time
- prefer small diffs
- keep files short and focused
- avoid speculative abstractions

## Tech stack
- Python 3.14
- Flask
- Jinja templates
- SQLite
- pytest
- uv
- pyproject.toml

## Architecture rules
Use a structured layout. Keep responsibilities separate.

Preferred modules:
- `src/<app_name>/web/` for Flask routes, forms, request handlers
- `src/<app_name>/domain/` for core models and scheduling logic
- `src/<app_name>/services/` for application services
- `src/<app_name>/repositories/` for persistence
- `src/<app_name>/importers/` for CSV parsing/import
- `tests/` for tests

Do not put all logic in one file.
No module over 250 lines without a strong reason.
No function over 40 lines without a strong reason.

## FSRS scope
MVP includes:
- scheduler only
- default parameters
- desired retention default 0.90
- grades: Again, Hard, Good, Easy
- persistent review history

MVP excludes:
- optimizer
- advanced analytics
- multi-user support
- background jobs
- cloud sync

## CSV rules
CSV structure may change over time.
Parse by header names, not by column index.
Accept aliases where practical.
Require logical fields for Czech word and Russian translation.
Treat notes and unknown extra columns as optional metadata.
Ignore unsupported columns safely.

## TDD rules
Use TDD for behavior-level work:
1. write a failing test
2. implement the smallest passing change
3. refactor
4. rerun relevant tests

Do not write meaningless tests for trivial scaffolding.

## Verification
Before declaring a step done:
- run the relevant tests
- run any formatter/linter/type checks already configured in the repo
- verify the changed behavior matches the step description

## Git rule
After completing a step:
- create one clear commit if the environment allows it
- otherwise provide the exact commit message that should be used

## Response style
Be concise.
State assumptions explicitly.
Do not claim work is done without naming the verification performed.
For UI work, name whether pytest, Playwright MCP, and Chrome DevTools MCP were used or skipped.

## UI/UX rules
- UI phase may include backend/data changes only when required by the approved UI planning
- Implement exactly one step at a time
- Do not skip tests
- Use Playwright/DevTools MCP only on major UI milestones
- No SPA unless explicitly required

## Commands
Use the real repository commands when available.

Preferred verification order:
1. run targeted tests first
2. run broader relevant tests
3. run configured format/lint/type checks
4. for major UI milestones, run browser verification with Playwright MCP and/or Chrome DevTools MCP if available

If a command is missing or unclear, inspect the repository and use the existing project convention.
Do not invent commands.

## Instruction scope note
The priority list in this file is a project working rule.
Codex may also load more specific AGENTS.md files from deeper directories when they exist.

## UI verification rule
For major UI milestones:
- verify server-rendered behavior with pytest first
- then use Playwright MCP for end-user flow checks when possible
- then use Chrome DevTools MCP for console, network, and responsive checks when useful
- if MCP/browser verification is unavailable in the environment, state that explicitly and do not pretend it was performed

## UI/backend change boundary
Backend or data-model changes are allowed during UI work only when:
- they are required by the approved current UI step, or
- they are an explicit dependency of that approved step

Do not pull future backend work into the current step.



# Git Rules — Commits, Branches, PRs

## Commit Messages

Follow the Conventional Commits spec: `<type>(<scope>): <short description>`

| Type | When to use |
|------|-------------|
| `feat` | New feature or behaviour |
| `fix` | Bug fix |
| `refactor` | Code change with no behaviour change |
| `docs` | Documentation only |
| `chore` | Build, config, dependency updates |
| `test` | Adding or fixing tests |

**Examples:**
```
feat(agents): add display_agent formatting for chart data
fix(streaming): abort fetch on component unmount
refactor(state): rename stream_chunks to token_chunks
docs(rules): add ai-agents best practices
chore(deps): pin langgraph to 0.2.28
```

Rules:
- Subject line ≤ 72 characters, imperative mood, no trailing period.
- Body (optional) explains *why*, not *what*. Wrap at 100 characters.
- Reference issues: `Closes #12`, `Refs #34`.

## Branches

```
main          ← stable, always runnable
feat/<topic>  ← new features
fix/<topic>   ← bug fixes
chore/<topic> ← tooling / config
```

- Branch from `main`. Rebase onto `main` before opening a PR.
- Delete branches after merging.
- Never commit directly to `main`.

## Pull Requests

- PR title follows the same Conventional Commits format as the commit message.
- Description must include:
  - **What** changed and **why**.
  - **How to test** it locally.
  - Screenshots / terminal output for UI or streaming changes.
- Keep PRs small and focused. One concern per PR.
- Self-review before requesting review: run lint, confirm the three services start correctly.

## What Never Goes in Git

- `.env` files or any file containing secrets, tokens, or passwords.
- `__pycache__/`, `*.pyc`, `.venv/` (add to `.gitignore` if missing).
- `node_modules/`, `.next/` (should already be in `.gitignore`).
- Large binary files or model weights.

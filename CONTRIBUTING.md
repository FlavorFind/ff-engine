# Contributing to ff-engine

## Who can contribute

All contributions go through pull requests. Direct pushes to `main` are blocked
for everyone including owners.

---

## Branching

| Branch type | Pattern | Example |
|-------------|---------|---------|
| Build step | `eN/short-description` | `e3/django-project-skeleton` |
| Bug fix | `fix/short-description` | `fix/scorer-tie-break` |
| Data change | `data/short-description` | `data/seed-coastal-dishes` |
| Infrastructure | `infra/short-description` | `infra/caddy-tls-config` |
| Documentation | `docs/short-description` | `docs/api-v1-guide` |

Rules:
- Branches are short-lived. Open a PR within a day or two of starting.
- Delete the branch after the PR is merged.
- Never commit directly to `main`.

---

## Commit messages

We use [Conventional Commits](https://www.conventionalcommits.org/).

```
<type>(<scope>): <short summary>

[optional body]

[optional footer]
```

Types: `feat`, `fix`, `data`, `test`, `docs`, `refactor`, `ci`, `chore`

Examples:
```
feat(search): add explore mode to matching pipeline
fix(resolver): handle ambiguous unga alias correctly
data(dishes): seed 20 coastal dishes batch 1
test(scorer): add golden set cases for dietary filters
docs(api): document /v1/search/by-ingredients response shape
```

Rules:
- Summary is lowercase, no full stop, under 72 characters.
- Body explains *why*, not *what* (the diff shows the what).
- Reference the build step or issue: `Closes #12` or `Build step E4`.
- Commits must be signed (SSH or GPG).

---

## Pull requests

1. Open a PR from your feature branch into `main`.
2. Fill in the PR template completely.
3. CI must be green before requesting review.
4. At least 1 approval required (2 once the team exceeds 3 developers).
5. All review comments must be resolved.
6. Squash merge only — one clean commit per PR on `main`.

---

## Definition of done

A build step is **done** when:

- [ ] Code is reviewed and approved
- [ ] All tests are written and passing
- [ ] No ruff or mypy errors
- [ ] Migrations are reversible (if applicable)
- [ ] Docs updated (API docs, runbook, ADR where needed)
- [ ] Deployed to staging and smoke-tested
- [ ] Demoed (not done on one laptop)

For data changes, additionally:
- [ ] Reviewer has checked authenticity, names, roles and source
- [ ] QA report has no new critical issues

---

## Code style

- Formatter and linter: **ruff** (configured in `pyproject.toml`)
- Type checker: **mypy** (gradual; new code must be typed)
- Run `make lint` and `make typecheck` before pushing
- Pre-commit hooks enforce style automatically on commit

---

## Data changes

Data lives in `data/seed/` as CSV files. All changes go through a PR with the
`data/` prefix. The data lead must approve all data PRs.

Never edit the database directly. All changes go through the curation workflow
(Django admin → draft → reviewed → verified → released).

---

## Security

- Never commit secrets, `.env` files, keys or passwords.
- `detect-private-key` pre-commit hook will block you if you try.
- If you accidentally commit a secret, rotate it immediately and notify the
  security reviewer. Do not just delete the file — the secret is in git history.

---

## Questions

Open a GitHub Discussion or ask in the team channel.

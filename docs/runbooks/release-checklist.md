# Release Checklist — Flavor Find Engine

Use this checklist before every production release.

---

## Pre-release

- [ ] All CI checks green on the release branch
- [ ] `python manage.py qa_report --fail-on-critical` exits 0
- [ ] `python manage.py run_golden_set` passes ≥ 95% (≥ 190/200 cases)
- [ ] Migration plan reviewed — can all new migrations be reversed cleanly?
- [ ] `DATASET_VERSION` and `ENGINE_VERSION` env vars updated in Render dashboard
- [ ] Release notes written in `CHANGELOG.md`
- [ ] Backup taken from current production state:
      `python manage.py backup_drill --step backup`
- [ ] Backup verified: `python manage.py backup_drill --step verify --snapshot-dir <path>`

## Deploy

- [ ] PR squash-merged to `main`
- [ ] Render auto-deploy triggered (or manual deploy initiated)
- [ ] Health check passes within 3 min:
      `curl https://ff-engine-kuar.onrender.com/v1/health/`

## Post-deploy verification

- [ ] Golden set passing on staging: `python manage.py run_golden_set`
- [ ] Sample search request returns results:
      ```bash
      curl -X POST https://ff-engine-kuar.onrender.com/v1/search/by-ingredients \
        -H "X-API-Key: $FF_API_KEY" \
        -H "Content-Type: application/json" \
        -d '{"ingredients": ["tomato", "onion", "beef"]}'
      ```
- [ ] Admin login works (2FA)
- [ ] No new errors in Render logs

## If anything fails

1. Do not panic.
2. Run: `python manage.py rollback_drill` and follow the printed instructions.
3. Record the incident in `docs/runbooks/incident-log.md`.

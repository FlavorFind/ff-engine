# Operations Runbook — Flavor Find Engine

**Version:** 1.0.0  
**Last updated:** 2026-10-26  
**Service:** ff-engine (isolated recipe engine, Sprint 1)  
**Staging URL:** https://ff-engine-kuar.onrender.com  

---

## Health Check

```bash
curl https://ff-engine-kuar.onrender.com/v1/health/
# Expected: {"status": "ok", "database": "ok"}
```

If `database` is not `"ok"`, the PostgreSQL connection is broken — see [Database Issues](#database-issues).

---

## Deploy

Render auto-deploys on every push to `main`. To trigger manually:

1. Go to Render dashboard → ff-engine → Manual Deploy → Deploy latest commit.
2. Wait for the health check to go green (≈ 2 min).
3. Run the golden set post-deploy:
   ```bash
   python manage.py run_golden_set --fail-fast
   ```

---

## Monitoring and Alerts

**Uptime monitoring:** BetterStack (or UptimeRobot) pings `/v1/health/` every 60 seconds.
- If the check fails 3 times in a row, an alert is sent via Sentry notification.

**Error tracking:** Sentry captures all unhandled exceptions and 5xx responses automatically.
- Set `SENTRY_DSN` environment variable to enable.
- Alert threshold: any new error or error rate spike > 1% in a 5-minute window.

**Response time alerts:** Sentry performance monitoring tracks p95 latency.
- Alert if p95 exceeds 500ms for the `/v1/search/by-ingredients` endpoint.

To check current alerts:
```bash
# Check service health
curl https://engine.flavorfind.co.ke/v1/health/
# Review Sentry dashboard for recent errors
```

---

## Rollback

Run the rollback drill first to print instructions:

```bash
python manage.py rollback_drill
```

Then follow the printed steps:

1. In Render dashboard → Deploys → find the previous deploy → **Rollback to this deploy**.
2. If a migration reversal is needed:
   ```bash
   python manage.py migrate <app> <previous-migration-name>
   ```
3. Verify health: `curl /v1/health/`
4. Verify golden set: `python manage.py run_golden_set --fail-fast`

---

## Backup and Restore

### Take a backup

```bash
python manage.py backup_drill --step backup
# Writes to data/snapshots/<timestamp>/
```

### Verify a backup

```bash
python manage.py backup_drill --step verify --snapshot-dir data/snapshots/<timestamp>
```

### Restore from backup (disaster recovery only)

```bash
python manage.py backup_drill --step restore --confirm \
  --snapshot-dir data/snapshots/<timestamp>
```

---

## Database Issues

**Symptom:** `/v1/health/` returns `{"database": "error"}`.

1. Check Render → ff-engine → Logs for `OperationalError`.
2. Check Render → PostgreSQL instance status.
3. Restart the web service: Render dashboard → Restart.
4. If the DB is truly down, Render's managed Postgres has automatic failover — wait up to 5 min.

---

## Redis / Cache Issues

**Symptom:** Search is slow (no cache hits), or `500` errors with `ConnectionError`.

1. Check `REDIS_URL` env var on Render.
2. The search endpoint has a fallback — it will work without Redis, just slower.
3. To clear all cache keys:
   ```bash
   python manage.py shell -c "from django.core.cache import cache; cache.clear()"
   ```

---

## Zero-Result Queries

Review which ingredient inputs are returning zero dishes:

```bash
python manage.py qa_zero_results --top 20
```

Act on the top entries by adding aliases or new seed data.

---

## QA Report

Run the full data quality report:

```bash
python manage.py qa_report --fail-on-critical
```

Exits 1 if there are integrity violations (V01–V23 rules). Green exit = data is clean.

---

## Load Testing

```bash
# Standard load test (50 users, 2 min):
FF_API_KEY=<key> locust -f load_tests/locustfile.py \
  --host https://ff-engine-kuar.onrender.com \
  --users 50 --spawn-rate 5 --run-time 2m --headless \
  --html load_tests/report_load.html -u SearchUser

# Soak test (20 users, 30 min):
FF_API_KEY=<key> locust -f load_tests/locustfile.py \
  --host https://ff-engine-kuar.onrender.com \
  --users 20 --spawn-rate 1 --run-time 30m --headless \
  --html load_tests/report_soak.html -u SoakUser
```

Target: p95 < 150 ms at 50 rps.

---

## Incident Log

Record incidents in `docs/runbooks/incident-log.md`. Template:

```
## [DATE] — [TITLE]
**Severity:** P1 / P2 / P3
**Duration:** X min
**Impact:** Description
**Root cause:** Description
**Resolution:** Steps taken
**Follow-up:** Link to GitHub issue
```

---

## Render Free Plan Database Expiry

The PostgreSQL database (`flavorfind_engine_db`) is on Render's **free plan**, which
**expires after 90 days of inactivity** (or as per Render's current free-tier policy).

**Renewal checklist (run before expiry):**
1. Log in to the Render dashboard.
2. Navigate to **PostgreSQL → flavorfind_engine_db**.
3. Check the expiry date shown on the database overview page.
4. If expiry is within 14 days: upgrade to a paid plan OR export a full backup and
   recreate the database on a new free instance.

**External backup before renewal:**
```bash
python manage.py backup_drill --step backup
```
Store the snapshot outside Render (S3, GCS, or local) before recreating the database.

**Tracking:** Review this checklist every 60 days. Log any renewal in the incident log.

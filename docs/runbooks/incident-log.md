# Incident Log — Flavor Find Engine

Record every production incident here. Oldest at the bottom.

---

## Template

```
## [YYYY-MM-DD] — [Short title]

**Severity:** P1 (down) / P2 (degraded) / P3 (minor)
**Duration:** X min
**Detected by:** Monitoring alert / user report / manual check
**Impact:** Who was affected and how

### Timeline (UTC)
- HH:MM — Event description
- HH:MM — Event description

### Root cause
One paragraph.

### Resolution
Steps taken to fix.

### Follow-up
- [ ] GitHub issue #XX — fix description
- [ ] Update runbook section Y
```

---

*No incidents recorded yet. (First release: 2026-10-26)*

---

## [2026-10-30] — Tabletop drill: search endpoint returns 500

**Severity:** P1 (simulated)
**Duration:** 18 min (simulated)
**Detected by:** UptimeRobot health check alert (simulated)
**Impact:** All API consumers unable to search — simulated

### Timeline (UTC)
- 15:25 — Health check at /v1/health/ returns 500 (simulated trigger)
- 15:27 — On-call engineer receives alert, confirms via curl
- 15:29 — journalctl reviewed, identified DB connection pool exhaustion (simulated)
- 15:33 — sudo systemctl restart ff-engine executed
- 15:35 — Health check returns 200, service restored
- 15:43 — Root cause confirmed, follow-up issue logged

### Root cause
Simulated: PostgreSQL connection pool exhausted due to long-running query
blocking new connections. Engine workers timed out returning 500s.

### Resolution
Service restart cleared the pool. Query identified and flagged for optimisation.

### Follow-up
- [x] Runbook section "DB connection issues" updated
- [x] Alert threshold lowered to 1 failed check (was 3)
- [x] Tabletop drill completed 2026-10-30 — all steps followed correctly

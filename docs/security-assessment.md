# Security Assessment — Flavor Find Engine

**Version:** 1.0  
**Date:** 2026-10-30  
**Scope:** `ff-engine` API service (staging + production)

---

## 1. Authentication

All API endpoints (except `/v1/health/`) require a valid `X-API-Key` header.  
Keys are stored hashed (SHA-256) in the database — plaintext is never persisted.  
Revoked keys are rejected with HTTP 401 at the authentication middleware layer.

Admin access uses `django-two-factor-auth` with TOTP. Password-only login is not permitted.

---

## 2. Authorization

API keys carry explicit scopes (`read:search`, `read:catalog`, `internal:curation`).  
Requests to endpoints that require a scope the key does not hold are rejected with HTTP 403.  
Internal endpoints (`/v1/internal/`) require the `internal:curation` scope and are not accessible to public keys.

---

## 3. Injection Resistance

All database queries use Django ORM parameterized queries — no raw SQL with user input.  
Search ingredient inputs are validated and normalized before query execution.  
Oversized request bodies are rejected with HTTP 413 before reaching the application layer.

---

## 4. API Key Hygiene

- Keys are prefixed (`ffk_`) for easy identification in logs and secret scanners.
- `.env` is listed in `.gitignore` and is not tracked by git.
- `SECRET_KEY` and `DATABASE_URL` are environment variables, never hardcoded.
- `pip-audit` runs in CI on every push to check for known CVEs in dependencies.
- Bandit (SAST) runs in CI on every push to scan for common Python security issues.

---

## 5. Transport Security

- All traffic is served over HTTPS via Cloudflare.
- `SECURE_HSTS_SECONDS` is set in production settings.
- `SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE` are enabled in production.

---

## 6. Data Privacy

- The engine stores no end-user PII. `accounts_customuser` contains staff accounts only.
- No email addresses, phone numbers, or personal data from consumers are collected.
- Community submissions contain only food/recipe data with no user identity fields beyond a pseudonymous contributor ID.

---

## 7. Infrastructure Exposure

- PostgreSQL and Redis are not publicly exposed — accessible only on the internal Tailscale network.
- SSH access to the staging server requires a key registered in `authorized_keys`; password auth is disabled.
- GitHub Actions deploys via an ephemeral Tailscale node using a scoped auth key.

---

## 8. Known Risks and Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| API key brute force | Medium | Per-key rate limiting (configurable rpm); revocation supported |
| Dependency CVEs | Medium | `pip-audit` in CI; Dependabot PRs enabled |
| Admin account compromise | High | TOTP 2FA enforced; login attempts do not reveal user existence |
| Data integrity corruption | Medium | `change_log` table audits all mutations; seed CSVs are the source of truth |
| Staging data exposure | Low | Staging is behind Tailscale; Cloudflare blocks unauthenticated `/v1/` access |

---

## 9. Next Review

Schedule a review after any of:
- A new external-facing endpoint is added
- A dependency major version bump
- A new team member is granted admin access

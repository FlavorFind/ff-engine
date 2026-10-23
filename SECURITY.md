# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in ff-engine, please report it
**privately**. Do not open a public GitHub issue.

**Email:** security@flavorfind.co.ke

Include in your report:
- A description of the vulnerability
- Steps to reproduce it
- The potential impact
- Any suggested fix (optional)

We will acknowledge your report within **48 hours** and aim to release a fix
within **14 days** for critical issues.

We do not currently run a bug bounty programme, but we will credit researchers
who report valid vulnerabilities (unless you prefer to stay anonymous).

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest  | ✅ Yes    |

## Security Expectations

- All human accounts (curators, reviewers, admins, engineers) require two-factor
  authentication.
- API keys are stored hashed and scoped. They are shown once and revocable.
- The engine database is on a private network and never exposed to the internet.
- The engine holds no user data. A breach of the engine cannot expose users.
- All data changes are logged with who, when and why.
- Backups are encrypted and tested on a schedule.

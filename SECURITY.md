# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please report it responsibly.

### How to Report

**Please use GitHub's private vulnerability reporting feature:**

1. Go to the [Security tab](../../security) of this repository
2. Click "Report a vulnerability"
3. Fill out the form with details about the vulnerability

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested fixes (optional)

### What to Expect

- **Acknowledgment**: We will acknowledge receipt within 48 hours
- **Updates**: We will provide updates on our progress
- **Resolution**: We aim to resolve critical issues promptly
- **Credit**: We will credit reporters in our release notes (unless you prefer anonymity)

### What NOT to Do

- Do not open public issues for security vulnerabilities
- Do not exploit vulnerabilities beyond what is necessary to demonstrate them
- Do not access or modify other users' data

## Security Measures

This project implements several security measures:

- **Dependency scanning**: Regular audits with `pip-audit` (Python) and `npm audit` (JavaScript)
- **Framework protections**: Django's built-in CSRF, XSS, and SQL injection prevention
- **Secrets management**: All secrets managed via environment variables
- **Audit logging**: Changes tracked via django-auditlog

## Production Security Configuration

The following settings are required for a secure production deployment.

### Required Environment Variables

| Variable | Requirement |
|----------|-------------|
| `SECRET_KEY` | Must be set — Django will refuse to start without it. Use a long random string (50+ characters). |
| `JWT_SIGNING_KEY` | Must be set — used to sign all JWT access and refresh tokens. Use a separate long random string. |
| `DEBUG` | Must be `False` in production. |

### HTTPS / SSL

Tractor is designed to run behind a reverse proxy (nginx) that handles TLS termination. Configure your proxy to:

- Redirect all HTTP traffic to HTTPS
- Set `Strict-Transport-Security` (HSTS) with a long `max-age` (e.g. 1 year: `max-age=31536000`)

If not using a proxy, enable Django's own SSL redirect and HSTS in `backend/settings/production.py`:

```python
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
```

### JWT Token Security

- `JWT_SIGNING_KEY` must be kept secret and rotated if compromised. All existing sessions are invalidated on rotation.
- Access tokens expire after 60 minutes; refresh tokens after 24 hours.
- Refresh token rotation is enabled — each refresh issues a new refresh token and blacklists the old one.

### API Key Rotation

API keys are stored as SHA-256 hashes and never persisted in plaintext. To rotate a key:

1. Generate a new key from the Settings page (admin only) or Django Admin.
2. Distribute the new key to the consuming service.
3. Revoke the old key from the Settings page.

There is no grace period — the old key is rejected immediately on revocation.

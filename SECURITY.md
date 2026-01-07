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

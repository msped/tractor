# Contributing to Tractor

Thank you for your interest in contributing to Tractor! This document provides guidelines for contributing to the project.

## Getting Started

1. Fork the repository
2. Clone your fork locally
3. Set up the development environment (see README.md)
4. Create a new branch for your feature or fix

## Development Setup

### Backend (Django)

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

In a separate terminal, start the task queue:

```bash
python manage.py qcluster
```

### Frontend (Next.js)

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

## Running Tests

### Backend

```bash
python manage.py test                           # Run all tests
python manage.py test cases.tests.test_views    # Run specific module
coverage run manage.py test && coverage report  # With coverage (90% threshold)
```

### Frontend

```bash
cd frontend
npm run cy:run      # Headless
npm run cy:open     # Interactive
npm run cy:test     # With coverage (80% threshold)
```

## Code Style

### Python

- Follow PEP 8 guidelines
- Use meaningful variable and function names
- Add docstrings to functions and classes

### JavaScript

- Run `npm run lint` before committing
- Use functional components with hooks for React
- Follow existing patterns in the codebase

## Commit Messages

Use clear, descriptive commit messages:

- `feat: add user authentication flow`
- `fix: resolve document upload timeout`
- `docs: update installation instructions`
- `test: add tests for redaction service`
- `refactor: simplify case export logic`

## Pull Request Process

1. Ensure all tests pass locally
2. Update documentation if needed
3. Create a pull request with a clear description of changes
4. Link any related issues
5. Wait for review - maintainers will provide feedback

## Reporting Issues

When reporting bugs, please include:

- Steps to reproduce
- Expected vs actual behavior
- Browser/OS/Python version if relevant
- Screenshots if applicable

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## Questions?

Open an issue for questions about contributing.

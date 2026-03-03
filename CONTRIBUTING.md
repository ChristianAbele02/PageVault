# Contributing to PageVault

Thank you for your interest in contributing! PageVault is a small personal project and every contribution — bug reports, feature ideas, documentation fixes, or code — is genuinely appreciated.

---

## Getting Started

### 1. Fork & clone

```bash
git clone https://github.com/YOUR_USERNAME/pagevault.git
cd pagevault
```

### 2. Set up a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
```

### 3. Install dev dependencies

```bash
make dev
# or: pip install -r requirements-dev.txt
```

### 4. Run the app locally

```bash
make run
# open http://localhost:5000
```

### 5. Run tests

```bash
make test
# with coverage:
make coverage
```

---

## Development Workflow

1. **Create a branch** from `main`:
   ```bash
   git checkout -b feature/my-feature
   # or: git checkout -b fix/some-bug
   ```

2. **Make your changes.** Keep commits focused and descriptive.

3. **Write or update tests** in `tests/test_api.py` — all new API behaviour must be tested.

4. **Lint and format**:
   ```bash
   make format   # auto-fix formatting
   make lint     # check for issues
   ```

5. **Run the full test suite** and make sure everything passes:
   ```bash
   make test
   ```

6. **Open a Pull Request** against `main` using the provided PR template.

---

## Code Style

- **Python**: follows [PEP 8](https://peps.python.org/pep-0008/), enforced by [Ruff](https://docs.astral.sh/ruff/)
- **Line length**: 100 characters
- **Docstrings**: Google style for public functions
- **Type hints**: encouraged for new code, not strictly required

---

## Reporting Bugs

Please use the [Bug Report](.github/ISSUE_TEMPLATE/bug_report.yml) template. Include:
- Python version and OS
- Steps to reproduce
- Expected vs actual behaviour
- Relevant log output

---

## Suggesting Features

Use the [Feature Request](.github/ISSUE_TEMPLATE/feature_request.yml) template. Explain the problem you're trying to solve, not just the solution.

---

## Commit Message Convention

We loosely follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add Goodreads CSV import
fix: handle missing ISBN gracefully
docs: update Docker setup instructions
test: add review deletion edge cases
chore: bump Flask to 3.1
```

---

## Questions?

Open a [GitHub Discussion](https://github.com/yourname/pagevault/discussions) or file an issue — happy to help.

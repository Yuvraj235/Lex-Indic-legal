# Lex-Indic test suite

94 tests, runs in <2 seconds, zero network calls.

```bash
# Run everything
python3 -m pytest tests/

# Just the pure-function tests (fastest, ~0.2s)
python3 -m pytest tests/test_pure.py

# Just the Flask route tests (~1.5s)
python3 -m pytest tests/test_routes.py

# Verbose, with print output
python3 -m pytest tests/ -v -s
```

## Design rules

1. **No network.**  Groq, Gemini, Ollama, and ChromaDB are all monkey-
   patched in `tests/conftest.py` so the suite doesn't depend on
   external services or API keys.
2. **Isolated state.**  Every test runs in a per-test temp dir
   (`isolate_outputs` fixture in conftest.py), so writes to
   `outputs/` don't leak across tests or pollute the real folder.
3. **Single import of the Flask app.**  `app` is a session-scoped
   fixture — built once, reused across all route tests, runs in <2s.

## Coverage

| Layer | File | Tests |
|---|---|---|
| Pure functions (no Flask) | `test_pure.py` | 43 |
| Flask routes + JSON contracts | `test_routes.py` | 51 |

## What's NOT tested

- Real Groq / Gemini calls (would cost money + need network)
- Real ChromaDB embedding build (slow, needs Gemini)
- Browser-level UI (no Selenium / Playwright yet)
- Cloudflare tunnel delivery
- Word add-in inside actual Word

Add `@pytest.mark.network` to any test that genuinely needs an external
service — those skip by default and only run with `pytest -m network`.

## CI

There's no GitHub Actions config yet — drop the following at
`.github/workflows/test.yml` when you're ready to publish:

```yaml
name: tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.13' }
      - run: pip install -r requirements.txt pytest pytest-mock
      - run: python -m pytest tests/ -v
```

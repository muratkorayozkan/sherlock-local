# Verification — 2026-11-09

## Automated checks

- Python 3.12, Windows: `python -m pytest -q` — 27 passed.
- `node --check sherlock_local/static/app.js` — passed.
- `uv lock --check` — locked dependency resolution checked.
- Application wheel built and installed successfully with pip.
- Launcher regression: existing environment is reused and occupied port is reported without reinstalling dependencies.

The suite covers input validation, localhost host/origin boundary, platform validation, live job snapshots, single active scan, subprocess cancellation, non-reading workers, global deadlines, worker crashes, bounded retention and CSV formula escaping. The actual Sherlock engine is exercised against a controlled local HTTP server, including missing profiles, bot challenge pages, HTTP 401/403/429/500/503. External platform access is not required for the suite.

## Browser QA

Headless Chrome, 1440×1050 desktop and 390×844 mobile:

- Initial page, platform filtering and selection.
- Result rendering, status filters and platform text filtering.
- Only http/https links on found results are actionable.
- No page JavaScript errors; no mobile document overflow.
- Progress polling recovers after six consecutive simulated HTTP 503 responses.

## Live integration

Real Sherlock worker searched the public `octocat` username on GitHub: completed, found profile at `https://www.github.com/octocat`. CSV endpoint returned an UTF-8 BOM export. This validates the integration, not the accuracy or availability of every third-party platform.

## Review fixes

- HTTP failures (other than the missing-resource statuses 404/410) are inconclusive even when Sherlock's status-code detector returns Available.
- Frontend polling retries with bounded backoff and does not abandon a running job after transient failures.
- Worker input is sent from the monitor thread so a child that does not read stdin cannot block the API request; the overall deadline can terminate it.
- PowerShell dependency probe passes module names as arguments, avoiding Windows PowerShell's embedded quote handling.

## Limits

Platform definitions are bundled with the pinned Sherlock 0.16.0 release. They are not refreshed online. Platform-specific behavior may change. Search state is memory-only, with the last 20 jobs retained. No account identity correlation is performed.

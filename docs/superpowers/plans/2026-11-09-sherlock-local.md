# Sherlock Local Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement task-by-task. User explicitly authorized starting work; execute inline.

**Goal:** Deliver a runnable local Turkish username search app and transfer it to the user's private GitHub repository.

**Architecture:** FastAPI serves static UI and bounded in-memory scan jobs. Each job launches an isolated Sherlock worker and reads JSON-line progress. Browser polls snapshots and downloads CSV.

**Tech Stack:** Python 3.12, FastAPI, uvicorn, sherlock-project, vanilla JavaScript, pytest.

**Spec:** docs/superpowers/specs/2026-11-09-sherlock-local-design.md

## Global Constraints
- Windows; bind 127.0.0.1; Turkish UI; real Sherlock; upstream attribution; private GitHub target.
- No persisted personal search data, no arbitrary commands or user-supplied target URLs.

## Review Focus
- Malformed username and invalid platform rejected before work starts.
- Worker errors and cancellation remain distinct from missing accounts.
- Duplicate scans and retained job growth bounded.
- Host/origin validation prevents unwanted browser requests.
- CSV formula characters and profile links safely handled.

## Task 1: API and scan protocol
Files: pyproject.toml, sherlock_local/app.py, jobs.py, worker.py, tests/test_app.py, tests/test_worker.py.
Interfaces: create_app(manager=None); manager.start(username, sites, timeout), get(id), cancel(id); worker emits started/result/error/done JSON lines.
- [x] Write failing API tests for validation, snapshots, CSV, host/origin rejection and concurrency.
- [x] Run pytest and observe missing implementation failures.
- [x] Implement isolated worker, bounded job manager, API and dependency configuration.
- [x] Run suite; test actual worker against controlled local HTTP fixture.

## Task 2: User interface and launcher
Files: sherlock_local/static/index.html, styles.css, app.js, start.ps1, start.cmd.
- [x] Build Turkish responsive search form, platform selection, progress, filters, cancellation, CSV and accessible status updates.
- [x] Exercise browser: empty state, search, results, errors, cancel, narrow viewport.
- [x] Verify launcher starts loopback server without requiring global activation.

## Task 3: Delivery
Files: README.md, LICENSE, THIRD_PARTY_NOTICES.md.
- [x] Document setup, architecture, attribution and limitations.
- [x] Run full pytest, JavaScript syntax check and live upstream smoke test.
- [x] Review and verify source for GitHub transfer. User explicitly approved the existing public repository after visibility was checked.
- [x] GitHub write access granted by the user after the initial HTTP 403. Deliver the verified application tree atomically to the public repository and verify its SHA against local source.

# Sherlock Local

Approved in chat: Turkish browser application for personal use on Windows, powered by Sherlock. Target private repository: https://github.com/muratkorayozkan/sherlock-local.

Delivery update: GitHub reported the repository as public; the user explicitly approved public transfer on 2026-11-09.

## Intent
Search a username across Sherlock's platforms, see progress and profile links, filter results, and download CSV. Run on 127.0.0.1 only; external network access is needed to check platforms. No accounts, cloud hosting, or persisted search history.

## Approaches
Chosen: FastAPI with local HTML/CSS/JavaScript and the real Sherlock Python package. Alternative: packaged desktop app, rejected for extra packaging overhead. No third party frontend CDN or build pipeline needed.

## Behavior
Turkish responsive interface. Select all platforms or individual platforms; default to a small popular set for a quick first search. Stream snapshots through polling; separate found, absent and inconclusive results. Bound username length, timeout and concurrent searches. Allow cancellation. Keep jobs in memory with bounded retention. CSV includes all completed checks and protects against spreadsheet formulas. Local API rejects untrusted hosts and cross-origin mutations.

## Attribution
README explains setup, limitations, upstream repository and MIT license. Sherlock is a dependency, not copied and rebranded source. Retain attribution in THIRD_PARTY_NOTICES.md.

## Builder decisions
Use isolated Python 3.12, FastAPI, uvicorn, sherlock-project 0.16.0 (verify available package), vanilla frontend. Run a separate worker process per scan so cancellation can terminate networking. Sherlock QueryNotify emits JSON lines; parent consumes only structured protocol messages. No shell command interpolation. One active scan, bounded retained jobs. Test API and worker boundary without depending on external sites; additionally run a live smoke check.

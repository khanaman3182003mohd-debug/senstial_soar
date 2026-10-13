# senstial_soar
# SOAR Sentinel — Local Analyst Workspace (Full-Stack, Secure)

A self-contained **Flask + SQLite** project: a Security Orchestration, Automation and Response (SOAR) learning platform with real authentication, role-based access, audit logging, a modern UI, and an interactive assistant.

> **Demo application, not a production product.** Local records only. Playbooks run in dry-run / preview mode — no containment, isolation, or destructive actions ever execute automatically.

## Aaj ki features

* **Authentication & access control** — Password hashing (Werkzeug pbkdf2), role-based access (`admin`, `analyst`, `viewer`), login throttling, CSRF protection, security headers, 30-min session expiry.
* **Auto-triage bot** — RegEx extraction of IP/domain/URL/email/SHA-256/MD5, simulated enrichment verdict, priority scoring, playbook suggestion.
* **Case management** — Per-incident detail page: assignment, status, notes/timeline, observability Verdicts (Malicious/Internal/Unknown).
* **Human-in-the-loop approvals** — Analyst proposes an action; Admin approves/rejects in `/approvals` queue (with pending badge).
* **Alert ingestion webhook** — `POST /api/ingest` with token, auto-creates case + indicators + suggested playbook (currently LIVE at `http://127.0.0.1:5000`).
* **Google login (OAuth)** — optional, via `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` env vars.
* **Registration** — anyone can create a Viewer account (configurable via `ALLOW_REGISTRATION`).
* **Password change** — `/account/password`, current password required.
* **Audit log** — logins, indicator enrichment, notes, assignments, approvals, ingested alerts.
* **Interactive UI** — dark/light theme, responsive, assistant panel (rule-based, local, no external API).

## Project Structure


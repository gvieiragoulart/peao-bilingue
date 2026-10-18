# Peão Bilíngue

A personal job radar for Windows: it collects jobs from several sites, filters them by your
searches and lets you know about the new ones. You pick which to analyze, with which LLM and
with which source's profile.

Each analysis gives a fit score, a summary of the fit, preparation steps, exactly 20 interview
questions, gaps, and what to improve in your profile.

The app's screens are in **Brazilian Portuguese**; the code and these docs are in English.
Every user-facing text lives in [`src/peao_bilingue/locales/`](src/peao_bilingue/locales), so
another language is a new catalog away.

## Install

```bash
uv sync
uv run peao-ui
```

The app opens with no console. Run it from the project folder: the data (`data/`) and `.env`
are looked up in the current folder. **The first time**, a six-step guide takes the place of the
tabs: what the app does with your data, a first search, the sources, your CV, the LLM, and the
daily collection with its notices. Nothing is saved until "Concluir"; it can be skipped, and
reopened from Settings. After that, everything is configured on its tabs: sources, searches,
LLM providers, notices and limits. **Keys and passwords live in Windows Credential Manager**,
not in a file; the rest goes to `data/config.json`. `.env` (copied from `.env.example`) still
works as an alternative for the command line.

| Tab (in the app) | What it's for |
|---|---|
| Vagas (Jobs) | the list with fit and filters, a text search; pick the LLM and profile, then **Analisar**; mark as studying/applied/discarded |
| Buscas (Searches) | keywords, excluded terms and which sources each search uses |
| Fontes (Sources) | turn each site on or off; manual login and session check |
| LLMs | the LLM preselected on the Jobs tab, models and keys |
| Perfil (Profile) | your pasted or imported CV, each source's profile (no personal data), their history, and notes about you |
| Execuções (Runs) | "collect now", the daily automatic collection, history and the live log |
| Configurações (Settings) | collection limits, notice channels (Windows notification, email, WhatsApp), version and logs |

**Each source has its own profile** (the one on VanHack is not the one on LinkedIn), and a job
is analyzed, by default, with its source's profile. A job from a source with no profile (the
public APIs) uses **your CV**: paste it, or import a `.pdf`, `.txt` or `.md`, on the Profile tab.
Emails, phone numbers, links and CPF numbers are removed before it is saved; a name or an address
can't be found by a pattern, so check the text. The **notes** (what you want, what the profile
doesn't show) go into every analysis. The collection calls no LLM: nothing is spent until you
click Analyze.

**Sources:** VanHack (manual login, reads your profile), Remotive and Remote OK (public APIs of
remote jobs, no account), Arbeitnow (jobs in Germany with visa sponsorship), Himalayas (remote
jobs open to people in Brazil), We Work Remotely (public RSS) and Strider (its public jobs page:
long-term remote jobs at US companies, open to Latin America), and the job repositories of
Brazilian communities on GitHub (backend-br/vagas and others, set in `github_job_repositories`),
and companies' own job boards on Greenhouse, Lever and Ashby (Nubank, Stone, QuintoAndar and
others, set in `company_boards`; only jobs open in Brazil, LATAM or worldwide), Jobicy (a
public API of remote jobs open to Brazil), Get on Board (fully remote jobs from a Latin
American tech job board) and Hacker News' monthly "Who is hiring?" thread (only posts open to
Brazil, LATAM or anywhere).
The APIs are queried once per
collection and the answer is reused for hours; Remotive asks for at most ~4 calls a day. Each
job keeps its original link on the source, as their terms ask. Turn the sources on in the
Sources tab, or only for one collection: `uv run peao run --source remoteok`.

The same job posted on several sites (same company and title) shows up once, with the other
links under "Também em" (Also on) in the detail.

The app uses **the Chrome installed on the machine**, not Playwright's Chromium: VanHack's
Cloudflare rejects unusual browsers.

## Command line

The CLI logs in, manages searches, collects and schedules; it is what the scheduled collection
uses. Analysis happens in the app.

**1. Log in to VanHack (always by hand).** Login is passwordless (an email link, Google or
LinkedIn) and guarded by a human check, so there is no automatic login:

```bash
uv run peao login
```

It opens a Chrome window. If you log in by email, **copy the link you get and paste it in that
window's address bar**; clicking it in your email client creates the session in the wrong
browser. The "confirm you are human" check is yours; the robot never solves it. Check with
`uv run peao check`.

**2. Add your searches:**

```bash
uv run peao searches add "Python" python django fastapi
uv run peao searches add "React" react typescript --exclude internship
uv run peao searches                    # list
```

Careful with `--exclude`: the filter looks at the whole description, and a senior job often
says "mentor junior engineers"; excluding "junior" would drop exactly those.

**3. Collect:**

```bash
uv run peao run                  # collects and saves the new jobs; calls no LLM
uv run peao run --notify         # and reports new jobs and problems on the enabled channels
```

To limit the sources: `--source vanhack`. `uv run peao adapters` lists what is available.

## Daily automatic collection

On the **Execuções** (Runs) tab, type the time and click **Agendar** (Schedule), or from the
command line:

```bash
uv run peao schedule enable --time 08:00
uv run peao schedule                    # next and last run
uv run peao schedule disable
```

The task lives in Windows Task Scheduler ("Peao Bilingue - daily collection") and runs with the
app closed; if the PC was off at that time, it runs as soon as it turns on. It collects like
`uv run peao run` and **reports the new jobs** (title, source and link) as a **Windows
notification**, on by default with nothing to set up, and on the other channels enabled in
Settings (email, WhatsApp), which start off: turn on the ones you have filled in. If something fails (the
VanHack session expired, a site went down), a notice says what, on every collection, until it is
fixed. Since it runs with no window, the log goes to `data/logs/collection.log`. One collection runs
at a time: if the task starts while you collect from the app (or the other way around), the
second one is turned away.

## The .exe (no Python or uv needed)

```bash
uv run --group packaging pyinstaller packaging/peao_bilingue.spec --noconfirm
```

It builds `dist/PeaoBilingue/` (one folder, ~170 MB): take the whole folder and open
`PeaoBilingue.exe`. With no arguments it opens the app; with arguments it is the same command
line (`PeaoBilingue.exe run`, `PeaoBilingue.exe login`...). Scheduling the collection from the
.exe's window makes the task call the .exe itself.

Differences from running the project:

- **The data lives in `%LOCALAPPDATA%\PeaoBilingue`** (`data/`, `.env`, `profile_notes.md`,
  `artifacts/`), not next to the program: the .exe can be anywhere. To bring existing data, copy
  the project's `data/` there (with the app closed). `PEAO_DATA_DIR` still points elsewhere.
- The LLM keys live in Windows Credential Manager, shared with the project: what was saved on
  the LLMs tab works in both. A key only in the project's `.env` does **not** reach the .exe;
  save it on the tab.
- It uses **the installed Chrome** (Playwright's Chromium isn't bundled).

## Choosing the LLM

Four providers: **Claude** (`anthropic`, the default), **Ollama** (local and free), **OpenAI**
and **Gemini**. You choose on the Jobs tab, for each analysis; the last one picked becomes the
default. The analysis is written in the app's language.

To spend nothing, install Ollama and download a model that fits a 6 GB GPU:

```bash
ollama pull qwen3:8b
```

Local 7–8B models are weaker at the finer parts (the 20 questions and the profile
improvements): good for a first look, with Claude for the jobs that really matter.

## How it works

Ports and adapters: the core only knows interfaces (`JobSource`, `LLMProvider`, `Notifier`,
`JobRepository`...), and each site, LLM or channel is an adapter registered by name in a
factory. Adding a source is writing a module and registering it; nothing in the core changes.
Details and decisions are in [CLAUDE.md](CLAUDE.md).

Each run is recorded with counters and errors. A failing source doesn't stop the others; any
reading failure leaves a screenshot + HTML in `artifacts/`.

## Logs, version and updates

The app logs to `data/logs/app.log`, the scheduled collection to `data/logs/collection.log`, and
a hard crash to `data/logs/crash.log` (in the .exe, under `%LOCALAPPDATA%\PeaoBilingue`).
**Configurações → Sobre e suporte** (Settings → About and support) shows the version and opens
the logs folder: that folder is what to send when asking for help.

When the app opens it asks GitHub Releases whether there's a newer version and, if there is,
shows a banner with a download button. It sends nothing about you; turn it off in the same
section.

## Expired session

When a run ends with `login_required`, log in again: **Fazer login** (Log in) on the Sources
tab, or `uv run peao login`. `data/state.json` holds session cookies: treat it like a password
and never commit it (it is in `.gitignore`).

## Upgrading from a Portuguese-named version

Versions before 2026-10-17 used Portuguese names for the database, the settings and the
commands. The first time the new version opens it migrates everything by itself: the database
is moved to the new schema (a copy of the old file is left next to it as
`peao.before-english-<date>.db`), `config.json` and `.env` get the new setting names, and the
daily task is registered again under its new name and command.

## Development

```bash
uv run pytest                          # all offline: no site, no SMTP, no LLM
uv run pytest -m "not integration"     # unit tests only: seconds
uv run pytest -m integration           # Chromium, a Tk window, PowerShell, another process
uv run ruff check . && uv run ruff format .
uv run mypy                            # strict typing of src/ and tests/
```

The whole pipeline is tested with fakes of the ports and an in-memory SQLite. The scraping
adapters use real, anonymized HTML in `tests/fixtures/<source>/`. The tests run with the
English text; `tests/test_i18n.py` checks that every message has a translation and that no
Portuguese slipped into the code.

**CI** (`.github/workflows/ci.yml`): every PR and every push to `main` runs three jobs: lint
and typing (ruff and mypy, on Linux), unit tests and integration tests (on Windows, the app's
OS; the integration job installs Playwright's Chromium, with a cache).

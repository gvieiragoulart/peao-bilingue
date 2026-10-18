# Peão Bilíngue

A personal job radar: it collects jobs from several sites, filters them by configurable searches
and reports the new ones by email and WhatsApp. The LLM fit analysis is **requested one job at a
time** in the app, with the LLM and profile picked right then. A Windows desktop app
(CustomTkinter), with the daily collection started by Windows Task Scheduler.

Each analysis has: a fit score (0–100), a summary of the fit, preparation steps, **exactly 20**
interview questions, gaps, and what to improve in the profile (CV, LinkedIn, VanHack).

## Context

- **User:** Gabriel, a senior backend engineer (PHP/Laravel, Python, TypeScript, AWS). Uses
  **Windows** (PowerShell). **Talk to him in Brazilian Portuguese.**
- **Language rules (since 2026-10-17, the code is going public):** code, comments, docstrings,
  logs, tests, docs and commit messages in **English**; everything the app shows the user in
  **Brazilian Portuguese**, through the translation catalog (see "Text and translations").
- **History:** started as "VanHack Watcher" (VanHack only, Claude only, a FastAPI panel). On
  2026-10-06 it became multi-source and multi-LLM with ports and adapters; on 2026-10-17 the
  code moved to English. The approved plan is in
  `~/.claude/plans/quero-alterar-o-nosso-resilient-patterson.md`.
- **Repository:** `gvieiragoulart/peao-bilingue` (private for now). `gh` is installed but **not on
  PATH** (`"/c/Program Files/GitHub CLI/gh.exe"`) and the PAT can't create repositories or change
  visibility.
- **Hardware:** an RTX 3050 Laptop with 6 GB of VRAM, which limits Ollama to quantized 7–8B
  models.

## Current state (2026-10-17)

**Phases 1 to 5 and 8 of the roadmap are done** (6 waits for a decision; 7 hasn't started), plus
the 2026-10-07 change: the collection calls no LLM; each job is analyzed with the **Analisar**
(Analyze) button on the Jobs tab, with the chosen LLM (Anthropic, Ollama, OpenAI, Gemini) and the
**profile of the job's source** (each source has its own). The code is in English, with the app
in Brazilian Portuguese. All tests run offline; `ruff` and `mypy --strict` are clean.

The database evolves through **automatic additive migration** (`add_new_columns` in
`persistence/sqlite/database.py`): `create_all` doesn't add columns to existing tables, so a new
model field gets an `ALTER TABLE ADD COLUMN` with the model's default. A non-additive change needs
a hand-written migration, like `persistence/sqlite/legacy.py`.

---

## Non-negotiable rules

- **Never bypass 2FA, captchas or bot detection, on any source.** No stealth, fingerprint spoofing
  or IP rotation. If one shows up: stop, save evidence (`artifacts/`), tell the user and require
  a manual login.
- **Login is always manual** on sources that need an account. The robot only reuses the saved
  session; if it expired, the run ends with `login_required`. Never fill in a login form.
- **Polite behavior:** one run at a time, no parallel pages, a random 2–5 s pause between
  navigations (the adapter's job), a limit of jobs detailed per run.
- **Sources with an official API or feed** use the API/feed. Scraping only where there's no
  alternative, and always reading the DOM like a user.
- **VanHack:** never call the internal API (no httpx, no intercepting XHR).
- **Secrets in Windows Credential Manager** (through `keyring`, service `peao-bilingue`), never in
  a committed file. `.env` (in `.gitignore`, along with `data/` and `artifacts/`) is only the
  CLI's fallback. Never log a password or a cookie.
- **No PII in the snapshot or the prompt:** no email, phone, documents, visa, passport,
  citizenship, name, or signed URLs (CV, video). A test guards it.
- Every text the user reads goes through `_()` and has a Brazilian Portuguese translation.

---

## Architecture: ports and adapters

```
src/peao_bilingue/
├── domain/
│   │                  # one module per subdomain: entities (pydantic, no SQL) + ports (ABCs)
│   ├── jobs.py        # Job, JobSummary, Skill, JobStatus, ListedJob, Posting · JobRepository
│   ├── searches.py    # Search · SearchRepository
│   ├── profile.py     # Profile, profile_hash · ProfileSource, ProfileRepository
│   ├── analysis.py    # JobAnalysis, SavedAnalysis, Message, LLMResponse · LLMProvider,
│   │                  #   AnalysisRepository
│   ├── collection.py  # Run, RunStatus, Trigger · JobSource, ManualSession, Lock,
│   │                  #   RunRepository
│   ├── notifications.py  # Notifier
│   ├── schedule.py    # ScheduleStatus · Scheduler
│   ├── repository.py  # Repository = the five repository ports together (UI and composition)
│   ├── privacy.py     # remove_contact_data: emails, links, phones, CPF
│   └── errors.py      # SessionExpired, HumanChallenge, CollectionError, InvalidAnalysis...
├── application/
│   ├── profile.py     # the pasted CV and the notes, without contact data
│   ├── collect.py     # run_collection: search → filter → save → notify (no LLM), with a lock
│   ├── analysis.py    # on-demand analysis: prompt, validation and retries, provider-agnostic
│   └── filters.py     # a search's keywords / exclude / sources
├── adapters/          # importing the package registers them all in the factories
│   ├── sources/       # api.py (ApiSource base), remotive, remoteok, arbeitnow, himalayas,
│   │                  #   weworkremotely, html.py; vanhack/ (Playwright: auth, listing, detail,
│   │                  #   profile, selectors, session, source)
│   ├── llm/           # anthropic, ollama, openai, gemini
│   ├── notification/  # formatting, email, whatsapp
│   ├── scheduling/windows.py   # Task Scheduler through PowerShell
│   └── persistence/   # sqlite/ (tables, database, legacy, one file per aggregate and
│                      #   SQLiteRepository joining the five), lock.py (filelock)
├── factories.py       # Registry[T] + sources / llms / notifiers
├── composition.py     # composition root: the only place that wires ports to adapters
├── config.py          # Settings: config.json + the Windows vault + .env (fallback)
├── i18n.py            # `_()` and the locale; locales/pt_BR.py has the translations
├── texts.py           # user-facing text shared by the CLI and the window
├── launcher.py        # the .exe's entry point: window or CLI
├── ui/                # CustomTkinter: app, async executor, tabs, widgets, presentation,
│                      #   onboarding (the first-run guide)
└── cli.py             # peao login | check | run | searches | schedule | adapters
```

**Configuration:** precedence `config.json` > vault > environment variables > `.env` > default.
The window writes to `data/config.json` (public) and to the vault (fields in `SECRETS`) through
`config.save()`, which also updates `settings` **in place**: several modules do
`from peao_bilingue.config import settings`, and swapping the object wouldn't reach them.
`PEAO_DATA_DIR` changes the data folder (default `data`; `PEAO_DADOS` still works); the tests
point it at a temp folder and swap the keyring for an in-memory one **before** importing the
project, so they never touch the real configuration.

**Window (`ui/`):** Tkinter is synchronous and the core is async (Playwright). Coroutines run on
an asyncio loop in a thread of their own (`AsyncExecutor`); results come back through `after()`
(`track`) and logs through a queue (`LogQueue`). **No widget is touched outside the window's
thread**: callbacks coming from the worker (e.g. the login's `report`) only queue. Verified on
Windows: Playwright works on that thread (Proactor loop) without freezing the window. The LLM and
notice forms are built from the `fields` each adapter declares, with the widget type inferred
from `Settings` itself. Sources with a manual login implement the `ManualSession` port and get
login/check buttons automatically. Tabs have an internal id (`jobs`, `runs`...) and a translated
title. `peao-ui` is a gui-script: it opens with no console.

**Jobs tab (2026-10-17):** the table fills the tab and shows, as colored chips (one color per
search, `presentation.search_colors`), the keywords of the job's searches that show up in it
(`filters.matched_keywords`); no description. It is **drawn on a `tk.Canvas`**
(`ui/tabs/jobs/table.py`): a `ttk.Treeview` only colors whole rows, and a row of CustomTkinter
widgets per job took 45 s for 500 jobs (the Canvas: 0.24 s). A click opens the job's dialog
(`ui/tabs/jobs/dialog.py`) **inside the window**, placed over the tab (not a `CTkToplevel`, for
the same reason as the guide), with the analysis, the LLM/profile pickers, Analyze, Open and the
status buttons; Esc, ✕ or a click outside closes it. Generated mouse and key events don't reach
the hidden test window: the tests call the click handler and check the Esc binding.
**Selection and status colors (2026-10-18):** the first column is a box per row (the header's
ticks every listed job); a click on the box only toggles it, elsewhere it opens the dialog. A
refresh keeps the boxes of jobs still listed. "Descartar selecionadas" asks (`App.confirm`) and
calls `JobRepository.change_statuses` (one transaction, all or none). Each `JobStatus` carries
its display color (`JobStatus.color`, light/dark pair): the Status column draws it as a chip and
the "Mark as" buttons use it as their border. A click on the Published header cycles ↕ (the
repository's order, newest found first) → ▼ newest at the source → ▲ oldest → ↕, sorted in the
table (`JobTable.sort_by_published`), kept across refreshes; jobs with no date go last.

**Dependency rule:** `domain` imports nothing from the project except `i18n` (a leaf utility for
user-facing error messages); `application` only knows `domain`; adapters implement ports; only
`composition.py`, `cli.py` and `ui/` know concrete adapters.

**Ports are `abc.ABC`:** a class that forgets an abstract method can't even be instantiated (a
test proves it).

**Registry factories:** each adapter registers itself with `@sources.register("name")` (or
`llms`, `notifiers`). `factories.sources.create("name", **config)`; a wrong name raises
`UnknownName` listing the available ones. A new adapter = a new module + an import in
`adapters/__init__.py`, nothing else.

**Job identity:** `source:external_id` (`vanhack:12030`): ids from different sites collide. The
whole job is kept as JSON (`JobTable.data`); each source's own fields go in `Job.extras`.

**Duplicates across sources** (2026-10-13): the same job shows up on several sites (Lemon.io
posts on Remotive, Himalayas and WWR). `Job.fingerprint()` = normalized company + title
(lowercase, no accents, only letters and digits: "Full-stack" = "full stack", "Lemon.io" =
"lemon io"). Only across **different sources**: within one source, equal title and company are
different jobs (Bjak has "Frontend Engineer" in Singapore and in Ireland, on Remote OK). No
company means no fingerprint: VanHack never publishes the company, and the title alone would
merge unrelated jobs. The duplicate is **saved** with `duplicate_of=<the original's key>` (or it
would be detailed again on every collection, using up the per-source limit), but it isn't new,
isn't notified and isn't listed; the original's detail shows "Também em <source>: <link>".

**Search text** on the Jobs tab (`list_jobs(search_text=)`, `Job.matches`): every word has to
appear in the title, company, location, skills or description, ignoring accents and case.

**Collection (`run_collection`):** search → filter → save → notify; **calls no LLM**. Sources run
one at a time (one browser open at a time). A failing source doesn't stop the others: it becomes
"Partial failures" on the run; everything fails only if every source fails. The Runs tab's
picker collects all enabled sources or **only one** of them (2026-10-17; `build_services(sources=)`,
like `peao run --source`); each run records its sources (`Run.sources`, a JSON column that is
NULL in older rows, read as `[]`) and the history shows them. Each source that
implements `ProfileSource` reads and saves **its own profile** on every collection; if reading
fails, its last saved one stays. **Notices** (a digest of the new jobs: title, source, link) only
with `notify=True`: the scheduled collection and `peao run --notify`; the button's doesn't
notify, because whoever asked is watching. A failed notice also becomes "Partial failures" (the
jobs stay saved). The Windows notification (`windows`) is on by default, with nothing to set
up; email and WhatsApp start off: turned on before being filled in, every notice would fail. **Problem notices** (`Notifier.notify_problem`, 2026-10-13): with
`notify=True`, a failing source (or the whole run, when it wasn't a source) is reported too:
"VanHack: The VanHack session expired…". Without it an expired session made the scheduled
collection fail every day in silence. It repeats on every collection until fixed, on purpose:
it's the reminder. A failed *notice* is not reported as a problem (that channel is the broken
one).

**Profile per source:** the profile on VanHack isn't the one on LinkedIn. `Profile.source`; the
repository saves, deduplicates and keeps the history **per source**.

**The pasted CV** (2026-10-17): the profile of source `manual` (`MANUAL_SOURCE`), the one for
jobs whose source reads none (the public APIs) and for anyone without a VanHack account.
`analyze_job` tries the job's source, then `manual`. Pasted on the Profile tab or imported
(`adapters/documents.py`: `.pdf` through `pypdf`, `.txt`/`.md` in UTF-8 or cp1252); before saving,
`domain/privacy.remove_contact_data` takes out emails, links (they carry names), CPF and phone
numbers (≥ 9 digits, so "2019-2023" stays) and the lines left with only separators. A name or an
address can't be found by a pattern: the screen asks the user to check. The **notes**
(`profile_notes.md`) are edited on the same tab and cleaned the same way. An unsaved paste
survives a refresh (`edit_modified`); the tab starts on a source with a saved profile, else on
the CV, until the user picks one.

**The first-run guide** (`ui/onboarding.py`, 2026-10-17): six steps (welcome and privacy, a
first search, sources, the CV, the LLM and its key, the daily collection + the Windows notice)
**in the place of the tabs**, not in a `CTkToplevel` (Windows may open it behind the window).
Shown when `needs_onboarding`: `onboarding_done` is false **and** there's no search and no
profile, so whoever set the app up before the guide existed never sees it. Each Next checks its
step (`Step.check` raises `ValueError`); **nothing is saved until Finish**, which saves the
search, the CV (cleaned), the settings and `onboarding_done`, and schedules the task off the
window's thread. Skip only saves `onboarding_done`. Email/WhatsApp turned on earlier are kept;
"collect every day" off leaves an existing schedule alone. Settings → "Run the setup guide
again". The UI tests' `window` fixture starts with `onboarding_done = True`; `new_user_window`
doesn't.

---

## Text and translations

- **Every user-facing string goes through `_()`** (`peao_bilingue.i18n`): the English text is the
  key, `locales/pt_BR.py` maps it to Brazilian Portuguese, and a missing entry falls back to
  English. Placeholders use `str.format` names (`_("Run {id}").format(id=...)`) so a translator
  can reorder them. `LOCALE` is fixed at startup (`pt_BR`); labels built at import time (adapter
  labels, registry kinds) are translated once.
- **Logs stay in English**, untranslated: they are for whoever maintains the app.
- **The LLM prompt is in English** and asks for the answer in the user's language
  (`i18n.response_language()`, "Brazilian Portuguese"). The readable profile (`to_text`) is in
  English too.
- `tests/test_i18n.py` checks that every `_()` literal has a translation, that no translation is
  unused, that placeholders match, and that **no accented Portuguese** appears in `src/` outside
  `locales/` (the product name "Peão Bilíngue" is the exception; text matched on a third-party
  page, like a Cloudflare message, is written with `\u` escapes).
- **The tests run in English** (`i18n.LOCALE = "en"` in `conftest.py`), so assertions read the
  English text.
- Don't call `_()` on something that isn't a literal: the coverage test can't see it.

---

## Migration from the Portuguese names (2026-10-17)

Up to 2026-10-16 the database tables and columns, the enum values, the keys inside the JSON
columns, the settings and the CLI commands were in Portuguese. The update migrates by itself:

- **Database** (`persistence/sqlite/legacy.py`, on the first open, when table `vaga` exists):
  backs up the file as `peao.before-english-<date>.db` (SQLite backup API, safe with WAL),
  creates the new tables, copies every row translating columns, enum values (`nova` → `new`,
  `agendado` → `scheduled`, `erro` → `error`...) and the JSON keys (`JOB_KEYS`, `ANALYSIS_KEYS`,
  `PROFILE_KEYS`; VanHack's question labels in `other_fields` are kept verbatim), recomputes
  each profile's `content_hash` (so the next reading isn't a fake change), renames Himalayas
  keys `sem-empresa/` → `no-company/`, and drops the old tables, all in one transaction. The
  readable profile text and old run errors stay in Portuguese until they're rewritten.
- **Settings** (`config.migrate_legacy_names`, on every start, cheap): old names in
  `config.json` and `.env` (`fontes_habilitadas`, `llm_analise`, `HIMALAYAS_PAIS`...) are
  renamed in place; a new name already present wins.
- **API caches** with the old keys simply count as misses.
- **CLI:** `run --agendado` is still accepted (hidden) as `--scheduled`, for tasks registered
  before the change.
- **Scheduled task:** renamed to "Peao Bilingue - daily collection". `schedule()` removes the old
  "Peao Bilingue - coleta diaria" (two tasks would collect twice); `status()` still finds it; and
  the window, on startup, calls `upgrade_legacy_task()` (off the window's thread), which
  re-registers it under the new name and command at the same time.
- **Files:** `coleta.log` → `logs/collection.log`, `execucao.lock` → `run.lock`; the old ones are
  just left behind.

---

## Windows notifications (2026-10-17)

- `adapters/notification/windows_toast.py`, notifier `windows`, on by default. A toast needs an
  AppUserModelID; the app isn't packaged, so it registers `PeaoBilingue.App` under
  `HKCU\Software\Classes\AppUserModelId` (DisplayName "Peão Bilíngue", per user, no admin,
  idempotent) and shows the toast through the WinRT API that PowerShell 5.1 exposes: no new
  dependency, and it works from the window, the CLI and the scheduled task (it runs in the user's
  session). PowerShell helpers live in `adapters/powershell.py`, shared with the scheduler.
- The XML is built with `xml.sax.saxutils` (escaped) and passed as a single-quoted PowerShell
  literal. A single job opens on click (`activationType="protocol"` with the job's URL); several
  are listed (3 lines, the last one "+N").
- Verified on 2026-10-17 through a temporary scheduled task (outside the Claude container):
  `ToastNotificationManager.History.GetHistory('PeaoBilingue.App')` had the toast, accents
  intact. A toast from a process inside the Claude container might not count as the user's.

---

## Logs and updates (2026-10-17)

- **`logs.py`:** `log_to_file(name)` sends the root logger to `data/logs/<name>.log` (rotating,
  1 MB × 3): `app.log` from the window, `collection.log` from `run --scheduled`. Entry points
  also call `record_uncaught_exceptions()`: `sys.excepthook`, `threading.excepthook` and
  `faulthandler` (to `crash.log`, a file kept open for the whole process), installed once. The
  window overrides `report_callback_exception` (Tk would print to a console the app doesn't
  have) and logs every error it shows. Tests patch the hooks: they are process-wide.
- **Settings → About and support:** the version, the update switch, "open the logs folder"
  (`os.startfile`) and the project page.
- **The CLI in the .exe:** a GUI .exe has no stdout, so `launcher.attach_parent_console()`
  attaches to the terminal it was started from (`AttachConsole(-1)`, UTF-8 code page, `CONOUT$`).
  Under Task Scheduler there's no parent console and printing stays silent.
- **Version:** `peao_bilingue.__version__` from the package metadata (the spec copies
  `peao-bilingue`'s metadata, or the .exe would show 0.0.0); in the window title.
- **Updates:** the `ReleaseFeed` port (`domain/updates.py`), `GitHubReleases` adapter
  (`GET /repos/{repo}/releases/latest`, no token; 404 = none or private repo; offline = None),
  `application/updates.newer_release`. The window checks once when it opens (if
  `check_for_updates`) and shows a banner with "Baixar"/"Depois". `update_repository` lets a
  fork point at itself. Nothing is downloaded or installed automatically: that needs a signed
  installer first.

---

## Scheduled collection and concurrency

- **The task** is registered through PowerShell 5.1 (`Register-ScheduledTask`; `schtasks` has no
  `-StartWhenAvailable`): daily, runs when the PC turns on if the time went by while it was off,
  `-MultipleInstances IgnoreNew`, a 2 h limit. It runs `.venv\Scripts\pythonw.exe -m
  peao_bilingue.cli run --scheduled` (collects and reports new jobs and problems; no LLM), or
  `PeaoBilingue.exe run --scheduled` in the .exe (see "Executable"), with the **project folder as
  the working directory**: `data/`, `.env` and `profile_notes.md` are relative to it. ASCII task
  name: PowerShell 5.1's output comes in the console's code page.
- **The script always has `$ErrorActionPreference = 'Stop'` and `exit 0` at the end.** Without
  it, `Get-ScheduledTask -ErrorAction SilentlyContinue` with a missing task exits with code 1 and
  no message. 5.1's `ConvertTo-Json` serializes dates as `\/Date(...)\/`: dates are formatted as
  ISO inside the script. `LastRunTime` 1999-11-30 = never ran; `LastTaskResult` 0 = ok, 1 = our
  failure, 267009 = running, 267011 = never ran.
- `pythonw` has no console: with `--scheduled`, the log goes to `data/logs/collection.log`
  (rotating, 1 MB × 3; see "Logs and updates").
- **One run at a time, across processes:** `FileRunLock` (`filelock` on `data/run.lock`). The same
  `FileLock` instance is **reentrant**, so every acquisition uses a new instance, or a second run
  in the same process would get in. Verified on Windows: app/CLI and the scheduled task exclude
  each other.
- **Orphan runs:** holding the lock, no other run is alive; anything still listed as running
  belongs to a process that died (app closed halfway, PC turned off, the time limit) and is
  marked as an error when the next run starts.
- SQLite in **WAL** with a 5 s `busy_timeout`: the window reads while the task writes.
- **PC suspended during a collection:** the process comes back with the PC and Playwright fails
  with `ERR_NETWORK_IO_SUSPENDED`; the run is recorded as an error (seen on 2026-10-06). No
  `-WakeToRun` on purpose: waking the user's laptop is intrusive.

---

## Executable (Phase 8)

- `packaging/peao_bilingue.spec`, built with
  `uv run --group packaging pyinstaller packaging/peao_bilingue.spec --noconfirm` →
  `dist/PeaoBilingue/PeaoBilingue.exe` (~170 MB, mostly Playwright's node driver). PyInstaller is
  in the `packaging` group, outside the normal `uv sync` and CI.
- **One .exe for both roles** (`launcher.py`): no arguments opens the window, arguments run the
  CLI. It is a GUI app (`console=False`); the scheduled task runs `PeaoBilingue.exe run
  --scheduled` (`collection_command()` picks between that and the project's `pythonw` by
  `sys.frozen`).
- **Data in `%LOCALAPPDATA%\PeaoBilingue`** when frozen (`config.base_dir()`): `data/`, `.env`,
  `profile_notes.md` and `artifacts/` come from there, not from the .exe's folder or the working
  directory. In the project, everything stays relative to the current folder.
- Added by hand in the spec: `peao_bilingue`'s submodules (adapters are imported by the
  registry), the `keyring` backends + metadata (found through entry points), `win32ctypes.core`
  and SQLAlchemy's `sqlite` dialect. Playwright's Chromium is **not** bundled: it uses the
  installed Chrome. The spec isn't type-checked: a name that looks like a word (`datas` is
  PyInstaller's argument) must stay as it is.
- **Gabriel's installation (2026-10-13):** the program in `%LOCALAPPDATA%\Programs\PeaoBilingue`,
  data in `%LOCALAPPDATA%\PeaoBilingue` (migrated from the project's `data/`), a Start menu
  shortcut and the 08:00 task calling the .exe. The project's `data/` is only a development copy.
- **Updating it (2026-10-18):** `powershell -ExecutionPolicy Bypass -File packaging\deploy.ps1`
  runs the tests, builds, and swaps the install folder, keeping the old one as
  `PeaoBilingue.previous` (`-Rollback` restores it). It refuses while the installed .exe runs
  (the window or a collection) unless `-Force`; `-SkipTests`, `-BuildOnly`, `-InstallDir`.
  ASCII only (PowerShell 5.1 reads a BOM-less script in the ANSI code page). Gabriel runs it from
  his own terminal: from the agent's shell the install would land in the MSIX container (below).
  Verified on 2026-10-18 with `-InstallDir` pointing at a temp folder.
- **Claude desktop is MSIX:** a **new** folder created in `AppData` by a process started from the
  agent's shell (the .exe included) goes to `%LOCALAPPDATA%\Packages\Claude_*\LocalCache\...`,
  which only the agent sees. That's how the first migration "vanished": the scheduled task
  opened an empty database and exited with code 0 and no log. To install, update or really test
  the .exe, use a **temporary scheduled task** (it runs outside the container) and remove it
  afterwards.
- **A bug the .exe found (it was in the project too):** when VanHack's `__aenter__` failed after
  opening the browser (expired session, challenge), `async with` didn't call `__aexit__` and
  Chrome + the driver held the process open: a scheduled collection with an expired session
  never ended (until the 2 h limit). Now `__aenter__` closes everything before re-raising.

---

## Analysis with LLMs

- **On demand:** `analyze_job(key, provider, jobs=, profiles=, analyses=, profile_source=None,
  notes="")`, called by the Analyze button on the Jobs tab. It uses the profile of the **job's
  source**; the profile picker chooses another source's (the way for sources with no profile,
  like the public APIs). No profile read → `MissingProfile`, before spending on the LLM. The
  analysis keeps `profile_id`: when the same source gets a newer snapshot,
  `SavedAnalysis.profile_outdated` and the screen suggests analyzing again; there's no automatic
  re-analysis.
- The provider only translates the call (`generate_json(system, messages, schema)` → JSON text or
  a refusal). **Validation and retries live in `application/analysis.py`**, the same for all.
- **No provider enforces `minItems`/`maxItems` on the server.** On Anthropic, `transform_schema`
  (the same one `messages.parse` uses) **moves** those limits and `minimum`/`maximum` into the
  schema's `description`. "Exactly 20 questions" is guaranteed by Pydantic validation on the
  client + up to 3 attempts sending the error back to the model.
- **Anthropic:** `beta.messages.create` with `output_config.format` (the transformed schema).
  Forced tool use (`tool_choice` `any`/`tool`) returns **400** on the current models; don't use
  it. On the models that support it (Sonnet 5.5, Opus 5.5/5, Fable 5.1), the server-side refusal
  fallback goes along (`fallbacks: "default"` + beta `server-side-fallback-2026-07-01`). Check
  `stop_reason == "refusal"` before reading: a refusal arrives as HTTP 200.
- **Ollama:** `format` gets the JSON Schema (it becomes a grammar; the output already fits). Its
  default context is small and **truncates the prompt silently**: `num_ctx` is always explicit
  (`OLLAMA_CONTEXT`; 8192 fits 6 GB with an 8B model). Down, or the model not downloaded, become
  `ProviderUnavailable` with the instruction (`ollama serve` / `ollama pull`).
- **OpenAI:** `chat.completions.create` with a strict `response_format` (`to_strict_json_schema`
  is the converter `parse` uses). Don't use `parse`: it validates inside the SDK and swallows the
  text the application sends back to the model on retry. A refusal comes in `message.refusal`.
- **Gemini:** the assistant is called `"model"`; a safety block **doesn't** raise: it arrives as
  a response with no text and `finish_reason` `SAFETY`/`PROHIBITED_CONTENT`/`BLOCKLIST`.
- **OpenAI and Gemini have no default model** (`OPENAI_MODEL`/`GEMINI_MODEL` are required): the
  catalog changes and a made-up name would only fail at run time.
- **Before writing a new adapter:** check the API in the installed SDK (introspection) and in
  the official docs. Never guess a method or parameter name.
- `profile_improvements` points at concrete items of the profile, not generic advice. Input: the
  profile text + `profile_notes.md` (optional) + the job as JSON.

---

## VanHack adapter: what the real site showed

**Login:** `app.vanhack.com/login` is a 404. Login lives on `auth.vanhack.com`, is
**passwordless** (magic link, Google or LinkedIn) and has Cloudflare Turnstile and a honeypot
(the "Website" input: never touch it). `uv run peao login` opens a visible Chrome; with email,
**paste the link in the open window**, don't click it in the email client. The session is saved
in `data/state.json`.

**Session:** `/jobs` is **public**: loading it proves nothing. The proof is `/profile`, which
starts the OIDC flow without authentication. The `.AspNetCore.Antiforgery.*` cookie exists even
logged out.

**Browser:** the installed Chrome (`BROWSER_CHANNEL=chrome`), not the bundled Chromium:
Cloudflare rejects unusual browsers. The logged-in app is **not** blocked under headless
Playwright.

**Listing:** search by URL (`/jobs/{slug}-jobs`), which really filters. **Infinite scroll** (10
cards on the first render, 25 after scrolling). A search with no results shows "You're seeing 0
jobs" and returns `[]`. Rendering is sometimes slow: it waits for a card **attached to the DOM**
(not "visible") and reloads once before giving up. Links are scoped to `div.vh-cards`: the job
page has minicards of **other** jobs.

**Job:** VanHack **never publishes the company** ("our hiring partner"): `company` is `None`.
Skills come as `span.vh-jd-skill` chips with the years in a `<small>`.

**Profile (`/profile`):** an editable form; values in `input_value()`, `.vh-dd` dropdowns, checked
radios and checkboxes: `inner_text()` isn't enough. Blazor ids (`0HNP0Q2EPN2A7`,
`vhdd-<guid>-button`) **change on every render**: never use them as selectors. Structure:

```
section.pf-section > h5.pf-section-title + div.pf-card
  div.pf-field > label.pf-label + (div.vh-dd | input.form-control | radios | checks | pf-target-row)
  div.pf-skill-group > .pf-skill-group-title + div.pf-skill-row
  div.pf-lang-row > .pf-lang-select + .pf-lang-level
  div.pf-exp > a.pf-item-title + .pf-item-sub + div.pf-role(.pf-role-head/.pf-role-desc/.pf-chips)
```

The snapshot keeps **every** question/answer pair (it survives a question being reworded). There's
no bio field: the "headline" is the answer to "Which role best applies...". The Intro Video card
has the video's signed URL and the spoken transcript: only "Level: X" is used.

Selectors **only** in `selectors.py`, documented. Real anonymized fixtures in
`tests/fixtures/vanhack/` (its README explains the anonymization and what to audit).

**Screenshots on request** (2026-10-17): the Runs tab's "Save a screenshot of each search" (or
`peao run --capture`) sets `JobSource.capture_to` (through `build_services(capture_to=)`) to
`artifacts/captures/<timestamp>/`; after each search, scrolled to the end, VanHack saves a
full-page PNG + HTML there (`debug.dump`, label made file-safe). Only the search listings, not
job pages; only sources that read web pages (the APIs keep their raw response in
`data/cache/`); never in the scheduled run. A failed capture is only logged. The window opens
the folder when the run ends.

---

## API sources

No login and no profile: a job from them is analyzed with the profile picked in the selector
(the default falls back to the first saved profile, VanHack's today). HTML descriptions become
text with one line per paragraph (`adapters/sources/html.py`). Fixture = a real response saved in
`tests/fixtures/<source>/`; the tests use `FakeApi` (in `fakes.py`, over
`httpx.MockTransport`), with no network, and count the calls.

**The `ApiSource` base** (`adapters/sources/api.py`), three ways to query:
- **the whole list** (`params()`): one call per collection, and each term is filtered locally
  against the same text the search filter uses: Remotive, Remote OK, Arbeitnow;
- **per term** (`params_for_term()`): the API searches, one call per term, with `pause_s`
  between real calls: Himalayas;
- **a few fixed queries** (`queries()`): the list comes in parts: We Work Remotely, one feed per
  category. `decode()` swaps JSON for another format (RSS).
A cache per query in `data/cache/<source>[-<hash>].json` (`validity_s`, 6 h by default; only for
the same query); `detail` doesn't call the API. Each source defines `url`, the parameters,
`brand` (how it asks to be credited) and `convert()`. A 429 becomes a readable
`CollectionError`.

**Remotive** (`GET https://remotive.com/api/remote-jobs?category=software-dev`). Terms, in the
response's own legal notice: link the job on Remotive **and** credit Remotive as the source; **at
most ~4 calls a day** (more than 2 a minute get blocked); data is 24 h behind; don't republish on
other job sites. Hence **one call per collection** (the category comes whole, 17 jobs on
2026-10-07, and each term is filtered locally) and a **6 h cache** in `data/cache/remotive.json`.
The API ignored `limit` in a real test. Salary is `""` when not given. The listing already has
the whole job.

**Remote OK** (`GET https://remoteok.com/api`). Terms in the response's first item: link the job
on Remote OK (no `nofollow`) and credit "Remote OK"; don't use the logo. No declared limit; the
base makes one call per collection. It returns the ~100 latest jobs from **every field**, with a
**shortened** description (the full text only on the site, which isn't scraped). Three traps:
- every description ends with an anti-spam sentence ("Please mention the word **X** and tag R…")
  whose token is **the caller's IP address** in base64: `clean_description` removes the sentence
  and any loose token; in the fixture the token is the one for `2001:db8::1` (documentation);
- UTF-8 read as Latin-1, from the server itself: `fix_encoding`;
- an escaped `<img>` with a base64 image in the middle of the text, sometimes cut: removed.
Salary in `salary_min`/`salary_max` (0 = not given); `location` is `""` when the job doesn't say.

**Arbeitnow** (`GET https://www.arbeitnow.com/api/job-board-api?visa_sponsorship=true`). Terms
(`meta.terms` in the response and section 11 of the site's terms): a free API, "don't abuse it",
**link back** to Arbeitnow; access may be revoked. A limit of 50 calls (`X-RateLimit-Limit`).
Only jobs **with visa sponsorship**: the relocation path, like VanHack; the default list is local
jobs in Germany, many in German. On 2026-10-07: 312 jobs in a single page. The API **ignores**
`remote=true`. The description comes with **escaped** HTML, sometimes only partly (`&lt;p&gt;`
inside real tags): `description_as_text` converts and, if a closing tag is left, converts again.
`created_at` is epoch.

**Himalayas** (`GET https://himalayas.app/jobs/api/search?q=<term>&country=BR&sort=recent`).
Terms (https://himalayas.app/api): link the job on Himalayas **and** credit Himalayas; don't
republish on other sites; abuse gets a 429. **At most 20 jobs per call** and more than 5,000 in
the whole list, so it searches **per term**: one call per search keyword, a **2 s pause** between
real calls and a **12 h cache per term** (the data changes every 24 h). `country=BR`
(`HIMALAYAS_COUNTRY`) brings only jobs open to Brazil or worldwide; without it, 3 out of 18 fit.
The id is `company/slug` (`no-company/slug` without a company slug): the slug alone repeats
across companies. `locationRestrictions` becomes the location (up to 3 countries; above that,
the count) and stays whole in `extras["countries"]`.

**We Work Remotely** (RSS: `https://weworkremotely.com/categories/<category>.rss`). The feed page
says: *"Anyone can use the feed, all we ask is that you attribute the links back to We Work
Remotely."* The general feed (`remote-jobs.rss`) only has the ~90 latest from **every** field (it
was missing 38 of the 57 programming jobs), so it's the back-end, full-stack and front-end feeds:
**3 calls per collection**, a 2 s pause, a 6 h cache. The title comes as "Company: Role";
`skills` as "A, B, and C". WebFetch gets a 403 from their Cloudflare, but honest access (our
User-Agent) gets a 200: no disguise. XML through the stdlib's `ElementTree` (Python's expat
already guards against entity expansion).

---

## Brazilian sites (Phase 6): what the terms allow

Investigated on 2026-10-08, before any code, as the roadmap says (terms read on each site, with
honest access):

| Site | Official API/feed | What the terms say | Verdict |
|---|---|---|---|
| Gupy | only for client companies | forbids "aggregating, copying or duplicating parts of Gupy [...] including job opportunities" | **no** |
| Remotar | no | forbids "mechanisms, software or scripts"; copying by "Robot/Crawler" "expressly forbidden" | **no** |
| GeekHunter | no | forbids "scraping, spiders, crawlers, bots" without prior written authorization | **no** |
| Trampos | no | the same clause as Remotar (scripts and robots forbidden) | **no** |
| Programathor | no (`/jobs.rss` returns 500) | **silent** about automated access; `robots.txt` allows the job pages | **Gabriel decides** |

Programathor would need reading the HTML pages (there's no official alternative): the terms
don't forbid it, but don't authorize it either. On hold until Gabriel decides.

---

## Roadmap

One phase at a time; at the end of each: `uv run pytest`, `uv run ruff check .`, `uv run mypy`,
commit and push.

- [x] **Phase 1 — Hexagonal core.** Domain, ports, factories, composition; VanHack and Anthropic
      as adapters; FastAPI/APScheduler removed; the listing bug fixed (empty search and slow
      rendering); evidence saved on any reading failure.
- [x] **Phase 2 — LLMs:** Ollama, OpenAI, Gemini; a common contract tested against all four.
      **Still to validate against the real services:** Ollama isn't installed on the machine,
      and OpenAI/Gemini need a key.
- [x] **Phase 3 — CustomTkinter UI:** the tabs; an async executor on its own thread; secrets in
      the vault; the window checked by screenshot.
- [x] **Phase 4 — Windows Task Scheduler:** a daily task from the app or `peao schedule`; a lock
      across processes with `filelock`; SQLite in WAL; orphan runs closed. Verified end to end.
- [x] **On-demand analysis and profile per source** (2026-10-07).
- [x] **Phase 5 — Public APIs:** Remotive, Remote OK, Arbeitnow (Germany with a visa), Himalayas
      (open to Brazil) and We Work Remotely (RSS), over the `ApiSource` base. Terms checked one
      by one; all off by default.
- [~] **Phase 6 — Brazilian sites:** investigated (see above); **waits for Gabriel**.
- [ ] **Phase 7 — LinkedIn/Indeed:** opt-in, off by default, the same rules as VanHack. Their
      terms forbid automation (risk of the account being restricted); if they block, **don't**
      escalate to evasion: the alternative is reading their job-alert emails (IMAP).
- [x] **Phase 8 — `.exe`** with PyInstaller, one folder, no Chromium (see "Executable").
- [x] **Code in English** (2026-10-17): identifiers, comments, docs, the database, settings and
      CLI, with automatic migration; the app stays in Brazilian Portuguese through `_()`.
- [x] **Launch items requested on 2026-10-17:** manual profile + notes in the app (2), a guided
      first run (3), native Windows notifications (4), version + update check (7), an app log +
      "open the logs folder" (8).

Waiting on Gabriel (costs money or needs him): the first real analysis with the Analyze button
(Claude spends credit; Ollama is free but needs installing), a real email notice (fill in SMTP,
turn the channel on in Settings and run `peao run --notify`).

---

## Commands

```bash
uv sync
uv run peao-ui                       # the desktop app
uv run peao login                    # manual login to VanHack (--source for others)
uv run peao check                    # is the saved session still valid?
uv run peao searches                 # list; `searches add NAME kw1 kw2 --exclude x`
uv run peao adapters                 # registered sources, LLMs and notifiers
uv run peao run                      # collect and save; no LLM (analysis is in the app)
uv run peao run --source vanhack     # only one source
uv run peao run --notify             # also report new jobs and problems
uv run peao run --capture            # also save a screenshot + HTML of each search
uv run peao schedule                 # the daily collection's status
uv run peao schedule enable --time 08:00             # or `schedule disable`
uv run pytest
uv run ruff check . && uv run ruff format .
uv run mypy                          # strict on src/ and tests/ (configured in pyproject)
```

## Tests

- All offline: fakes of the ports, in-memory SQLite, an in-memory keyring and a temp
  `PEAO_DATA_DIR` (`conftest.py` sets this up **before** importing the project), in English
  (`i18n.LOCALE = "en"`).
- **Unit × integration** by the `integration` marker (`--strict-markers`: a wrong name fails).
  Integration = a real component outside Python: Playwright's Chromium (every test with the
  `page` fixture is marked by `conftest.py`), a Tk window (all of `test_ui_app.py`), another
  process (the cross-process lock) and PowerShell. The rest is unit (~5 s).
- **CI** in `.github/workflows/ci.yml`, on every PR and push to `main`: `lint` (ruff + mypy,
  Linux; mypy is pinned to `platform = "win32"` so it doesn't depend on the runner), `unit` and
  `integration` (Windows; installs Chromium with a cache keyed by `uv.lock`'s hash). Everything
  with `uv sync --locked`: an outdated `uv.lock` breaks CI on purpose.
- **`--capture=sys` in `pyproject.toml` is required.** pytest's default capture (fd) swaps the
  process's stdout/stderr handles on every phase; Tcl keeps those handles and Windows recycles
  the values, so the next test's window failed to read Tcl's own files (`Can't find a usable
  init.tcl`, `tcl_findLibrary`), at random. Outside pytest, 40 windows in a row open fine.
- With the app open, `uv run` fails to reinstall the project (`peao-ui.exe` in use) when
  `pyproject.toml` changed: use `uv run --no-sync ...` or close the app.

## Lint and typing

- **ruff** with rules beyond the default (bugbear, pyupgrade, async, timezone-aware dates, broad
  `except`, etc., see `[tool.ruff.lint]`). Off on purpose: `E501` (the formatter handles it),
  `RUF001-003` (typographic dashes and quotes in the texts), `PT018`. A `noqa` always says why.
- **mypy `--strict` on `src/` and `tests/`**, with the pydantic plugin (`mypy_path = tests` for
  `fakes`/`builders`/`queries`). CustomTkinter has no types: its widgets are `Any` and the tabs
  may inherit from them (override only in `peao_bilingue.ui.*`).
- SQLModel columns in `order_by`/`.desc()` go through `col(...)`, or mypy sees them as
  `int | None`/`datetime`.
- Messages to the SDKs are typed (`BetaMessageParam`, `ChatCompletionMessageParam`), and an
  optional Anthropic parameter that must not be sent is `omit`, not `**kwargs` built apart, which
  mypy can't check. A test with the real SDK over a local transport (`httpx2`, which the SDK uses)
  proves `omit` doesn't reach the API.
- A name that is both a library's and looks Portuguese (`le=` in pydantic's `Field`, `os`,
  `datas` in the PyInstaller spec) was kept as is in the rename; remember them when renaming in
  bulk again.

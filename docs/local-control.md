# Control a running Linux window

The Linux app exposes a private Unix socket at `data/control.sock`. The packaged
app uses `${XDG_DATA_HOME:-~/.local/share}/peao-bilingue/data/control.sock`.
`PEAO_DATA_DIR` overrides both. The socket is available only while the window is
open, and its file mode is `0600` so only the same OS user can connect.

Use the CLI from the same project directory as the running source app, or set
`PEAO_DATA_DIR` to the same directory for both processes. With the release
bundle, run `./PeaoBilingue/PeaoBilingue control ...` from anywhere.

```bash
uv run peao control state
```

The result is JSON with `ok` and `result`. `result` contains the effective
nonsecret settings, which secrets are configured (booleans only), available
adapter names, searches, the manually entered CV, and profile notes. Treat the
CV and notes as private user data.

Send one JSON object on standard input to `control apply`. The response is JSON;
the command exits nonzero when `ok` is false. For example:

```bash
printf '%s\n' '{"op":"settings.patch","changes":{"enabled_sources":["remotive","himalayas"],"analysis_llm":"ollama"}}' | uv run peao control apply
```

`settings.patch` changes only the named fields. The app validates field names,
types, and adapter names, saves ordinary settings to `config.json`, stores API
keys and passwords in the OS keyring, reloads the shared settings object, and
refreshes the window. Available setting names and current values appear in
`control state`. A `collection_time` change updates the preference only; use
the Runs tab or `peao schedule enable --time HH:MM` to change the systemd timer.

## Searches

```bash
printf '%s\n' '{"op":"search.upsert","search":{"name":"Python remote","keywords":["python","django"],"exclude":[],"sources":["remotive"],"active":true}}' | uv run peao control apply
```

The response includes the assigned `id`. To edit, send `search.upsert` with
that `id` and the complete search. `sources: []` means every enabled source.
To remove one, send `{"op":"search.delete","id":3}`. Read the current state
first so the ID and content are current.

## CV and notes

`profile.set` replaces the manual CV snapshot; `notes.set` replaces the notes
used in analyses. Both take a `text` string. The app removes email addresses,
phone numbers, links, and CPF numbers before saving, just as the Profile tab
does. It cannot reliably remove names or addresses, so review the text.

```json
{"op":"notes.set","text":"I want remote backend roles in Brazil."}
```

`profile.set` creates a new history snapshot only when the cleaned content
changes. These operations do not read profiles from job sites and do not start
collection or an LLM analysis.

## Protocol and boundaries

Each connection sends a single UTF-8 JSON line and receives one JSON line.
Requests and responses are capped at 1 MiB. The operations are `state.get`,
`settings.patch`, `search.upsert`, `search.delete`, `profile.set`, and
`notes.set`. The CLI `control state` sends `state.get`; `control apply` sends
the object read from standard input. Socket handlers queue work onto Tk's
thread, which performs the write and refreshes the panels.

The control channel is Linux only. It does not expose jobs, run collection,
schedule the OS timer, log in to VanHack, or trigger paid LLM analysis. The
existing CLI and UI handle those actions.

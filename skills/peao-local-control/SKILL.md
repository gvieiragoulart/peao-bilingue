---
name: peao-local-control
description: Inspect and update preferences or state in a running Peão Bilíngue Linux window through its local control CLI. Use for settings, searches, CV, or profile notes in the open app.
---

# Peão Bilíngue local control

Read [the control guide](../../docs/local-control.md) for the request format and
path rules. Use `peao control state` to inspect the effective state and available
adapter names before changing it. In a source checkout, run commands from the
same working directory as the open app, or set the same `PEAO_DATA_DIR` for both.

Send one JSON object through `peao control apply` on standard input. Patch only
requested settings. For search edits, reuse the current `id` and send the full
search object; check the returned state afterward. Use `profile.set` and
`notes.set` for user-provided text, and review the cleaned result because names
and addresses are not removed automatically. Never edit `config.json`, the
SQLite database, keyring, or notes file directly while the app is running.

The state response omits secret values. Treat the returned CV and notes as
private. Ask the user for missing secret values; do not infer or search for
them. Deleting a search is permanent, so get explicit authorization for that
particular deletion unless the user already requested it.

The socket works only while the Linux window is open. A changed
`collection_time` does not reschedule systemd; use the existing schedule
command or Runs tab when the user asks to change the actual daily timer.

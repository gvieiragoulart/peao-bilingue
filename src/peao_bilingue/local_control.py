"""Private Unix socket for configuring a running Linux window.

Socket threads only handle bytes. The window drains requests on Tk's thread so
configuration reloads, repository writes, and widget refreshes stay together.
"""

import json
import socket
import socketserver
import stat
import threading
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from queue import Empty, Queue
from typing import Any

from pydantic import ValidationError

from peao_bilingue import config, factories
from peao_bilingue.application.profile import clean_notes, manual_profile
from peao_bilingue.composition import read_profile_notes, save_profile_notes
from peao_bilingue.config import DATA_DIR, SECRETS, Settings, settings
from peao_bilingue.domain.profile import MANUAL_SOURCE
from peao_bilingue.domain.repository import Repository
from peao_bilingue.domain.searches import Search

SOCKET_PATH = DATA_DIR / "control.sock"
MAX_MESSAGE = 1024 * 1024
REQUEST_TIMEOUT = 15.0


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(k, str) for k in value):
        raise ValueError(f"{label} must be a JSON object")
    return value


class ControlService:
    """A narrow, validated set of configuration operations."""

    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: object) -> tuple[dict[str, Any], bool]:
        command = _object(request, "Request")
        op = command.get("op")
        if op == "state.get":
            if set(command) != {"op"}:
                raise ValueError("state.get takes no arguments")
            profile = self.repository.last_profile(MANUAL_SOURCE)
            return {
                "settings": settings.model_dump(exclude=set(SECRETS)),
                "secrets_configured": {
                    name: bool(getattr(settings, name)) for name in sorted(SECRETS)
                },
                "sources": factories.sources.available(),
                "llms": factories.llms.available(),
                "notifiers": factories.notifiers.available(),
                "searches": [s.model_dump() for s in self.repository.list_searches()],
                "manual_profile": profile[1].text if profile else None,
                "profile_notes": read_profile_notes(),
            }, False
        if op == "settings.patch":
            if set(command) != {"op", "changes"}:
                raise ValueError("settings.patch requires changes only")
            changes = _object(command["changes"], "changes")
            if not changes:
                raise ValueError("changes must not be empty")
            unknown = changes.keys() - Settings.model_fields.keys()
            if unknown:
                raise ValueError(f"Unknown settings: {', '.join(sorted(unknown))}")
            validated = Settings.model_validate({**settings.model_dump(), **changes})
            for name, registry in (
                ("enabled_sources", factories.sources),
                ("notifiers", factories.notifiers),
            ):
                if name in changes:
                    for item in getattr(validated, name):
                        registry.class_of(item)
            if "analysis_llm" in changes:
                factories.llms.class_of(validated.analysis_llm)
            config.save(validated.model_dump(include=set(changes)))
            return {"updated": sorted(changes)}, True
        if op == "search.upsert":
            if set(command) != {"op", "search"}:
                raise ValueError("search.upsert requires search only")
            supplied = _object(command["search"], "search")
            unknown = supplied.keys() - Search.model_fields.keys()
            if unknown:
                raise ValueError(f"Unknown search fields: {', '.join(sorted(unknown))}")
            search = Search.model_validate(supplied)
            if search.id is not None and search.id not in {
                item.id for item in self.repository.list_searches()
            }:
                raise ValueError(f"Search {search.id} not found")
            for source in search.sources:
                factories.sources.class_of(source)
            saved = self.repository.save_search(search)
            return {"search": saved.model_dump()}, True
        if op == "search.delete":
            if set(command) != {"op", "id"} or type(command["id"]) is not int:
                raise ValueError("search.delete requires an integer id")
            self.repository.remove_search(command["id"])
            return {"deleted": command["id"]}, True
        if op == "profile.set":
            if set(command) != {"op", "text"} or not isinstance(command["text"], str):
                raise ValueError("profile.set requires text")
            if not command["text"].strip():
                raise ValueError("Profile text must not be empty")
            manual, removed = manual_profile(command["text"])
            if not manual.text:
                raise ValueError("Profile has no text after contact data is removed")
            _id, changed = self.repository.save_profile(manual)
            return {"changed": changed, "contact_data_removed": removed.any()}, True
        if op == "notes.set":
            if set(command) != {"op", "text"} or not isinstance(command["text"], str):
                raise ValueError("notes.set requires text")
            clean, removed = clean_notes(command["text"])
            save_profile_notes(clean + "\n" if clean else "")
            return {"contact_data_removed": removed.any()}, True
        raise ValueError(f"Unknown operation: {op!r}")


@dataclass
class PendingRequest:
    payload: object
    done: threading.Event = field(default_factory=threading.Event)
    response: dict[str, Any] | None = None


class _SocketHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        server = self.server
        assert isinstance(server, _SocketServer)
        try:
            line = self.rfile.readline(MAX_MESSAGE + 1)
            if not line or len(line) > MAX_MESSAGE:
                raise ValueError("Request is empty or too large")
            pending = PendingRequest(json.loads(line))
            server.requests.put(pending)
            if not pending.done.wait(REQUEST_TIMEOUT):
                raise TimeoutError("The window did not answer in time")
            response = pending.response
        except (ValueError, TimeoutError) as failure:
            response = {"ok": False, "error": str(failure)}
        with suppress(OSError):  # The client may leave before the window answers.
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode() + b"\n")


# Windows imports this module through the app, but never starts local control.
# Its socketserver may not define the Unix server class at all.
_UnixServerBase = getattr(
    socketserver, "ThreadingUnixStreamServer", socketserver.ThreadingTCPServer
)


class _SocketServer(_UnixServerBase):  # type: ignore[misc,valid-type]
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, path: Path, requests: Queue[PendingRequest]) -> None:
        self.requests = requests
        super().__init__(str(path), _SocketHandler)


class LocalControl:
    def __init__(self, path: Path = SOCKET_PATH) -> None:
        self.path = path
        self.requests: Queue[PendingRequest] = Queue()
        self.server: _SocketServer | None = None
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists() or self.path.is_symlink():
            mode = self.path.lstat().st_mode
            if not stat.S_ISSOCK(mode):
                raise RuntimeError(f"Control path is not a socket: {self.path}")
            try:
                with socket.socket(socket.AF_UNIX) as probe:  # type: ignore[attr-defined]
                    probe.settimeout(0.2)
                    probe.connect(str(self.path))
            except (ConnectionRefusedError, FileNotFoundError):
                self.path.unlink()
            else:
                raise RuntimeError("Another Peão Bilíngue window is already running")
        self.server = _SocketServer(self.path, self.requests)
        self.path.chmod(0o600)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def drain(self, service: ControlService, refresh: Callable[[object], None]) -> None:
        while True:
            try:
                pending = self.requests.get_nowait()
            except Empty:
                return
            try:
                result, changed = service.handle(pending.payload)
                if changed:
                    refresh(pending.payload)
                pending.response = {"ok": True, "result": result}
            except (KeyError, LookupError, ValueError, ValidationError) as failure:
                pending.response = {"ok": False, "error": str(failure)}
            except Exception as failure:  # noqa: BLE001 - return errors to the client
                pending.response = {"ok": False, "error": str(failure)}
            finally:
                pending.done.set()

    def close(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        if self.thread is not None:
            self.thread.join(timeout=1)
            self.thread = None
        if self.path.exists() and stat.S_ISSOCK(self.path.lstat().st_mode):
            self.path.unlink()


def request(payload: object, path: Path = SOCKET_PATH) -> dict[str, Any]:
    """Send one JSON request to the running window, with no direct file writes."""
    with socket.socket(socket.AF_UNIX) as connection:  # type: ignore[attr-defined]
        connection.settimeout(REQUEST_TIMEOUT + 1)
        connection.connect(str(path))
        connection.sendall(json.dumps(payload, ensure_ascii=False).encode() + b"\n")
        with connection.makefile("rb") as stream:
            line = stream.readline(MAX_MESSAGE + 1)
    if not line or len(line) > MAX_MESSAGE:
        raise ValueError("Invalid response from the window")
    return _object(json.loads(line), "Response")

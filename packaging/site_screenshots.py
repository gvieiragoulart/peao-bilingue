"""Screenshots of the real window for the download site, with demo data.

    uv run --no-sync python packaging/site_screenshots.py

Opens the app's window over an in-memory database seeded with **fictitious** jobs,
searches, analyses and a CV (never the real data/: PEAO_DATA_DIR points at a new temp
folder and the keyring is an in-memory one, both before the project is imported, as in
tests/conftest.py), in Brazilian Portuguese, and saves site/img/<screen>-<theme>.png in
light and dark: the Jobs table, a job's panel with its analysis, the Sources cards and the
LLMs cards.

The capture is PrintWindow on the window's handle, cropped to what DWM draws (no resize
borders), written as PNG with zlib: no Pillow. The window shows on screen for a few
seconds while it runs.
"""

import ctypes
import os
import struct
import sys
import tempfile
import time
import zlib
from ctypes import wintypes
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

os.environ["PEAO_DATA_DIR"] = tempfile.mkdtemp(prefix="peao-site-")

import keyring
from keyring.backend import KeyringBackend


class MemoryVault(KeyringBackend):
    priority = 1

    def __init__(self) -> None:
        super().__init__()
        self.passwords: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, user: str) -> str | None:
        return self.passwords.get((service, user))

    def set_password(self, service: str, user: str, password: str) -> None:
        self.passwords[(service, user)] = password

    def delete_password(self, service: str, user: str) -> None:
        self.passwords.pop((service, user), None)


keyring.set_keyring(MemoryVault())

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))  # the fakes the UI tests use

import customtkinter as ctk
from fakes import FakeReleaseFeed, FakeScheduler
from sqlmodel import create_engine
from sqlmodel.pool import StaticPool

from peao_bilingue import config
from peao_bilingue.adapters.persistence.sqlite import SQLiteRepository
from peao_bilingue.domain.analysis import JobAnalysis
from peao_bilingue.domain.collection import RunStatus, Trigger
from peao_bilingue.domain.jobs import Job, JobStatus, Skill
from peao_bilingue.domain.profile import MANUAL_SOURCE, Profile
from peao_bilingue.domain.schedule import ScheduleStatus
from peao_bilingue.domain.searches import Search
from peao_bilingue.ui import presentation
from peao_bilingue.ui.app import App

OUTPUT = ROOT / "site" / "img"
NOW = datetime.now(UTC)

SEARCHES = [
    Search(name="Backend Python", keywords=["python", "django", "fastapi"]),
    Search(name="PHP / Laravel", keywords=["php", "laravel"]),
    Search(name="TypeScript", keywords=["typescript", "node", "react"]),
]

# fmt: off
# (source, id, title, company, location, mode, salary, skills, days ago, status,
#  searches). Every company is made up.
JOBS: list[tuple[Any, ...]] = [
    ("himalayas", "orbita-labs/senior-backend-engineer", "Senior Backend Engineer (Python/Django)", "Orbita Labs", "Brasil, Argentina, México", "Remote", "US$ 6k–8k /mês", ["Python", "Django", "PostgreSQL", "AWS"], 1, JobStatus.new, ["Backend Python"]),
    ("remotive", "1987345", "Staff Software Engineer, Payments", "Lumen Pay", "LATAM", "Remote", "US$ 120k–150k /ano", ["Python", "FastAPI", "Kafka"], 2, JobStatus.new, ["Backend Python"]),
    ("github", "backend-br/vagas#12873", "[Remoto] Desenvolvedor PHP/Laravel Sênior na Caju Software", "Caju Software", "Remoto", "Remote", "PJ", ["PHP", "Laravel", "MySQL", "Docker"], 0, JobStatus.new, ["PHP / Laravel"]),
    ("vanhack", "18342", "Senior Full Stack Developer (Laravel + Vue)", None, "Toronto - Canada", "Hybrid", "CAD $110k–130k /yr", ["PHP", "Laravel", "Vue.js"], 3, JobStatus.studying, ["PHP / Laravel"]),
    ("jobicy", "110422", "Backend Engineer (PHP)", "Flowly", "Brazil, LATAM", "Remote", "US$ 50k–70k /ano", ["PHP", "Symfony", "Redis"], 6, JobStatus.new, ["PHP / Laravel"]),
    ("getonbrd", "senior-typescript-developer-andes", "Senior TypeScript Developer", "Andes Digital", "Remote (LATAM)", "Remote", "US$ 4.5k–5.5k /mês", ["TypeScript", "React", "Node.js"], 1, JobStatus.new, ["TypeScript"]),
    ("company_boards", "greenhouse:quasar:4412", "Software Engineer III, Platform", "Quasar Bank", "São Paulo, Brazil (Remote)", "Remote", None, ["Python", "Go", "Kubernetes"], 5, JobStatus.applied, ["Backend Python"]),
    ("strider", "8731", "Senior Python Developer", None, "LATAM (100% Remote)", "Remote", "US$ 5k–7k /mês", ["Python", "AWS", "Terraform"], 2, JobStatus.new, ["Backend Python"]),
    ("weworkremotely", "nimbus-health-senior-node", "Senior Node.js Engineer", "Nimbus Health", "Anywhere in the World", "Remote", None, ["Node.js", "TypeScript", "AWS"], 4, JobStatus.new, ["TypeScript"]),
    ("hackernews", "41873211", "Tidewater Robotics | Senior Backend Engineer | REMOTE (Americas)", "Tidewater Robotics", "Remote (Americas)", "Remote", None, ["Python", "Rust"], 8, JobStatus.new, ["Backend Python"]),
    ("himalayas", "brava/fullstack-engineer", "Full-stack Engineer (TypeScript)", "Brava", "Brazil", "Remote", None, ["TypeScript", "Next.js", "PostgreSQL"], 2, JobStatus.studying, ["TypeScript"]),
    ("remoteok", "1093822", "Senior React Engineer", "Pixelforge", "Worldwide", "Remote", "US$ 90k–120k", ["React", "TypeScript", "GraphQL"], 3, JobStatus.discarded, ["TypeScript"]),
    ("arbeitnow", "senior-php-developer-spreeline", "Senior PHP Developer (m/w/d)", "Spreeline GmbH", "Berlin, Germany", "Hybrid", "€70k–85k", ["PHP", "Laravel", "AWS"], 7, JobStatus.new, ["PHP / Laravel"]),
    ("company_boards", "lever:vertice:9f3e", "Senior Backend Engineer, Investments", "Vértice Invest", "Remote - Americas", "Remote", None, ["Python", "Django", "Celery"], 4, JobStatus.new, ["Backend Python"]),
]
# fmt: on

QUESTIONS = [
    "Conte sobre um sistema em Django que você levou para produção. Qual foi o maior desafio de escala?",
    "Como você identifica e resolve um problema de N+1 no ORM do Django?",
    "Quando você escolheria FastAPI em vez de Django REST Framework?",
    "Como você desenha uma API REST versionada sem quebrar clientes antigos?",
    "Como você estruturaria filas e workers para tarefas demoradas?",
    "Que estratégia de cache você usaria para um endpoint muito lido e pouco escrito?",
    "Como você garante idempotência num processamento de pagamentos?",
    "Fale da sua experiência com PostgreSQL: índices, EXPLAIN e locks.",
    "Como você faria uma migração de banco sem downtime?",
    "Que serviços da AWS você já usou em produção, e por quê?",
    "Como você monitora uma API em produção? Que métricas importam?",
    "Conte sobre um incidente que você ajudou a resolver. O que mudou depois?",
    "Como você testa código que depende de serviços externos?",
    "Que critérios você usa numa revisão de código?",
    "Como você lida com um requisito ambíguo vindo do produto?",
    "Já trabalhou com Kafka ou outro sistema de streaming? Como compara com filas?",
    "Como você dividiria um monólito em serviços, e quando não dividiria?",
    "Como você protege dados sensíveis numa API?",
    "Conte sobre uma vez em que você mentorou alguém do time.",
    "Por que você quer trabalhar num time remoto espalhado pelas Américas?",
]

ANALYSES = {
    "himalayas:orbita-labs/senior-backend-engineer": JobAnalysis(
        fit_score=88,
        summary=(
            "Ótimo encaixe: a vaga pede Python e Django em produção, APIs REST e AWS, "
            "exatamente o centro da sua experiência. O ponto de atenção é o volume de "
            "dados: eles citam pipelines com Kafka, que não aparece no seu perfil."
        ),
        preparation=[
            "Revise o ORM do Django em escala: select_related, índices e N+1",
            "Prepare um caso de sistema que você levou da ideia à produção na AWS",
            "Estude o básico de Kafka: tópicos, partições e consumer groups",
            "Leia o blog de engenharia da empresa e anote duas perguntas",
        ],
        questions=QUESTIONS,
        gaps=[
            "Kafka e processamento de streams",
            "Experiência com times em fusos diferentes",
        ],
        profile_improvements=[
            "Mostre no CV o volume que suas APIs atendem (requisições por dia, usuários)",
            "Inclua Django REST Framework e Celery nas habilidades do LinkedIn",
            "Na VanHack, descreva a migração para a AWS com o resultado medido",
        ],
    ),
    "remotive:1987345": JobAnalysis(
        fit_score=64,
        summary=(
            "Encaixe médio: Python e APIs batem, mas a vaga é Staff e espera liderança "
            "técnica em pagamentos, com Kafka e FastAPI em alto volume."
        ),
        preparation=[
            "Organize exemplos de decisões técnicas que você liderou",
            "Revise conceitos de pagamentos: idempotência, conciliação, estornos",
            "Monte um projeto pequeno com FastAPI e filas",
        ],
        questions=QUESTIONS,
        gaps=["Liderança técnica formal", "Domínio de pagamentos", "Kafka"],
        profile_improvements=[
            "Deixe claro no LinkedIn onde você liderou decisões de arquitetura",
            "Cite no CV os sistemas financeiros em que trabalhou",
            "Adicione FastAPI às habilidades, com um projeto de exemplo",
        ],
    ),
    "jobicy:110422": JobAnalysis(
        fit_score=41,
        summary=(
            "Encaixe baixo: a vaga é centrada em Symfony e Redis, que você usou pouco, "
            "e pede contato diário com clientes em inglês."
        ),
        preparation=[
            "Compare Symfony e Laravel: injeção de dependência, Doctrine, eventos",
            "Revise estruturas e casos de uso do Redis",
            "Treine uma apresentação curta da sua carreira em inglês",
        ],
        questions=QUESTIONS,
        gaps=["Symfony", "Redis em produção", "Atendimento a clientes"],
        profile_improvements=[
            "Separe no CV o que foi Laravel e o que foi PHP puro",
            "Mencione experiências com cache, mesmo fora do Redis",
            "Inclua seu nível de inglês no perfil da VanHack",
        ],
    ),
}

CV = """Engenheiro de software backend sênior, 9 anos de experiência.
Principais habilidades: Python (Django, FastAPI), PHP (Laravel), TypeScript, PostgreSQL, AWS.
Experiência: APIs de pagamentos, migração de monólito para serviços na AWS, liderança de
um time de 4 pessoas."""


def last_collection() -> datetime:
    """The daily collection at 08:00: this morning, or yesterday's before then."""
    now = datetime.now().astimezone()
    morning = now.replace(hour=8, minute=0, second=0, microsecond=0)
    return (morning if morning <= now else morning - timedelta(days=1)).astimezone(UTC)


def seed() -> SQLiteRepository:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    repository = SQLiteRepository(engine)
    for search in SEARCHES:
        repository.save_search(search)
    profile_id, _ = repository.save_profile(
        Profile(source=MANUAL_SOURCE, data={}, text=CV, content_hash="demo-cv")
    )
    # The table lists the newest found first: the first row is saved last.
    for row in reversed(JOBS):
        source, external_id, title, company, location, mode, salary = row[:7]
        skills, days, status, searches = row[7:]
        job = Job(
            source=source,
            external_id=external_id,
            url=f"https://example.com/{source}/{external_id}",
            title=title,
            company=company,
            location=location,
            work_mode=mode,
            salary=salary,
            skills=skills,
            published_at=(NOW - timedelta(days=days, hours=3)).isoformat(),
            description=(
                f"{title}. Stack: {', '.join(skills)}. Remote-first team, "
                "async communication, English for daily work."
            ),
            required_skills=[Skill(name=skill) for skill in skills],
        )
        repository.save_job(job, searches)
        if status != JobStatus.new:
            repository.change_status(job.key, status)
        if job.key in ANALYSES:
            repository.save_analysis(
                job.key,
                ANALYSES[job.key],
                provider="anthropic",
                model="claude-sonnet-5-5",
                profile_id=profile_id,
            )
    run = repository.start_run(Trigger.scheduled, ["himalayas", "remotive", "vanhack"])
    repository.finish_run(
        run.model_copy(
            update={
                "status": RunStatus.ok,
                "finished_at": last_collection() + timedelta(minutes=3),
                "listed_jobs": 148,
                "new_jobs": len(JOBS),
            }
        )
    )
    return repository


# --- Capture ---------------------------------------------------------------------------

PW_RENDERFULLCONTENT = 2
DWMWA_EXTENDED_FRAME_BOUNDS = 9
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
dwmapi = ctypes.windll.dwmapi


class BitmapInfoHeader(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


def png(width: int, height: int, bgra: bytes) -> bytes:
    rows = []
    for y in range(height):
        row = bgra[y * width * 4 : (y + 1) * width * 4]
        rgb = bytearray(width * 3)
        rgb[0::3], rgb[1::3], rgb[2::3] = row[2::4], row[1::4], row[0::4]
        rows.append(b"\x00" + bytes(rgb))

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
        + chunk(b"IEND", b"")
    )


def settle(app: App, seconds: float = 0.6) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.update()
        time.sleep(0.03)


def capture(app: App, name: str) -> None:
    settle(app)
    hwnd = int(app.wm_frame(), 16)
    window, frame = wintypes.RECT(), wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(window))
    dwmapi.DwmGetWindowAttribute(
        hwnd,
        DWMWA_EXTENDED_FRAME_BOUNDS,
        ctypes.byref(frame),
        ctypes.sizeof(frame),
    )
    width, height = window.right - window.left, window.bottom - window.top
    screen = user32.GetDC(0)
    memory = gdi32.CreateCompatibleDC(screen)
    bitmap = gdi32.CreateCompatibleBitmap(screen, width, height)
    gdi32.SelectObject(memory, bitmap)
    user32.PrintWindow(hwnd, memory, PW_RENDERFULLCONTENT)
    info = BitmapInfoHeader(
        biSize=ctypes.sizeof(BitmapInfoHeader),
        biWidth=width,
        biHeight=-height,  # top-down rows
        biPlanes=1,
        biBitCount=32,
    )
    pixels = ctypes.create_string_buffer(width * height * 4)
    gdi32.GetDIBits(memory, bitmap, 0, height, pixels, ctypes.byref(info), 0)
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(memory)
    user32.ReleaseDC(0, screen)

    # Only what DWM draws: GetWindowRect includes the invisible resize borders.
    left, top = frame.left - window.left, frame.top - window.top
    crop_width, crop_height = frame.right - frame.left, frame.bottom - frame.top
    raw = pixels.raw
    cropped = b"".join(
        raw[
            ((top + y) * width + left) * 4 : ((top + y) * width + left + crop_width) * 4
        ]
        for y in range(crop_height)
    )
    path = OUTPUT / f"{name}.png"
    path.write_bytes(png(crop_width, crop_height, cropped))
    print(f"{path.relative_to(ROOT)}: {crop_width}x{crop_height}")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    config.save(
        {
            "onboarding_done": True,
            "enabled_sources": [
                "vanhack",
                "himalayas",
                "remotive",
                "github",
                "company_boards",
                "getonbrd",
            ],
        }
    )
    scheduler = FakeScheduler()
    scheduler.current = ScheduleStatus(
        time="08:00",
        state="Ready",
        next_run=last_collection() + timedelta(days=1),
        last_run=last_collection(),
        last_result=0,
    )
    app = App(repository=seed(), scheduler=scheduler, release_feed=FakeReleaseFeed())
    app.geometry("1280x800+40+40")
    featured = "himalayas:orbita-labs/senior-backend-engineer"
    try:
        for mode in ("light", "dark"):
            ctk.set_appearance_mode(mode)
            app.show("jobs")
            jobs = app.panels["jobs"]
            jobs.filters.status.set(presentation.all_label())
            jobs.refresh()
            capture(app, f"jobs-{mode}")
            jobs.open_job(featured)
            capture(app, f"analysis-{mode}")
            jobs.dialog.close()
            app.show("sources")
            capture(app, f"sources-{mode}")
            app.show("llms")
            capture(app, f"llms-{mode}")
    finally:
        app.close()


if __name__ == "__main__":
    main()

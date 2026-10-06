import asyncio

import pytest

from vanhack_watcher import pipeline, scheduler
from vanhack_watcher.config import settings


def test_agenda_o_cron_configurado():
    agendador = scheduler.criar_scheduler()
    job = agendador.get_job(scheduler.JOB_ID)

    assert job is not None
    assert str(job.trigger.timezone) == settings.timezone
    assert job.coalesce is True
    assert job.max_instances == 1
    # alto para rodar ao ligar o computador se a hora marcada passou
    assert job.misfire_grace_time >= 6 * 60 * 60


def test_proxima_execucao_sem_scheduler_e_none():
    assert scheduler.proxima_execucao(None) is None


async def test_cron_pula_quando_ja_existe_execucao(monkeypatch: pytest.MonkeyPatch):
    chamadas = []

    async def executar_fake(*args, **kwargs):
        chamadas.append(args)
        raise pipeline.ExecucaoEmAndamento("já rodando")

    monkeypatch.setattr(scheduler, "executar", executar_fake)
    await scheduler._rodar_agendado()  # não pode propagar a exceção

    assert len(chamadas) == 1


async def test_lock_impede_execucao_concorrente(monkeypatch: pytest.MonkeyPatch):
    comecou = asyncio.Event()
    liberar = asyncio.Event()

    async def rodar_devagar(session, run, dry_run):
        comecou.set()
        await liberar.wait()

    monkeypatch.setattr(pipeline, "_rodar", rodar_devagar)
    monkeypatch.setattr(pipeline, "Session", _SessionFake)

    primeira = asyncio.create_task(pipeline.executar())
    await comecou.wait()
    assert pipeline.em_execucao()

    with pytest.raises(pipeline.ExecucaoEmAndamento):
        await pipeline.executar()

    liberar.set()
    await primeira
    assert not pipeline.em_execucao()


class _SessionFake:
    """Evita tocar no banco: o teste olha só o lock."""

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def add(self, _):
        pass

    def commit(self):
        pass

    def refresh(self, _):
        pass

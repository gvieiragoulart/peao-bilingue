import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from vanhack_watcher.config import settings
from vanhack_watcher.models import GatilhoRun
from vanhack_watcher.pipeline import ExecucaoEmAndamento, executar

logger = logging.getLogger(__name__)

JOB_ID = "coleta-diaria"
# Alto de propósito: se o computador estava desligado na hora marcada, a
# execução acontece uma vez quando o app sobe, em vez de ser descartada.
MISFIRE_GRACE_S = 6 * 60 * 60


async def _rodar_agendado() -> None:
    try:
        await executar(GatilhoRun.cron)
    except ExecucaoEmAndamento:
        logger.info("Execução manual em andamento; o cron desta vez foi pulado.")


def criar_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    scheduler.add_job(
        _rodar_agendado,
        trigger=CronTrigger.from_crontab(
            settings.schedule_cron, timezone=settings.timezone
        ),
        id=JOB_ID,
        coalesce=True,
        misfire_grace_time=MISFIRE_GRACE_S,
        max_instances=1,
    )
    return scheduler


def proxima_execucao(scheduler: AsyncIOScheduler | None) -> str | None:
    if scheduler is None:
        return None
    job = scheduler.get_job(JOB_ID)
    return job.next_run_time.isoformat() if job and job.next_run_time else None

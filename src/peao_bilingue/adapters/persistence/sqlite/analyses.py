"""Job analyses, with the profile each one used."""

from sqlmodel import Session, col, select

from peao_bilingue.adapters.persistence.sqlite.database import BaseSQLite
from peao_bilingue.adapters.persistence.sqlite.profiles import last_source_profile
from peao_bilingue.adapters.persistence.sqlite.tables import (
    AnalysisTable,
    ProfileTable,
)
from peao_bilingue.domain.analysis import AnalysisRepository, JobAnalysis, SavedAnalysis


def last_analysis(session: Session, key: str) -> AnalysisTable | None:
    query = (
        select(AnalysisTable)
        .where(AnalysisTable.job_key == key)
        .order_by(col(AnalysisTable.id).desc())
    )
    return session.exec(query).first()


class AnalysesSQLite(BaseSQLite, AnalysisRepository):
    def save_analysis(
        self,
        key: str,
        analysis: JobAnalysis,
        *,
        provider: str,
        model: str,
        profile_id: int | None,
    ) -> None:
        with self._session() as session:
            session.add(
                AnalysisTable(
                    job_key=key,
                    data=analysis.model_dump(),
                    provider=provider,
                    model=model,
                    profile_id=profile_id,
                )
            )
            session.commit()

    def current_analysis(self, key: str) -> SavedAnalysis | None:
        with self._session() as session:
            row = last_analysis(session, key)
            if row is None:
                return None
            profile = (
                session.get(ProfileTable, row.profile_id) if row.profile_id else None
            )
            # A newer snapshot from the same source: the analysis used an old profile.
            last = last_source_profile(session, profile.source) if profile else None
            outdated = (
                profile is not None and last is not None and last.id != profile.id
            )
            return SavedAnalysis(
                analysis=JobAnalysis.model_validate(row.data),
                provider=row.provider,
                model=row.model,
                created_at=row.created_at,
                profile_source=profile.source if profile else None,
                profile_outdated=outdated,
            )

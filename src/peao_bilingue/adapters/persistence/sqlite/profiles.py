"""Profile snapshots, one history per source."""

from typing import Any

from sqlmodel import Session, col, select

from peao_bilingue.adapters.persistence.sqlite.database import BaseSQLite
from peao_bilingue.adapters.persistence.sqlite.tables import ProfileTable
from peao_bilingue.domain.profile import Profile, ProfileRepository


def last_source_profile(session: Session, source: str) -> ProfileTable | None:
    query = (
        select(ProfileTable)
        .where(ProfileTable.source == source)
        .order_by(col(ProfileTable.id).desc())
    )
    return session.exec(query).first()


def _id(row: ProfileTable) -> int:
    # A row read from the database or already saved has an id; None here is a bug.
    if row.id is None:
        raise RuntimeError("Profile snapshot without an id.")
    return row.id


def _differences(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    keys = set(before) | set(after)
    return sorted(key for key in keys if before.get(key) != after.get(key))


class ProfilesSQLite(BaseSQLite, ProfileRepository):
    def save_profile(self, profile: Profile) -> tuple[int, bool]:
        with self._session() as session:
            current = last_source_profile(session, profile.source)
            if current and current.content_hash == profile.content_hash:
                return _id(current), False
            row = ProfileTable(**profile.model_dump())
            session.add(row)
            session.commit()
            session.refresh(row)
            return _id(row), True

    def last_profile(self, source: str) -> tuple[int, Profile] | None:
        with self._session() as session:
            row = last_source_profile(session, source)
            if row is None:
                return None
            return _id(row), Profile.model_validate(row, from_attributes=True)

    def sources_with_profile(self) -> list[str]:
        query = select(ProfileTable.source).distinct().order_by(ProfileTable.source)
        with self._session() as session:
            return list(session.exec(query))

    def profile_history(self, source: str) -> list[dict[str, Any]]:
        query = (
            select(ProfileTable)
            .where(ProfileTable.source == source)
            .order_by(col(ProfileTable.id).desc())
        )
        with self._session() as session:
            rows = list(session.exec(query))
        history = []
        for index, row in enumerate(rows):
            previous = rows[index + 1] if index + 1 < len(rows) else None
            history.append(
                {
                    "id": row.id,
                    "read_at": row.read_at,
                    "content_hash": row.content_hash,
                    "changed_fields": _differences(
                        previous.data if previous else {}, row.data
                    ),
                }
            )
        return history

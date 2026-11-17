"""Profile snapshots: the CV's, one per change."""

from sqlmodel import Session, col, select

from peao_bilingue.adapters.persistence.sqlite.database import BaseSQLite
from peao_bilingue.adapters.persistence.sqlite.tables import ProfileTable, local
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


class ProfilesSQLite(BaseSQLite, ProfileRepository):
    def save_profile(self, profile: Profile) -> tuple[int, bool]:
        with self._session() as session:
            current = last_source_profile(session, profile.source)
            if current and current.content_hash == profile.content_hash:
                return _id(current), False
            row = ProfileTable(**profile.model_dump(exclude={"saved_at"}))
            session.add(row)
            session.commit()
            session.refresh(row)
            return _id(row), True

    def last_profile(self, source: str) -> tuple[int, Profile] | None:
        with self._session() as session:
            row = last_source_profile(session, source)
            if row is None:
                return None
            profile = Profile.model_validate(row, from_attributes=True)
            return _id(row), profile.model_copy(update={"saved_at": local(row.read_at)})

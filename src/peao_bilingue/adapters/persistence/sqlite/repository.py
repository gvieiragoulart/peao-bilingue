"""Every SQLite repository in one object."""

from peao_bilingue.adapters.persistence.sqlite.analyses import AnalysesSQLite
from peao_bilingue.adapters.persistence.sqlite.jobs import JobsSQLite
from peao_bilingue.adapters.persistence.sqlite.profiles import ProfilesSQLite
from peao_bilingue.adapters.persistence.sqlite.runs import RunsSQLite
from peao_bilingue.adapters.persistence.sqlite.searches import SearchesSQLite
from peao_bilingue.domain.repository import Repository


class SQLiteRepository(
    SearchesSQLite,
    JobsSQLite,
    AnalysesSQLite,
    ProfilesSQLite,
    RunsSQLite,
    Repository,
):
    """The five ports on the same database: one object, each part in its own file."""

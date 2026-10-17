"""Repository reads the test expects to find: they fail with a clear message when
there is nothing, and return the type without `None` (which keeps mypy happy)."""

from peao_bilingue.domain.analysis import AnalysisRepository, SavedAnalysis
from peao_bilingue.domain.profile import Profile, ProfileRepository


def saved_profile(profiles: ProfileRepository, source: str) -> Profile:
    saved = profiles.last_profile(source)
    assert saved is not None, f"no profile from {source}"
    return saved[1]


def saved_analysis(analyses: AnalysisRepository, key: str) -> SavedAnalysis:
    saved = analyses.current_analysis(key)
    assert saved is not None, f"no analysis of job {key}"
    return saved

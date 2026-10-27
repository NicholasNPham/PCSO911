"""StacSession.upload_case: what is retried in a fresh browser and what never is."""

# Third-party Imports
import pytest

# Local Imports
from exceptions import SystemProblem
from ftp_to_stac import CaseNotFound, NameMismatch, SaveMayHaveHappened, StacSession

UCN = "53-2026-CF-000000-A000-XX"


class ScriptedSession(StacSession):
    """A StacSession whose browser steps are replaced by a script of outcomes."""

    def __init__(self, outcomes: list) -> None:
        """
        Stores what each attempt's add_files does, in order.

        Args:
            outcomes (list): None for success, or an exception to raise.

        Returns:
            None
        """
        super().__init__("user", "pass")
        self.outcomes = list(outcomes)
        self.opens = 0
        self.closes = 0
        self.cleanups = 0
        self.attempts = 0

    def open(self) -> None:
        """Counts sign-ins instead of starting Chrome."""
        self.opens += 1

    def close(self) -> None:
        """Counts closes instead of quitting Chrome."""
        self.closes += 1

    def leave_browser_clean(self) -> None:
        """Counts cleanups instead of refreshing the page."""
        self.cleanups += 1

    def find_case(self, ucn: str, child_dir_name: str) -> None:
        """Finds nothing; the script decides in add_files."""

    def add_files(self, ucn: str, file_list: list) -> None:
        """Plays the next scripted outcome."""
        self.attempts += 1
        outcome = self.outcomes.pop(0)
        if outcome is not None:
            raise outcome


def test_success_first_try() -> None:
    """A clean case runs once and restarts nothing."""
    session = ScriptedSession([None])
    session.upload_case(UCN, ["a.mp3"], "SMITH JOHN")
    assert session.attempts == 1
    assert session.closes == 0


def test_system_problem_retried_in_fresh_browser() -> None:
    """A STAC failure closes Chrome and the second attempt signs in again."""
    session = ScriptedSession([SystemProblem("spinner stuck"), None])
    session.upload_case(UCN, ["a.mp3"], "SMITH JOHN")
    assert session.attempts == 2
    assert session.closes == 1
    assert session.opens == 2


def test_system_problem_twice_raises() -> None:
    """Two STAC failures use up the retry, close Chrome without a refresh, and raise."""
    session = ScriptedSession([SystemProblem("one"), SystemProblem("two")])
    with pytest.raises(SystemProblem, match="two"):
        session.upload_case(UCN, ["a.mp3"], "SMITH JOHN")
    assert session.attempts == 2
    assert session.closes == 2
    assert session.cleanups == 0


@pytest.mark.parametrize("error", [CaseNotFound("missing"), NameMismatch("other person")])
def test_case_problems_not_retried(error: Exception) -> None:
    """A missing case or a mismatch does not improve by trying again."""
    session = ScriptedSession([error, None])
    with pytest.raises(type(error)):
        session.upload_case(UCN, ["a.mp3"], "SMITH JOHN")
    assert session.attempts == 1


def test_unconfirmed_save_never_retried() -> None:
    """A retry after an unconfirmed Save could file the audio twice."""
    session = ScriptedSession([SaveMayHaveHappened("no confirmation"), None])
    with pytest.raises(SaveMayHaveHappened):
        session.upload_case(UCN, ["a.mp3"], "SMITH JOHN")
    assert session.attempts == 1
    assert session.cleanups == 1

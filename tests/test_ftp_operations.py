"""Directory skipping, and the renames after a confirmed or unconfirmed Save."""

# Standard Library Imports
import ftplib
import os

# Third-party Imports
import pytest

# Local Imports
import ftp_operations
from exceptions import CaseProblem, SystemProblem
from ftp_operations import (
    DELETE_DIR_PREFIX,
    ERROR_SAVE_PREFIX,
    HAS_HTM_KEY,
    TEMP_DIR_PREFIX,
    handle_uploaded_case,
    mark_save_unconfirmed,
    process_single_case,
    should_skip_directory,
)
from ftp_to_stac import SaveMayHaveHappened

DIR_NAME = "53-2026-CF-000000-A000-XX SMITH JOHN"


@pytest.mark.parametrize("name, expected", [
    ("__Completed", True),
    ("_DELETE" + DIR_NAME, True),
    ("_ERROR_HTM " + DIR_NAME, True),
    (ERROR_SAVE_PREFIX + DIR_NAME + " _SCRIPT 123456", True),
    (DIR_NAME, False),
])
def test_should_skip_directory(name: str, expected: bool) -> None:
    """Completed, deleted, HTM-flagged and unconfirmed-Save directories are never run again."""
    assert should_skip_directory(name) is expected


class FakeFtp:
    """Records renames, or fails them when told to."""

    def __init__(self, fail: bool = False) -> None:
        """
        Sets whether rename fails.

        Args:
            fail (bool): True to raise ftplib.error_perm on rename.

        Returns:
            None
        """
        self.fail = fail
        self.renamed: list[tuple[str, str]] = []

    def rename(self, old: str, new: str) -> None:
        """Records the rename, or raises like a refused FTP rename."""
        if self.fail:
            raise ftplib.error_perm("550 refused")
        self.renamed.append((old, new))

    def cwd(self, path: str) -> None:
        """Changing folder always works here."""

    def retrbinary(self, command: str, callback) -> None:
        """Serves a few bytes for any file."""
        callback(b"audio")


class FailingStac:
    """A STAC session whose upload fails, recording where the files were."""

    def __init__(self) -> None:
        """
        Starts with no files seen.

        Returns:
            None
        """
        self.file_lists: list[list[str]] = []

    def upload_case(self, ucn: str, file_list: list, child_dir_name: str) -> None:
        """Records the files, checks they exist, then fails like a broken STAC."""
        assert all(os.path.isfile(path) for path in file_list)
        self.file_lists.append(file_list)
        raise SystemProblem("spinner stuck")


def test_unconfirmed_save_renames_directory() -> None:
    """The directory gets the skipped prefix and the error says so."""
    ftp = FakeFtp()
    with pytest.raises(SaveMayHaveHappened, match="renamed to"):
        mark_save_unconfirmed(ftp, DIR_NAME, SaveMayHaveHappened("no confirmation."))
    assert ftp.renamed[0][1].startswith(ERROR_SAVE_PREFIX)
    assert should_skip_directory(ftp.renamed[0][1])


def test_unconfirmed_save_rename_failure_is_loud() -> None:
    """If the rename fails too, the error warns the next run will upload it again."""
    with pytest.raises(SaveMayHaveHappened, match="WILL upload it again"):
        mark_save_unconfirmed(FakeFtp(fail=True), DIR_NAME, SaveMayHaveHappened("no confirmation."))


def test_each_case_gets_its_own_temp_folder_and_it_is_deleted() -> None:
    """Two cases never share a folder, and a failed upload still leaves nothing behind."""
    stac = FailingStac()
    case = {"ucn": "53-2026-CF-000000-A000-XX", "files": ["call.mp3"], HAS_HTM_KEY: False}
    for _ in range(2):
        with pytest.raises(SystemProblem):
            process_single_case(FakeFtp(), stac, DIR_NAME, case)

    folders = [os.path.dirname(files[0]) for files in stac.file_lists]
    assert folders[0] != folders[1]
    assert all(os.path.basename(folder).startswith(TEMP_DIR_PREFIX) for folder in folders)
    assert not any(os.path.exists(folder) for folder in folders)


@pytest.mark.parametrize("has_htm", [False, True])
def test_rename_after_save_failure_says_audio_is_saved(has_htm: bool) -> None:
    """A failed rename after a confirmed Save is a CaseProblem that says the audio is in STAC."""
    with pytest.raises(CaseProblem, match="IS saved in STAC"):
        handle_uploaded_case(FakeFtp(fail=True), {HAS_HTM_KEY: has_htm}, DIR_NAME, 0)


def test_saved_case_renamed_and_counted(monkeypatch: pytest.MonkeyPatch) -> None:
    """A saved case without an HTM file gets the delete prefix, moves, and counts."""
    moved: list[str] = []
    monkeypatch.setattr(ftp_operations, "move_to_completed", lambda ftp, name, completed: moved.append(name))
    ftp = FakeFtp()
    assert handle_uploaded_case(ftp, {HAS_HTM_KEY: False}, DIR_NAME, 4) == 5
    assert moved == [ftp.renamed[0][1]]
    assert moved[0].startswith(DELETE_DIR_PREFIX)

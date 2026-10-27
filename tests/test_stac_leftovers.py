"""Leftovers from the last case in the shared browser must not confirm this case's upload or Save."""

# Third-party Imports
import pytest
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait

# Local Imports
import ftp_to_stac
from exceptions import SystemProblem
from ftp_to_stac import (
    FILE_UPLOAD_SUCCESS_XPATH,
    IMAGE_SAVED_NOTIFICATION_XPATH,
    SAVE_IMAGE_BUTTON,
    SaveMayHaveHappened,
    StacSession,
)

UCN = "53-2026-CF-000000-A000-XX"
SHORT_WAIT_SECONDS = 0.3


class FakeElement:
    """A page element that is shown or hidden and runs a callback when clicked or typed into."""

    def __init__(self, shown: bool = True, on_use=None) -> None:
        """
        Sets whether the element is shown and what using it does.

        Args:
            shown (bool): What is_displayed returns.
            on_use (callable | None): Called on click or send_keys.

        Returns:
            None
        """
        self.shown = shown
        self.on_use = on_use

    def is_displayed(self) -> bool:
        """Returns whether the element is shown."""
        return self.shown

    def is_enabled(self) -> bool:
        """Always enabled."""
        return True

    def click(self) -> None:
        """Runs the click callback."""
        if self.on_use:
            self.on_use()

    def send_keys(self, *_) -> None:
        """Runs the typing callback."""
        if self.on_use:
            self.on_use()


class FakeDriver:
    """Just enough of a Chrome driver for upload and save_and_confirm."""

    def __init__(self, leftover_messages: int = 0, upload_finishes: bool = True,
                 leftover_note_shown: bool | None = None, save_confirms: bool = True) -> None:
        """
        Sets what the last case left in the page and how STAC answers this one.

        Args:
            leftover_messages (int): "Uploaded successfully" messages already listed.
            upload_finishes (bool): Whether this upload adds a message per file.
            leftover_note_shown (bool | None): A saved notification already in the
                                               page, shown or hidden; None for none.
            save_confirms (bool): Whether Save shows a new notification.

        Returns:
            None
        """
        self.messages = [FakeElement() for _ in range(leftover_messages)]
        self.notes = [] if leftover_note_shown is None else [FakeElement(leftover_note_shown)]
        self.upload_finishes = upload_finishes
        self.save_confirms = save_confirms
        self.save_clicked = False
        self.file_count = 0

    def execute_script(self, script: str, *_) -> str:
        """Answers the Subtype check; every other script does nothing here."""
        return ftp_to_stac.MATRIX_SEARCH_TERM

    def find_element(self, by: str, value: str) -> FakeElement:
        """Returns the Save button, the file input, or a shown notification."""
        if value == SAVE_IMAGE_BUTTON:
            return FakeElement(on_use=self.press_save)
        if value == IMAGE_SAVED_NOTIFICATION_XPATH:
            shown = [note for note in self.notes if note.shown]
            if shown:
                return shown[0]
            raise NoSuchElementException()
        return FakeElement(on_use=self.receive_files)

    def find_elements(self, by: str, value: str) -> list:
        """Returns the upload messages or the saved notifications."""
        if value == FILE_UPLOAD_SUCCESS_XPATH:
            return self.messages
        if value == IMAGE_SAVED_NOTIFICATION_XPATH:
            return self.notes
        return []

    def receive_files(self) -> None:
        """Lists one success message per file, if this upload finishes."""
        if self.upload_finishes:
            self.messages += [FakeElement() for _ in range(self.file_count)]

    def press_save(self) -> None:
        """Records the click and shows a new notification if STAC confirms."""
        self.save_clicked = True
        if self.save_confirms:
            self.notes.append(FakeElement())


@pytest.fixture(autouse=True)
def short_waits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Shrinks every wait so a test that times out does so quickly."""
    monkeypatch.setattr(ftp_to_stac, "WEBDRIVER_WAIT_TIMEOUT_SECONDS", SHORT_WAIT_SECONDS)
    monkeypatch.setattr(ftp_to_stac, "FILE_UPLOAD_WAIT_TIMEOUT_SECONDS", SHORT_WAIT_SECONDS)


def session_on(driver: FakeDriver) -> StacSession:
    """
    Builds a StacSession that drives the fake instead of Chrome.

    Args:
        driver (FakeDriver): The fake page.

    Returns:
        StacSession: A session with driver and wait set.
    """
    session = StacSession("user", "pass")
    session.driver = driver
    session.wait = WebDriverWait(driver, SHORT_WAIT_SECONDS)
    return session


def test_upload_counts_only_new_messages() -> None:
    """Two messages left from the last case do not stand in for two files that never finished."""
    driver = FakeDriver(leftover_messages=2, upload_finishes=False)
    driver.file_count = 2
    with pytest.raises(SystemProblem, match="finished uploading"):
        session_on(driver).upload(["a.mp3", "b.mp3"])


def test_upload_passes_when_new_messages_arrive() -> None:
    """With leftovers in the page, this upload's own messages still confirm it."""
    driver = FakeDriver(leftover_messages=2, upload_finishes=True)
    driver.file_count = 2
    session_on(driver).upload(["a.mp3", "b.mp3"])


def test_hidden_leftover_notification_does_not_confirm_save() -> None:
    """A hidden notification in the page is not a confirmation of this save."""
    driver = FakeDriver(leftover_note_shown=False, save_confirms=False)
    with pytest.raises(SaveMayHaveHappened):
        session_on(driver).save_and_confirm(UCN, 1)
    assert driver.save_clicked


def test_shown_leftover_notification_blocks_save() -> None:
    """A notification still up from the last case stops before Save, so the retry is safe."""
    driver = FakeDriver(leftover_note_shown=True)
    with pytest.raises(SystemProblem, match="still showing before Save"):
        session_on(driver).save_and_confirm(UCN, 1)
    assert not driver.save_clicked


def test_clean_save_confirms() -> None:
    """With nothing left over, a shown notification after Save confirms it."""
    driver = FakeDriver(save_confirms=True)
    session_on(driver).save_and_confirm(UCN, 1)
    assert driver.save_clicked

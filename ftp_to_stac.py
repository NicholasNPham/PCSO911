"""
STAC Web Scraper Module

Handles login, searching, and adding 911 audio to cases via the STAC web
interface using Selenium WebDriver automation.

One browser session covers a whole run. Chrome opens and signs in once, on the
first case, and every later case resets the search in place instead of
starting a new browser. Chrome is only restarted after something fails, and
the failed case is then tried once more in the fresh browser.

The browser handling and most of the checks are ported back from DALYN
(github.com/NicholasNPham/PROJECT-DALYN, src/stac.py), which grew them running
this same screen at higher volume. The dates in comments are DALYN runs.

Nothing here sends email. Failures raise CaseProblem (this case needs a person)
or SystemProblem (STAC or the browser is broken) for main.py to route, so one
failure sends one email.
"""

# Standard Library Imports
import re
import time
from pathlib import Path

# Third-party Imports
from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoAlertPresentException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from urllib3.exceptions import HTTPError as Urllib3Error

# Local Imports
from exceptions import CaseProblem, ServiceUnreachable, SystemProblem
from key import WEBSITE, CHROME_PATH

# CONSTANTS
# Every way the browser can fail under a Selenium call. WebDriverException
# alone misses the connection to chromedriver itself: in DALYN on 16 Oct 2026
# a STAC page that never answered raised urllib3's ReadTimeoutError after 120
# seconds and slipped past every handler.
BROWSER_ERRORS = (WebDriverException, Urllib3Error, TimeoutError, ConnectionError)

WEBDRIVER_WAIT_TIMEOUT_SECONDS = 10
FILE_UPLOAD_WAIT_TIMEOUT_SECONDS = 60

# Without a limit Chrome waits forever on a hung page, and the first thing to
# give up is Selenium's own 120 second read, which raises a urllib3 error
# instead of a TimeoutException.
PAGE_LOAD_TIMEOUT_SECONDS = 60

# Attempts per case. The second one gets a fresh browser.
MAX_ATTEMPTS = 2

# Kendo rebuilds its dialogs after each interaction and drops a click that
# lands too soon after the previous one (STAC setInterval bug).
KENDO_INTERVAL_RECOVERY_PAUSE_SECONDS = 1

EXCLUDED_TOKENS = {"AM", "SVP", "AME", "SO", "AMSP", "JLA", "PJLA", "SP", "ALERT", "BKGRDALERT", "CP", "DO", "NOT", "USE", "GANG", "NCP", "NO", "CC", "OSCP", "SPCALERT", "TTP", "VFOSC", "HA"}

# Fuzzy name match: a word this long or longer may be one letter off. Shorter
# words, like initials, must match exactly, since one letter is most of them.
MIN_FUZZY_WORD_LENGTH = 4
NAME_MATCH_EXACT = "exact"
NAME_MATCH_FUZZY = "fuzzy"

# browser_login
LOGIN_DROPDOWN_MENU_ID = 'LoginProvider'
USERNAME_AND_PASSWORD_DROPDOWN_MENU_VALUE = 'Local'
USERNAME_FIELD_ID = 'Username'
PASSWORD_FIELD_ID = 'Password'
SUBMIT_LOGIN_BUTTON_ID = 'submitLogin'

# case search
CASES_SIDEBAR_BUTTON_CSS_SELECTOR = "[data-menuid='incident']"
SEARCH_BAR_DROPDOWN_OPTION_CSS_SELECTOR = "button[role='button'][aria-label='select']"
UCN_SEARCH_BAR_DROPDOWN_OPTION_XPATH = "//ul[@id='incidentsSearchMainCriteria_listbox' and not(contains(@style,'display: none'))]//span[text()='UCN']"
SEARCH_BAR_FIELD_ID = "incidentsSearchMainSearchValue"
SEARCH_BAR_BUTTON_ID = "incidentsSearchMainButton"
NO_RECORDS_FOUND_CSS_SELECTOR = ".k-grid-norecords-template"
CASE_NAME_FROM_STAC_UCN_SEARCH = "td[data-original-column-name='Def_Name'] span.k-button-text"
IMAGES_TAB_OF_CASE_ID = "incidentsTab-tab-3"

# Clears the open case and its search results in place, so the next search
# needs no reload. Only reached once a search has run in this browser.
REMOVE_FROM_LIST_ID = "incidentsListMainListRemoveItem"
RESET_CLEAR_SECONDS = 3

# A "no records" can be read before the results finish loading. A case wrongly
# reported missing goes to a person, so a few seconds on each real miss is the
# cheaper mistake (DALYN, 14 Oct 2026).
NO_RECORDS_RECHECK_SECONDS = 5

# upload
FIRST_NON_SELECTED_IMAGE_TILE_CSS_SELECTOR = "#image-manager-listview-name .cipimage:not(.k-selected)"
IMAGES_TAB_PREVIEW_IFRAME_CSS_SELECTOR = "#imageTabPageSplitterRightPane iframe.iframe-document"
IMAGES_TAB_DROPZONE_PANEL_CSS_SELECTOR = ".pagesImagesIndex-upload-drop-zone-element"
TAB_DROPZONE_FILE_INPUT_CSS_SELECTOR = "input[id^='cipFileUpload_pagesImagesIndex-upload'][multiple]:not([webkitdirectory])"
FILE_UPLOAD_SUCCESS_XPATH = "//span[contains(@class,'k-file-validation-message') and text()='File(s) uploaded successfully.']"
PREVIEW_IFRAME_LOADED_MARKER = "web/viewer.html?file="

# Seconds to wait for an existing document's preview. Optional: a case with no
# images, or one whose preview never renders, moves on after this.
PREVIEW_WAIT_SECONDS = 5

# Kendo's loading spinner. Kendo leaves hidden ones in the page, so only shown
# ones count. In DALYN on 13 Oct 2026 one sat over Save for over a minute.
SPINNER_CSS = ".k-loading-image"
SPINNER_APPEAR_SECONDS = 2
PREVIEW_PANE_CSS = "#imageTabPageSplitterRightPane"
# Removing the preview iframe strands the preview's own spinner, which waits
# for a frame that is gone. It sits clear of Save, so the waits after the
# upload ignore it (DALYN, 14 Oct 2026).
SPINNER_OUTSIDE_PREVIEW_CSS = f"{SPINNER_CSS}:not({PREVIEW_PANE_CSS} {SPINNER_CSS})"

# type/subtype popup
IMAGE_SUB_TYPE_FIND_BUTTON_CSS_SELECTOR = ".c-button-find-type-subtype"
IMAGE_SUB_TYPE_ROW_XPATH = "//tr[.//span[text()='DISCOVERY'] and .//span[text()='911AUDIO']]"
MATRIX_SEARCH_INPUT_CSS_SELECTOR = "div#codeSearchDialog input.k-input-inner[placeholder='Search...']"
SELECT_BUTTON_ID = "SelectCodeAndSubCode"
MATRIX_SEARCH_TERM = "911AUDIO"
IMAGE_SUB_TYPE_INPUT_ID = "input[name='image_sub_type']"

# save
SAVE_IMAGE_BUTTON = "SaveImage"
IMAGE_SAVED_NOTIFICATION_XPATH = "//div[contains(@class,'c-notification-success')]"

# ERRORS
class CaseNotFound(CaseProblem):
    """STAC's search found no case with this UCN."""

class NameMismatch(CaseProblem):
    """STAC found the UCN, but its defendant does not match the FTP directory name."""

class SaveMayHaveHappened(CaseProblem):
    """
    Save was clicked but the confirmation never came, so nobody knows.

    The one failure that must never be retried: the audio may already be on
    the case. A person has to look before this directory is run again.
    """

# HELPER FUNCTIONS
def name_tokens(name: str) -> set[str]:
    """
    Splits a name into uppercase words, dropping parentheticals and excluded tokens.

    Args:
        name (str): A STAC defendant name or an FTP directory name.

    Returns:
        set[str]: The words that count toward a name match.
    """
    name = re.sub(r'\(.*?\)', '', name)
    return set(w for w in re.findall(r'[a-zA-Z]+', name.upper()) if w not in EXCLUDED_TOKENS)

def one_edit_apart(first: str, second: str) -> bool:
    """
    Checks whether two words differ by exactly one letter changed, added, or removed.

    Args:
        first (str): One word.
        second (str): The other word.

    Returns:
        bool: True if exactly one edit turns one word into the other, False otherwise.
    """
    if first == second or abs(len(first) - len(second)) > 1:
        return False

    shorter, longer = sorted((first, second), key=len)
    index = 0
    while index < len(shorter) and shorter[index] == longer[index]:
        index += 1

    if len(shorter) == len(longer):
        # Same length: the rest must agree after the one changed letter.
        return shorter[index + 1:] == longer[index + 1:]
    # One letter longer: the rest must agree after skipping the extra letter.
    return shorter[index:] == longer[index + 1:]

def fuzzy_subset(fewer: set[str], more: set[str]) -> bool:
    """
    Checks whether every word in one name has a partner in the other, allowing typos.

    A partner is the same word, or for words of MIN_FUZZY_WORD_LENGTH or more,
    a word one letter off. At least one word must match exactly, so two typos
    cannot turn the name into a different person, and each partner is used once.

    Args:
        fewer (set[str]): Words that each need a partner.
        more (set[str]): Words to find partners in.

    Returns:
        bool: True if every word in fewer has a partner, False otherwise.
    """
    exact = fewer & more
    if not exact:
        return False

    unused = [word for word in more if word not in exact]
    for word in fewer - exact:
        if len(word) < MIN_FUZZY_WORD_LENGTH:
            return False
        partner = next((c for c in unused if len(c) >= MIN_FUZZY_WORD_LENGTH and one_edit_apart(word, c)), None)
        if partner is None:
            return False
        unused.remove(partner)

    return True

def name_match_kind(stac_name: str, child_dir_name: str) -> str | None:
    """
    Compares a STAC defendant name with an FTP directory name.

    Exact when one word set is a subset of the other, as PCSO911 has always
    matched. Fuzzy when the same holds allowing a one-letter typo per word,
    because the people who name these directories sometimes misspell a name
    by a character. The UCN has already matched by the time this runs, so the
    looser rule only loosens the name, never the case.

    Args:
        stac_name (str): The defendant name from STAC (may contain parenthetical content).
        child_dir_name (str): The FTP directory name to compare against.

    Returns:
        str | None: NAME_MATCH_EXACT, NAME_MATCH_FUZZY, or None if the names do not match.
    """
    stac_tokens = name_tokens(stac_name)
    dir_tokens = name_tokens(child_dir_name)

    # An empty set is a subset of everything, so a STAC name made only of
    # excluded tokens used to match any directory.
    if not stac_tokens or not dir_tokens:
        return None

    if stac_tokens.issubset(dir_tokens) or dir_tokens.issubset(stac_tokens):
        return NAME_MATCH_EXACT
    if fuzzy_subset(stac_tokens, dir_tokens) or fuzzy_subset(dir_tokens, stac_tokens):
        return NAME_MATCH_FUZZY
    return None

def usable_driver_path(configured: str | None) -> str | None:
    """
    Returns the configured chromedriver only if it is actually a file.

    A blank or wrong path reaches Selenium as a directory and fails with a
    message about not obtaining a driver, which sends everyone looking in the
    wrong place.

    Args:
        configured (str | None): CHROME_PATH from key.py.

    Returns:
        str | None: The path if it is a file, otherwise None.
    """
    if not configured:
        return None
    path = Path(str(configured))
    if path.is_file():
        return str(path)
    print(f"CHROME_PATH is set to {path}, which is not a file. Ignoring it.")
    return None

def describe_intercepting_element(message: str) -> str:
    """
    Names the element Chrome says took a click, as tag.class or tag#id.

    Only the tag and its class or id are kept, so no page text reaches the log.

    Args:
        message (str): Chrome's ElementClickInterceptedException message.

    Returns:
        str: A short description of the covering element.
    """
    match = re.search(r"would receive the click: <(\w+)([^>]*)>", message)
    if not match:
        return "another element"
    tag, attributes = match.groups()
    found = re.search(r'\bclass="([^"]*)"', attributes)
    if found and found.group(1).strip():
        return f"{tag}.{'.'.join(found.group(1).split())}"
    found = re.search(r'\bid="([^"]*)"', attributes)
    if found and found.group(1):
        return f"{tag}#{found.group(1)}"
    return tag

class PressWhenUncovered:
    """
    A WebDriverWait condition that clicks the element once nothing covers it.

    Selenium's "clickable" means shown and enabled, not uncovered. After an
    upload STAC lays its spinner over the page for a moment, and a click then
    lands on the spinner. Each try records what stood in the way, in
    `blocker`, so the error can name it.
    """

    def __init__(self, element_id: str) -> None:
        """
        Remembers the element to click.

        Args:
            element_id (str): Id of the element, e.g. SAVE_IMAGE_BUTTON.

        Returns:
            None
        """
        self.element_id = element_id
        self.blocker = "nothing tried yet"
        # True while click() is running, so a caller that sees some other
        # browser error knows whether the click may have reached the page.
        # For Save that is the line between a safe retry and a person.
        self.clicking = False

    def __call__(self, driver: webdriver.Chrome) -> bool:
        """
        Tries the click once.

        Args:
            driver (WebDriver): Selenium Chrome driver.

        Returns:
            bool: True once the click went through, False to keep waiting.
        """
        self.clicking = False
        try:
            element = driver.find_element(By.ID, self.element_id)
            if not element.is_displayed():
                self.blocker = "the button is hidden"
                return False
            if not element.is_enabled():
                self.blocker = "the button is disabled"
                return False
            self.clicking = True
            element.click()
        except NoSuchElementException:
            self.blocker = "the button is not on the page"
            return False
        except StaleElementReferenceException:
            # Chrome refused the click on a redrawn button, so it never landed.
            self.clicking = False
            self.blocker = "the page was redrawing"
            return False
        except ElementClickInterceptedException as error:
            self.clicking = False
            self.blocker = f"covered by {describe_intercepting_element(error.msg or '')}"
            return False
        return True

# SESSION
class StacSession:
    """
    One signed-in STAC browser, reused for every case in a run.

    Used as `with StacSession(username, password) as stac:`. Entering the
    `with` opens nothing; the first upload_case signs in, so a run with no
    cases never opens Chrome. Leaving the `with` closes Chrome even when a
    case blew up halfway through.
    """

    def __init__(self, username: str, password: str) -> None:
        """
        Stores the STAC login. Opens nothing yet.

        Args:
            username (str): STAC username from Credential Manager.
            password (str): STAC password from Credential Manager.

        Returns:
            None
        """
        self._username = username
        self._password = password
        self._chromedriver = usable_driver_path(CHROME_PATH)
        self.driver: webdriver.Chrome | None = None
        self.wait: WebDriverWait | None = None
        # STAC keeps the search criteria once set, so the dropdown only needs
        # UCN chosen once per browser. Reset whenever a new browser opens.
        self._criteria_is_ucn = False
        # True once any search has run in this browser, found or not, since
        # either leaves the page needing a reset before the next search.
        self._searched = False

    def __enter__(self) -> "StacSession":
        """
        Returns the session without opening Chrome.

        Returns:
            StacSession: This session.
        """
        return self

    def __exit__(self, *_) -> None:
        """
        Closes Chrome on the way out of the `with`.

        Returns:
            None
        """
        self.close()

    # ------------------------------------------------------------ browser

    def open(self) -> None:
        """
        Launches Chrome, loads STAC, and signs in, unless already open.

        Returns:
            None

        Raises:
            ServiceUnreachable: If STAC's login page does not load in time.
            SystemProblem: If Chrome will not start, STAC will not load, or the
                           sign-in fails.
        """
        if self.driver is not None:
            return

        self.driver = self.start_chrome()
        self.wait = WebDriverWait(self.driver, WEBDRIVER_WAIT_TIMEOUT_SECONDS)
        self._criteria_is_ucn = False
        self._searched = False

        try:
            self.driver.get(WEBSITE)
            self.driver.maximize_window()
        except BROWSER_ERRORS as error:
            self.close()
            # Only a page load that ran out of time is STAC or the network not
            # answering. Chrome crashing is not fixed by waiting.
            problem = ServiceUnreachable if isinstance(error, TimeoutException) else SystemProblem
            raise problem(f"Could not load STAC: {type(error).__name__}") from error

        try:
            self.sign_in()
        except BROWSER_ERRORS as error:
            self.close()
            raise SystemProblem(f"The browser failed while signing in to STAC: {type(error).__name__}") from error
        except Exception:
            self.close()
            raise

    def start_chrome(self) -> webdriver.Chrome:
        """
        Starts Chrome, trying each way of finding chromedriver in turn.

        Selenium Manager comes first. It is built into Selenium, finds the
        installed Chrome's version, and keeps the matching chromedriver in its
        cache, so it only downloads again when Chrome updates. CHROME_PATH is
        the fallback for a machine that cannot reach the download.

        Returns:
            WebDriver: A running Chrome driver.

        Raises:
            SystemProblem: If no route produces a working Chrome. The message
                           lists what was tried.
        """
        attempts = [("Selenium Manager", lambda: None)]
        if self._chromedriver:
            attempts.append(("CHROME_PATH", lambda: Service(self._chromedriver)))

        failures = []
        for description, build_service in attempts:
            try:
                service = build_service()
                driver = webdriver.Chrome(service=service) if service else webdriver.Chrome()
                driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT_SECONDS)
                print(f"Chrome started via {description}")
                return driver
            except Exception as error:  # each route fails differently
                failures.append(f"{description}: {type(error).__name__}: {str(error).splitlines()[0] if str(error) else ''}")

        raise SystemProblem(
            "Could not start Chrome. Set CHROME_PATH in key.py to a chromedriver.exe "
            "matching the installed Chrome. Tried: " + " | ".join(failures)
        )

    def sign_in(self) -> None:
        """
        Fills the sign-in form and waits for the Cases sidebar to appear.

        Returns:
            None

        Raises:
            SystemProblem: If any step of sign-in does not complete.
        """
        try:
            dropdown_element = self.wait.until(EC.presence_of_element_located((By.ID, LOGIN_DROPDOWN_MENU_ID)))
            Select(dropdown_element).select_by_value(USERNAME_AND_PASSWORD_DROPDOWN_MENU_VALUE)
        except TimeoutException as error:
            raise SystemProblem("No 'Authenticate Using' dropdown on the STAC sign-in page.") from error

        try:
            self.wait.until(EC.element_to_be_clickable((By.ID, USERNAME_FIELD_ID))).send_keys(self._username)
            self.wait.until(EC.element_to_be_clickable((By.ID, PASSWORD_FIELD_ID))).send_keys(self._password)
        except TimeoutException as error:
            raise SystemProblem("Could not find the STAC username or password field.") from error

        try:
            submit_btn = self.wait.until(EC.element_to_be_clickable((By.ID, SUBMIT_LOGIN_BUTTON_ID)))
            # JavaScript click because an overlay covers the real button often
            # enough that a normal click is intercepted.
            self.driver.execute_script("arguments[0].click();", submit_btn)
        except TimeoutException as error:
            raise SystemProblem("Could not find the STAC sign-in button.") from error

        try:
            # The sidebar is the only reliable proof of a sign-in: STAC
            # re-renders the same page on a bad password.
            self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, CASES_SIDEBAR_BUTTON_CSS_SELECTOR)))
        except TimeoutException as error:
            raise SystemProblem(
                "Signed in but the Cases sidebar never appeared. Usually a wrong STAC "
                "username or password in Credential Manager."
            ) from error

        print("Signed in to STAC")

    def close(self) -> None:
        """
        Closes Chrome. Safe to call twice, and never raises.

        Returns:
            None
        """
        if self.driver is None:
            return
        try:
            self.driver.quit()
        except BROWSER_ERRORS as error:
            # A hung chromedriver fails here, and close runs inside error
            # handlers whose error must not be replaced by this one.
            print(f"Chrome did not close cleanly: {type(error).__name__}")
        finally:
            self.driver = None
            self.wait = None

    def leave_browser_clean(self) -> None:
        """
        Refreshes the page after a failure, or closes Chrome if that fails.

        A failure leaves STAC wherever it broke: a dialog open, an upload
        pending. The next case would then fail on that mess. A refresh keeps
        the sign-in and drops it. If the refresh fails, Chrome is closed rather
        than restarted here: the next case's open() signs in only if there is
        a next case. Never raises: whatever went wrong before this is the
        error worth reporting.

        Returns:
            None
        """
        if self.driver is None:
            return
        try:
            self.discard_pending_upload()
            print("Refreshed the STAC page after the failure, keeping the browser")
        except (SystemProblem, *BROWSER_ERRORS) as error:
            print(f"Refresh after the failure did not work ({type(error).__name__}); closing the browser")
            self.close()

    def discard_pending_upload(self) -> None:
        """
        Reloads the page so an unsaved upload cannot bleed into the next case.

        Returns:
            None

        Raises:
            SystemProblem: If the page does not come back to the Cases sidebar.
        """
        try:
            self.driver.refresh()
            try:
                self.driver.switch_to.alert.accept()
            except NoAlertPresentException:
                pass
            self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, CASES_SIDEBAR_BUTTON_CSS_SELECTOR)))
        except (TimeoutException, WebDriverException) as error:
            raise SystemProblem(f"Could not clear the page after a failure: {type(error).__name__}") from error
        # A reload resets the search criteria and clears any search.
        self._criteria_is_ucn = False
        self._searched = False

    # ------------------------------------------------------------- search

    def find_case(self, ucn: str, child_dir_name: str) -> None:
        """
        Searches STAC for a UCN, checks the defendant, and opens the Images tab.

        Args:
            ucn (str): Universal Case Number to search for.
            child_dir_name (str): FTP directory name, for the defendant check.

        Returns:
            None

        Raises:
            CaseNotFound: No case with that UCN.
            NameMismatch: More than one case came back, or the defendant does
                          not match the directory name.
            SystemProblem: STAC did not respond as expected.
        """
        self.open_case_search()
        stac_names = self.search_ucn(ucn)

        if len(stac_names) > 1:
            matching = sum(1 for name in stac_names if name_match_kind(name, child_dir_name))
            # No names in the message: it goes into the email and the log.
            raise NameMismatch(
                f"STAC returned {len(stac_names)} cases for {ucn} ({matching} with a matching "
                "defendant name). Check which one is right by hand."
            )

        kind = name_match_kind(stac_names[0], child_dir_name)
        if kind is None:
            print("DEFENDANT DOES NOT MATCH 911 CHILD DIRECTORY NAME")
            raise NameMismatch(f"STAC's defendant for {ucn} does not match the directory name.")
        if kind == NAME_MATCH_FUZZY:
            print("DEFENDANT MATCHES 911 CHILD DIRECTORY NAME (fuzzy, one letter off)")
        else:
            print("DEFENDANT MATCHES 911 CHILD DIRECTORY NAME")

        try:
            images_tab = self.wait.until(EC.element_to_be_clickable((By.ID, IMAGES_TAB_OF_CASE_ID)))
            self.driver.execute_script("arguments[0].click();", images_tab)
        except TimeoutException as error:
            raise SystemProblem(f"Could not open the Images tab for {ucn}.") from error

    def open_case_search(self) -> None:
        """
        Gets to a usable Cases search box, whatever page the browser is on.

        After a search, Remove from List clears it in place with no reload.
        If that does not work, the Cases sidebar is tried, and if the box is
        still not usable the page is loaded fresh. STAC leaves the box present
        but disabled after a case is opened, so present is not enough.

        Returns:
            None

        Raises:
            SystemProblem: If the search box cannot be reached any way.
        """
        if self._searched:
            if self.reset_search():
                return
            print("Remove from List did not reset the search; trying the sidebar")

        if self.try_open_case_search():
            return

        print("Search box was not usable; reloading STAC to clear the page")
        try:
            self.driver.get(WEBSITE)
            self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, CASES_SIDEBAR_BUTTON_CSS_SELECTOR)))
        except (TimeoutException, WebDriverException) as error:
            raise SystemProblem(f"Could not get back to STAC's Cases page: {type(error).__name__}") from error

        self._criteria_is_ucn = False
        if not self.try_open_case_search():
            raise SystemProblem("STAC's case search box is still not usable after reloading the page.")

    def reset_search(self) -> bool:
        """
        Presses Remove from List and checks the search box is ready. Never raises.

        The search criteria stay on UCN afterwards, so _criteria_is_ucn is
        left alone. The old UCN stays in the box; search_ucn empties it.

        Returns:
            bool: True if the box is ready, False on any doubt.
        """
        try:
            button = self.wait.until(EC.element_to_be_clickable((By.ID, REMOVE_FROM_LIST_ID)))
            ActionChains(self.driver).move_to_element(button).pause(0.3).click().perform()
            WebDriverWait(self.driver, RESET_CLEAR_SECONDS, poll_frequency=0.25).until(
                lambda d: not self.case_rows_showing()
            )
            self.let_spinner_appear()
            self.wait_out_spinner("Remove from List")
            field = self.wait.until(EC.element_to_be_clickable((By.ID, SEARCH_BAR_FIELD_ID)))
            return field.is_enabled() and field.is_displayed()
        except (TimeoutException, WebDriverException, SystemProblem) as error:
            # SystemProblem is a spinner that would not clear. The reload
            # fallback clears that, so it is not worth stopping for here.
            print(f"Remove from List reset failed ({type(error).__name__})")
            return False

    def case_rows_showing(self) -> bool:
        """
        Checks whether a case row is on screen. Hidden Kendo markup does not count.

        Returns:
            bool: True while any result row is displayed.
        """
        try:
            return any(row.is_displayed() for row in self.driver.find_elements(By.CSS_SELECTOR, CASE_NAME_FROM_STAC_UCN_SEARCH))
        except StaleElementReferenceException:
            return True

    def try_open_case_search(self) -> bool:
        """
        Makes one attempt at reaching a usable search box.

        Returns:
            bool: True if the box is ready, False if not.
        """
        try:
            self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, CASES_SIDEBAR_BUTTON_CSS_SELECTOR))).click()
        except (TimeoutException, WebDriverException):
            return False

        if not self._criteria_is_ucn and not self.choose_ucn_criteria():
            return False

        try:
            field = self.wait.until(EC.element_to_be_clickable((By.ID, SEARCH_BAR_FIELD_ID)))
            return field.is_enabled() and field.is_displayed()
        except (TimeoutException, WebDriverException):
            return False

    def choose_ucn_criteria(self) -> bool:
        """
        Sets the search dropdown to UCN.

        Returns:
            bool: True if UCN was chosen, False if the option was not offered.
        """
        try:
            dropdown_button = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, SEARCH_BAR_DROPDOWN_OPTION_CSS_SELECTOR)))
            self.driver.execute_script("arguments[0].click();", dropdown_button)
        except (TimeoutException, WebDriverException):
            return False

        try:
            ucn_option = self.wait.until(EC.element_to_be_clickable((By.XPATH, UCN_SEARCH_BAR_DROPDOWN_OPTION_XPATH)))
            self.driver.execute_script("arguments[0].click();", ucn_option)
        except (TimeoutException, WebDriverException):
            # A dropdown left open would block the next click.
            try:
                self.driver.switch_to.active_element.send_keys(Keys.ESCAPE)
            except WebDriverException:
                pass
            return False

        self._criteria_is_ucn = True
        return True

    def search_ucn(self, ucn: str) -> list[str]:
        """
        Runs the UCN search and returns the defendant name of every result row.

        Args:
            ucn (str): Universal Case Number to search for.

        Returns:
            list[str]: Defendant names of the displayed rows, at least one.

        Raises:
            CaseNotFound: If no case has that UCN.
            SystemProblem: If the search cannot run or the results never load.
        """
        try:
            self._searched = True
            search_field = self.wait.until(EC.element_to_be_clickable((By.ID, SEARCH_BAR_FIELD_ID)))
            search_field.click()
            # Ctrl+A and Delete, not clear(). clear() left the last UCN in the
            # box after a reset, and after a "no records" search STAC refused
            # the box outright (DALYN, 14 Oct 2026).
            search_field.send_keys(Keys.CONTROL, "a")
            search_field.send_keys(Keys.DELETE)
            search_field.send_keys(ucn)
            search_btn = self.driver.find_element(By.ID, SEARCH_BAR_BUTTON_ID)
            self.driver.execute_script("arguments[0].click();", search_btn)
        except (TimeoutException, WebDriverException) as error:
            raise SystemProblem(f"Could not run the UCN search in STAC: {type(error).__name__}") from error

        # find_elements returns a list, so this is truthy on a result row and
        # on "no records", and keeps waiting while the grid is still loading.
        try:
            self.wait.until(lambda d:
                            d.find_elements(By.CSS_SELECTOR, NO_RECORDS_FOUND_CSS_SELECTOR) or
                            d.find_elements(By.CSS_SELECTOR, CASE_NAME_FROM_STAC_UCN_SEARCH))
        except TimeoutException as error:
            raise SystemProblem(f"STAC's search results never loaded for {ucn}.") from error

        if self.driver.find_elements(By.CSS_SELECTOR, NO_RECORDS_FOUND_CSS_SELECTOR) and not self.found_on_second_look():
            print("NO RECORDS FOUND IN STAC")
            raise CaseNotFound(f"No case in STAC with UCN {ucn}.")

        try:
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, CASE_NAME_FROM_STAC_UCN_SEARCH)))
            names = [row.text.strip() for row in self.driver.find_elements(By.CSS_SELECTOR, CASE_NAME_FROM_STAC_UCN_SEARCH) if row.is_displayed()]
        except (TimeoutException, StaleElementReferenceException) as error:
            raise SystemProblem(f"Search for {ucn} returned a row with no readable defendant name.") from error

        if not names:
            raise SystemProblem(f"Search for {ucn} returned rows but none are displayed.")
        return names

    def found_on_second_look(self) -> bool:
        """
        Looks again for a result row before believing "no records".

        Returns:
            bool: True if a result row showed up after all.

        Raises:
            SystemProblem: If STAC's spinner never clears.
        """
        self.let_spinner_appear()
        self.wait_out_spinner("the search")
        try:
            WebDriverWait(self.driver, NO_RECORDS_RECHECK_SECONDS, poll_frequency=0.25).until(
                lambda d: self.case_rows_showing()
            )
        except TimeoutException:
            return False
        print('"No records" was read before the results loaded; found on a second look')
        return True

    # ------------------------------------------------------------- upload

    def add_files(self, ucn: str, file_list: list) -> None:
        """
        Uploads every file to the open case under DISCOVERY / 911AUDIO and saves.

        Args:
            ucn (str): Universal Case Number, for messages only. The case is already open.
            file_list (list): Absolute local file paths to upload.

        Returns:
            None

        Raises:
            SaveMayHaveHappened: Save was clicked and never confirmed.
            SystemProblem: Anything else in STAC misbehaved. Nothing was saved.
        """
        if self.open_dropzone():
            self.let_spinner_appear()
        self.wait_out_spinner("opening the dropzone")
        self.upload(file_list)
        self.wait_out_spinner("the upload", SPINNER_OUTSIDE_PREVIEW_CSS)
        self.select_image_subtype()
        self.wait_out_spinner("picking 911AUDIO", SPINNER_OUTSIDE_PREVIEW_CSS)
        self.save_and_confirm(ucn, len(file_list))

    def open_dropzone(self) -> bool:
        """
        Gets the Images tab into the state where files can be dropped.

        Clicking an existing image tile is what makes STAC render the
        dropzone, but a case with no images yet has no tile to click and the
        dropzone is there anyway, so only the dropzone itself is required.

        Returns:
            bool: True if an image tile was clicked, since that starts a
                  preview load the caller must let finish.

        Raises:
            SystemProblem: If the dropzone never appears.
        """
        clicked = False
        tiles = self.driver.find_elements(By.CSS_SELECTOR, FIRST_NON_SELECTED_IMAGE_TILE_CSS_SELECTOR)
        if tiles:
            try:
                self.driver.execute_script("arguments[0].click();", tiles[0])
                clicked = True
            except WebDriverException as error:
                print(f"Could not click an image tile: {type(error).__name__}")
        else:
            print("No existing images on this case, going straight to the dropzone")

        try:
            self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, IMAGES_TAB_DROPZONE_PANEL_CSS_SELECTOR)))
        except TimeoutException as error:
            raise SystemProblem("The upload dropzone never appeared.") from error

        self.wait_for_preview()
        return clicked

    def wait_for_preview(self) -> None:
        """
        Lets an existing document's preview settle, if there is one.

        When a preview is loading, letting it finish stops STAC replacing the
        file input under an upload in progress. When there is nothing to
        preview, waiting the full timeout would stall every empty case.

        Returns:
            None
        """
        try:
            WebDriverWait(self.driver, PREVIEW_WAIT_SECONDS).until(
                lambda d: PREVIEW_IFRAME_LOADED_MARKER in (d.find_element(By.CSS_SELECTOR, IMAGES_TAB_PREVIEW_IFRAME_CSS_SELECTOR).get_attribute("src") or "")
            )
        except (TimeoutException, WebDriverException):
            print("No document preview to wait for, continuing")

    def upload(self, file_list: list) -> None:
        """
        Sends the files to the dropzone and waits for every one to confirm.

        Args:
            file_list (list): Absolute local file paths to upload.

        Returns:
            None

        Raises:
            SystemProblem: If the file input is missing or the uploads do not finish.
        """
        try:
            file_input = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, TAB_DROPZONE_FILE_INPUT_CSS_SELECTOR)))
            # The input is hidden behind a class; Selenium cannot type into it until that is removed.
            self.driver.execute_script("arguments[0].removeAttribute('class')", file_input)
        except TimeoutException as error:
            raise SystemProblem("Could not find STAC's file input.") from error

        # The browser now outlives a case, so the last case's success messages
        # can still be in the page. Counting from what is already there stops
        # them from passing this wait before the new files have finished.
        already_listed = len(self.driver.find_elements(By.XPATH, FILE_UPLOAD_SUCCESS_XPATH))

        try:
            file_input.send_keys("\n".join(file_list))
            WebDriverWait(self.driver, FILE_UPLOAD_WAIT_TIMEOUT_SECONDS).until(
                lambda d: len(d.find_elements(By.XPATH, FILE_UPLOAD_SUCCESS_XPATH)) >= already_listed + len(file_list)
            )
        except TimeoutException as error:
            raise SystemProblem(f"Only some of the {len(file_list)} file(s) finished uploading within {FILE_UPLOAD_WAIT_TIMEOUT_SECONDS}s.") from error

        print(f"{len(file_list)}/{len(file_list)} files uploaded successfully.")

        # The preview iframe's resize handler leaks memory across every
        # document viewed in the case, and the iframe can intercept Save.
        self.driver.execute_script("let f = document.querySelector(arguments[0]); if (f) { f.remove(); }", IMAGES_TAB_PREVIEW_IFRAME_CSS_SELECTOR)

    def select_image_subtype(self) -> None:
        """
        Selects DISCOVERY / 911AUDIO from the image type/subtype matrix dialog.

        Returns:
            None

        Raises:
            SystemProblem: If the find button, matrix search box, 911AUDIO row,
                           or Select button never become usable.
        """
        try:
            find_button = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, IMAGE_SUB_TYPE_FIND_BUTTON_CSS_SELECTOR)))
            self.driver.execute_script("arguments[0].click();", find_button)
        except TimeoutException as error:
            raise SystemProblem("Could not locate the Subtype Find Button.") from error

        try:
            search_box = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, MATRIX_SEARCH_INPUT_CSS_SELECTOR)))
            search_box.send_keys(MATRIX_SEARCH_TERM)
        except TimeoutException as error:
            raise SystemProblem("Could not locate the matrix search box.") from error

        try:
            row = self.wait.until(EC.visibility_of_element_located((By.XPATH, IMAGE_SUB_TYPE_ROW_XPATH)))
            self.driver.execute_script("arguments[0].click();", row)
        except TimeoutException as error:
            raise SystemProblem("Could not locate the DISCOVERY / 911AUDIO row.") from error

        try:
            time.sleep(KENDO_INTERVAL_RECOVERY_PAUSE_SECONDS)  # STAC setInterval bug: Kendo drops a click that comes too soon
            select_btn = self.wait.until(EC.element_to_be_clickable((By.ID, SELECT_BUTTON_ID)))
            self.driver.execute_script("arguments[0].click();", select_btn)
        except TimeoutException as error:
            raise SystemProblem("Could not locate the Select Button.") from error

    def save_and_confirm(self, ucn: str, file_count: int) -> None:
        """
        Presses Save and waits for STAC to confirm.

        Every browser error is sorted by where it happened. Before the click,
        nothing was saved and a retry is safe. From the click on, STAC may
        already have the audio, so the case goes to a person instead.

        Args:
            ucn (str): Universal Case Number, for messages only.
            file_count (int): Number of files in this upload, for messages only.

        Returns:
            None

        Raises:
            SaveMayHaveHappened: Save was clicked but no confirmation came.
            SystemProblem: Save could not be pressed at all.
        """
        upload_wait = WebDriverWait(self.driver, FILE_UPLOAD_WAIT_TIMEOUT_SECONDS)

        # The subtype reaches the form through Kendo a moment after the dialog
        # closes. Saving before it lands files under whatever was there before.
        try:
            upload_wait.until(lambda d: d.execute_script(f"return $(\"{IMAGE_SUB_TYPE_INPUT_ID}\").data('kendoDropDownList').value()") == MATRIX_SEARCH_TERM)
        except TimeoutException as error:
            raise SystemProblem(f"Subtype never showed {MATRIX_SEARCH_TERM} before Save.") from error
        except BROWSER_ERRORS as error:
            raise SystemProblem(f"The browser failed while checking the Subtype before Save: {type(error).__name__}") from error

        # The browser now outlives a case, so the last case's saved notification
        # could still be up, and it would pass the confirmation wait below for
        # a save that never happened. Nothing is saved yet, so a retry is safe.
        try:
            WebDriverWait(self.driver, WEBDRIVER_WAIT_TIMEOUT_SECONDS, poll_frequency=0.25).until(
                lambda d: not self.saved_notification_showing(if_unsure=True)
            )
        except TimeoutException as error:
            raise SystemProblem("The last case's saved notification was still showing before Save.") from error
        except BROWSER_ERRORS as error:
            raise SystemProblem(f"The browser failed while checking for an old saved notification: {type(error).__name__}") from error

        # A covered click never reaches the button, so nothing is saved and a retry is safe.
        press = PressWhenUncovered(SAVE_IMAGE_BUTTON)
        try:
            upload_wait.until(press)
        except TimeoutException as error:
            raise SystemProblem(f"Could not press Save: {press.blocker}.") from error
        except BROWSER_ERRORS as error:
            if not press.clicking:
                raise SystemProblem(f"The browser failed before Save was clicked: {type(error).__name__}") from error
            raise SaveMayHaveHappened(
                f"The browser failed while clicking Save for {file_count} file(s) on {ucn} "
                f"({type(error).__name__}). The audio may or may not be on the case. Check it by hand."
            ) from error

        # Past this line STAC may already have the audio. Shown, not just
        # present: Kendo can keep a hidden notification in the page, and none
        # was showing before the click, so a shown one is this save's.
        try:
            upload_wait.until(lambda d: self.saved_notification_showing(if_unsure=False))
        except BROWSER_ERRORS as error:
            # TimeoutException is a WebDriverException, so it lands here too.
            reason = "STAC never confirmed" if isinstance(error, TimeoutException) else f"the browser failed before STAC confirmed ({type(error).__name__})"
            raise SaveMayHaveHappened(
                f"Pressed Save for {file_count} file(s) on {ucn} but {reason}. "
                "The audio may or may not be on the case. Check it by hand."
            ) from error

        # Wait for the notification to clear, or it covers the next case's
        # Save button. The save is confirmed by now, so a failure here only warns.
        try:
            upload_wait.until(EC.invisibility_of_element_located((By.XPATH, IMAGE_SAVED_NOTIFICATION_XPATH)))
        except TimeoutException:
            print("Warning: the saved notification did not clear")
        except BROWSER_ERRORS as error:
            print(f"Warning: the browser failed after STAC confirmed the save ({type(error).__name__})")

        print("Image saved successfully.")

    def saved_notification_showing(self, if_unsure: bool) -> bool:
        """
        Checks whether STAC's green saved notification is shown.

        Args:
            if_unsure (bool): What to answer when a notification is replaced
                              mid-check. Each caller passes the answer that
                              keeps it waiting, never the one that lets it pass.

        Returns:
            bool: True while one is shown, False when none is or only hidden ones are.
        """
        try:
            return any(note.is_displayed() for note in self.driver.find_elements(By.XPATH, IMAGE_SAVED_NOTIFICATION_XPATH))
        except StaleElementReferenceException:
            return if_unsure

    # ----------------------------------------------------------- spinners

    def wait_out_spinner(self, after: str, css: str = SPINNER_CSS) -> None:
        """
        Waits for STAC's loading spinner to clear before the next step.

        Args:
            after (str): The step just done, for messages, e.g. "the upload".
            css (str): Which spinners count.

        Returns:
            None

        Raises:
            SystemProblem: If the spinner is still up after the upload timeout.
                           Nothing has been saved yet, so a retry in a fresh
                           browser is safe.
        """
        if not self.spinner_showing(css):
            return
        started = time.monotonic()
        try:
            WebDriverWait(self.driver, FILE_UPLOAD_WAIT_TIMEOUT_SECONDS, poll_frequency=0.25).until(
                lambda d: not self.spinner_showing(css)
            )
        except TimeoutException as error:
            raise SystemProblem(f"STAC's loading spinner was still up {FILE_UPLOAD_WAIT_TIMEOUT_SECONDS}s after {after}.") from error
        print(f"STAC's loading spinner cleared {time.monotonic() - started:.1f}s after {after}")

    def let_spinner_appear(self) -> None:
        """
        Gives a spinner that has not shown yet a moment to show.

        Returns as soon as one shows, or after SPINNER_APPEAR_SECONDS if none
        does. This only stops a spinner that is about to appear from being missed.

        Returns:
            None
        """
        try:
            WebDriverWait(self.driver, SPINNER_APPEAR_SECONDS, poll_frequency=0.1).until(lambda d: self.spinner_showing())
        except TimeoutException:
            pass

    def spinner_showing(self, css: str = SPINNER_CSS) -> bool:
        """
        Checks whether any Kendo loading spinner matching css is shown.

        Args:
            css (str): Which spinners count.

        Returns:
            bool: True while one is shown. One replaced mid-check counts as shown.
        """
        try:
            return any(spinner.is_displayed() for spinner in self.driver.find_elements(By.CSS_SELECTOR, css))
        except StaleElementReferenceException:
            return True

    # --------------------------------------------------------------- case

    def upload_case(self, ucn: str, file_list: list, child_dir_name: str) -> None:
        """
        Finds the case and uploads its files, retrying once in a fresh browser.

        Signs in on the first call. A CaseProblem is never retried: a missing
        case or a name mismatch does not improve by trying again, and a retry
        after SaveMayHaveHappened could file the audio twice.

        Args:
            ucn (str): Universal Case Number to search in STAC.
            file_list (list): Absolute local file paths to upload.
            child_dir_name (str): FTP directory name, for the defendant check.

        Returns:
            None

        Raises:
            CaseNotFound: No case with that UCN.
            NameMismatch: Several cases, or the defendant does not match.
            SaveMayHaveHappened: Save was clicked with no confirmation.
            SystemProblem: STAC is broken and the retry is used up.
        """
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                self.open()
                self.find_case(ucn, child_dir_name)
                self.add_files(ucn, file_list)
                return

            except (CaseNotFound, NameMismatch):
                # Only a search result list is left behind, which the next
                # search resets with Remove from List.
                raise

            except SaveMayHaveHappened:
                self.leave_browser_clean()
                raise

            except (SystemProblem, *BROWSER_ERRORS) as caught:
                error = caught if isinstance(caught, SystemProblem) else SystemProblem(f"The browser failed: {type(caught).__name__}")
                if attempt >= MAX_ATTEMPTS:
                    # main.py stops the run on this, so a refresh would only
                    # delay the email; with STAC down it costs a minute or more.
                    self.close()
                    if error is caught:
                        raise
                    raise error from caught

                print(f"{ucn}: attempt {attempt} of {MAX_ATTEMPTS} failed ({error}). Restarting the browser.")
                # close() then let the next attempt's open() sign in again, so
                # a failed sign-in here is retried rather than raised.
                self.close()

        # The loop either returns or raises; this is unreachable.
        raise SystemProblem(f"{ucn}: ran out of attempts without a result.")

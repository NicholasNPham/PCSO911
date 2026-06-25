"""
STAC Web Scraper Module

Handles login, navigation, searching, and adding images to cases
via the STAC web interface using Selenium WebDriver automation.
"""

# Standard Library Imports
import re
import time

# Third-party Imports
from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from webdriver_manager.chrome import ChromeDriverManager

# Local Imports
from ftp_outlook_error import send_error_email
from key import WEBSITE, STAC3_USERNAME, STAC3_PASSWORD

# CONSTANTS
PAUSE_BETWEEN_ACTIONS_SECONDS = 1
WEBDRIVER_WAIT_TIMEOUT_SECONDS = 5
FILE_UPLOAD_WAIT_TIMEOUT_SECONDS = 60
EXCLUDED_TOKENS = {"AM", "SVP", "AME", "SO", "AMSP", "JLA", "PJLA", "SP", "ALERT", "BKGRDALERT", "CP", "DO", "NOT", "USE", "GANG", "NCP", "NO", "CC", "OSCP", "SPCALERT", "TTP", "VFOSC", "HA"}

# HTML
#LOGIN
LOGIN_DROPDOWN_MENU_ID = 'LoginProvider'
USERNAME_AND_PASSWORD_DROPDOWN_MENU_VALUE = 'Local'
USERNAME_FIELD_ID = 'Username'
PASSWORD_FIELD_ID = 'Password'
SUBMIT_LOGIN_BUTTON_ID = 'submitLogin'

# CASES SIDEBAR PAGE
CASES_SIDEBAR_BUTTON_CSS_SELECTOR = "[data-menuid='incident']"

# SEARCHING UCN AND RESULTS
SEARCH_BAR_DROPDOWN_OPTION_CSS_SELECTOR = "button[role='button'][aria-label='select']"
SEARCH_BAR_DROPDOWN_LISTBOX_ID = "incidentsSearchMainCriteria_listbox"
UCN_SEARCH_BAR_DROPDOWN_OPTION_XPATH = "//ul[@id='incidentsSearchMainCriteria_listbox' and not(contains(@style,'display: none'))]//span[text()='UCN']"
SEARCH_BAR_FIELD_ID = "incidentsSearchMainSearchValue"
SEARCH_BAR_BUTTON_ID = "incidentsSearchMainButton"
NO_RECORDS_FOUND_CSS_SELECTOR = ".k-grid-norecords-template"
CASE_NAME_FROM_STAC_UCN_SEARCH = "td[data-original-column-name='Def_Name'] span.k-button-text"

# ADD IMAGE PAGE
IMAGES_TAB_OF_CASE_ID = "incidentsTab-tab-3"
ADD_BUTTON_BAR_OF_IMAGES_ID = "AddNewImagesTab"
ADD_IMAGE_NEW_IMAGE_MENU_ITEM_CSS_SELECTOR = "ul#AddNewImagesTab_buttonmenu li[data-id='newImage']"

# ADD IMAGE TYPE DROPDOWN MENU
SELECT_FILES_BUTTON_CSS_SELECTOR = ".k-upload-button"
IMAGE_SUB_TYPE_FIND_BUTTON_ID = "image_sub_typeFindButton"
IMAGE_SUB_TYPE_ROW_XPATH = "//span[text()='911AUDIO']"
SELECT_BUTTON_XPATH = "//span[text()='Select']/parent::button"

# UPLOADING AND SAVING FILES
ADD_IMAGE_UPLOAD_DROPBOX_CSS_SELECTOR = "input[id^='cipFileUpload_TelerikUpload']"
FILE_UPLOAD_SUCCESS_XPATH = "//span[contains(@class,'k-file-validation-message') and text()='File(s) uploaded successfully.']"
SAVE_IMAGE_BUTTON = "SaveImage"

# CONFIRMATION OF SAVE
IMAGE_SAVED_NOTIFICATION_XPATH = "//div[contains(@class,'c-notification-success')]"

# FUNCTIONS
def names_match(stac_name: str, child_dir_name: str) -> bool:
    """
    Check whether two names are a fuzzy match by comparing their word tokens.

    Strips parenthetical content from the STAC name, tokenizes both names into
    uppercase alphabetic words, filters out excluded tokens, and returns True if
    either token set is a subset of the other.

    Args:
        stac_name (str): The name from the STAC catalog (may contain parenthetical content).
        child_dir_name (str): The directory name to compare against.

    Returns:
        bool: True if one token set is a subset of the other, False otherwise.
    """
    stac_name = re.sub(r'\(.*?\)', '', stac_name)
    stac_tokens = set(w for w in re.findall(r'[a-zA-Z]+', stac_name.upper()) if w not in EXCLUDED_TOKENS)
    dir_tokens = set(w for w in re.findall(r'[a-zA-Z]+', child_dir_name.upper()) if w not in EXCLUDED_TOKENS)

    # Uncomment to Test
    # print(f"STAC tokens: {stac_tokens}")
    # print(f"DIR tokens: {dir_tokens}")

    return stac_tokens.issubset(dir_tokens) or dir_tokens.issubset(stac_tokens)

def setup_browser() -> tuple:
    """Open Chrome, log in to STAC website, and wait for the sidebar.

    Returns:
        tuple (WebDriver, WebDriverWait): Initialized driver and wait object.

    Raises:
        WebDriverException: If Chrome or chromedriver fails to launch.
        TimeoutException: If the sidebar element does not appear after login.
    """
    # DRIVER SET-UP
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)
    wait = WebDriverWait(driver, WEBDRIVER_WAIT_TIMEOUT_SECONDS)
    driver.get(WEBSITE) # Initialized the Chromedriver with the Website.
    driver.maximize_window() # Maximizes the Website

    return driver, wait

def browser_login(driver: webdriver.Chrome, wait: WebDriverWait) -> tuple:
    """
    Log in to the STAC website using stored credentials.

    Args:
        driver (WebDriver): Selenium Chrome driver.
        wait (WebDriverWait): WebDriverWait object for explicit waits.

    Returns:
        tuple (WebDriver, WebDriverWait): Unchanged driver and wait for chaining.

    Raises:
        TimeoutException: If the login fields or sidebar button fail to become clickable.
    """
    # LOGIN PATH

    dropdown_element = wait.until(EC.presence_of_element_located((By.ID, LOGIN_DROPDOWN_MENU_ID))) # Targets the "Authenticate Using" Dropdown Menu
    dropdown = Select(dropdown_element) # Targets the Dropdown Menu to Dropdown.
    dropdown.select_by_value(USERNAME_AND_PASSWORD_DROPDOWN_MENU_VALUE) # Selects Value "0" which is "Username and Password"

    wait.until(EC.element_to_be_clickable((By.ID, USERNAME_FIELD_ID))).send_keys(STAC3_USERNAME) # finds username field enters username
    wait.until(EC.element_to_be_clickable((By.ID, PASSWORD_FIELD_ID))).send_keys(STAC3_PASSWORD) # finds password field and enters password
    driver.find_element(By.ID, SUBMIT_LOGIN_BUTTON_ID).click() # clicks submit to log in.
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, CASES_SIDEBAR_BUTTON_CSS_SELECTOR))) # Waits for the "Cases Sidebar Button" to be clickable in order to move on.

    return driver, wait

def navigate_to_search(driver: webdriver.Chrome, wait: WebDriverWait) -> tuple:
    """Navigate to the search menu and prepare the dropdown for case search.

    Args:
        driver (WebDriver): Selenium Chrome driver.
        wait (WebDriverWait): WebDriverWait object for explicit waits.

    Returns:
        tuple (WebDriver, WebDriverWait): Unchanged driver and wait for chaining.

    Raises:
        TimeoutException: If any navigation element fails to become clickable.
    """
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, CASES_SIDEBAR_BUTTON_CSS_SELECTOR))).click()
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, SEARCH_BAR_DROPDOWN_OPTION_CSS_SELECTOR))).click()
    ucn_option = wait.until(EC.element_to_be_clickable((By.XPATH, UCN_SEARCH_BAR_DROPDOWN_OPTION_XPATH)))
    driver.execute_script("arguments[0].click();", ucn_option)

    return driver, wait

def search_by_ucn(driver: webdriver.Chrome, wait: WebDriverWait, ucn_value: str, child_dir_name: str) -> tuple:
    """Search for a case by Universal Case Number (UCN).

    Args:
        driver (WebDriver): Selenium Chrome driver.
        wait (WebDriverWait): WebDriverWait object for explicit waits.
        ucn_value (str): 1 Universal Case Number to search for.
        child_dir_name (str): the filename of the child directory

    Returns:
        tuple (WebDriver, WebDriverWait): Unchanged driver and wait for chaining.

    Raises:
        TimeoutException: If the UCN dropdown option fails to become clickable.
        NoSuchElementException: If the search field or button cannot be found.
    """

    search_field = wait.until(EC.element_to_be_clickable((By.ID, SEARCH_BAR_FIELD_ID))) # Initializes the "Searchbar Field" to be ready
    search_field.clear() # Clears the "Searchbar Field".
    search_field.click() # Clicks the "Searchbar Field".
    search_field.send_keys(ucn_value) # Sends the "UCN values" to be "Typed in the "Searchbar Field"
    driver.find_element(By.ID, SEARCH_BAR_BUTTON_ID).click() # Clicks the "Search Button to Search"

    """
    find_elements: always returns a list; either populated or empty.
    wait.until: Repeats the call until it returns a "truthy list" or times out.
    
    Three Results:
    - Returns a name found in the row. -> "Truthy"
    - Returns "No Record Found" -> "Truthy"
    - Returns "[]" -> False
    """
    wait.until(lambda d:
               d.find_elements(By.CSS_SELECTOR, NO_RECORDS_FOUND_CSS_SELECTOR) or
               d.find_elements(By.CSS_SELECTOR, CASE_NAME_FROM_STAC_UCN_SEARCH)
               )

    no_records = driver.find_elements(By.CSS_SELECTOR, NO_RECORDS_FOUND_CSS_SELECTOR) # If "No Records Found" is "Truthy" print and return False.
    if no_records:
        print("NO RECORDS FOUND IN STAC")
        print("-------------------")
        return (driver, wait), False

    stac_case_name = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, CASE_NAME_FROM_STAC_UCN_SEARCH))).text # If name found, initialize the name in the variable
    is_match = names_match(stac_case_name, child_dir_name) # Calls the function names_match to determine if the name found matches the child directory name tokens.

    # Uncomment to Test
    # print(f"STAC name: '{stac_case_name}'")
    # print(f"DIR name: '{child_dir_name}'")

    if is_match:
        images_tab = wait.until(EC.element_to_be_clickable((By.ID, IMAGES_TAB_OF_CASE_ID)))
        driver.execute_script("arguments[0].click();", images_tab)
        print("DEFENDANT MATCHES 911 CHILD DIRECTORY NAME")
        print("-------------------")
    else:
        print("DEFENDANT DOES NOT MATCH 911 CHILD DIRECTORY NAME")
        print("-------------------")

    return (driver, wait), is_match

def wait_for_all_uploads(wait: WebDriverWait, expected_count: int) -> bool:
    """
    Waits until the number of successfully uploaded files matches expected count.

    Args:
        wait (WebDriverWait): WebDriverWait object.
        expected_count (int): Number of files expected to finish uploading.

    Returns:
        bool: True when all files are confirmed uploaded.
    """
    wait.until(lambda d: len(d.find_elements(By.XPATH, FILE_UPLOAD_SUCCESS_XPATH))  >= expected_count)
    print(f"{expected_count}/{expected_count} files uploaded successfully.")
    return True

def navigate_to_add_image_dialog(driver: webdriver.Chrome, wait: WebDriverWait) -> tuple:
    """
    Navigates to the Add Image dialog and selects the 911AUDIO type and subtype.

    Args:
        driver (WebDriver): Selenium Chrome driver.
        wait (WebDriverWait): WebDriverWait object for explicit waits.

    Returns:
        tuple (WebDriver, WebDriverWait): Unchanged driver and wait for chaining.

    Raises:
        TimeoutException: If any dialog element fails to become visible or clickable.
    """

    try:
        # Finds the 'Image' Tab and Press '+ Add' and Selects 'New Image'
        time.sleep(1)
        add_button = wait.until(EC.element_to_be_clickable((By.ID, ADD_BUTTON_BAR_OF_IMAGES_ID)))
        driver.execute_script("arguments[0].click();", add_button)
        new_image_item = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ADD_IMAGE_NEW_IMAGE_MENU_ITEM_CSS_SELECTOR)))
        driver.execute_script("arguments[0].click();", new_image_item)
    except TimeoutException as IMAGE_TAB_ERROR:
        print(f"Could not locate the Image Tab: {IMAGE_TAB_ERROR}")
        send_error_email(f"Could not locate the Image Tab: {IMAGE_TAB_ERROR}")
        raise

    try:
        # Finding the Correct Type and Subtype
        wait.until(EC.visibility_of_element_located((By.ID, IMAGE_SUB_TYPE_FIND_BUTTON_ID))) # Waits for the "add" button to be clickable then clicks
        find_button = wait.until(EC.element_to_be_clickable((By.ID, IMAGE_SUB_TYPE_FIND_BUTTON_ID))) # Finds the first item inside the dropdown menu.
        driver.execute_script("arguments[0].click();", find_button) # Uses Javascript to click the first item in the dropdown menu.
    except TimeoutException as SUBTYPE_LIST_ERROR:
        print(f"Could not locate the Subtype List: {SUBTYPE_LIST_ERROR}")
        send_error_email(f"Could not locate the Subtype List: {SUBTYPE_LIST_ERROR}")
        raise

    try:
        # Finds the correct subtype
        row = wait.until(EC.visibility_of_element_located((By.XPATH, IMAGE_SUB_TYPE_ROW_XPATH)))
        driver.execute_script("arguments[0].click();", row)
    except TimeoutException as SELECT_SUBTYPE_ERROR:
        print(f"Could not locate the Subtype: {SELECT_SUBTYPE_ERROR}")
        send_error_email(f"Could not locate the Subtype: {SELECT_SUBTYPE_ERROR}")
        raise

    try:
        # presses the select button to confirm subtype
        select_btn = wait.until(EC.visibility_of_element_located((By.XPATH, SELECT_BUTTON_XPATH)))
        driver.execute_script("arguments[0].click();", select_btn)
    except TimeoutException as SELECT_BUTTON_ERROR:
        print(f"Could not locate the Select Button: {SELECT_BUTTON_ERROR}")
        send_error_email(f"Could not locate the Select Button: {SELECT_BUTTON_ERROR}")
        raise

    return driver, wait

def upload_files(driver: webdriver.Chrome, wait: WebDriverWait, file_list: list) -> tuple:
    """
    Sends local file paths to the hidden file input and waits for all uploads to complete.

    Args:
        driver (WebDriver): Selenium Chrome driver.
        wait (WebDriverWait): WebDriverWait object for explicit waits.
        file_list (list): List of absolute local file paths to upload.

    Returns:
        tuple (WebDriver, WebDriverWait): Unchanged driver and wait for chaining.

    Raises:
        TimeoutException: If the file input is not found or uploads do not complete.
    """
    # Send file path directly to hidden input — bypasses OS file dialog entirely
    try:
        file_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ADD_IMAGE_UPLOAD_DROPBOX_CSS_SELECTOR)))
        driver.execute_script("arguments[0].removeAttribute('class')", file_input)  # unhide the input
    except TimeoutException as DROPBOX_TIMEOUT:
        print(f"Could not find Dropbox area: {DROPBOX_TIMEOUT}")
        send_error_email(f"Could not find Dropbox area: {DROPBOX_TIMEOUT}")
        raise

    # Uploading Files to the DropBox
    try:
        file_input.send_keys("\n".join(file_list))
        wait_for_all_uploads(wait, len(file_list))
    except TimeoutException as DROPBOX_UPLOAD_TIMEOUT:
        print(f"Took to long to upload in dropbox: {DROPBOX_UPLOAD_TIMEOUT}")
        send_error_email(f"Took to long to upload in dropbox: {DROPBOX_UPLOAD_TIMEOUT}")
        raise

    return driver, wait

def save_and_confirm(driver: webdriver.Chrome) -> None:
    """
    Clicks the Save button and waits for the success notification to confirm the image was saved.

    Args:
        driver (WebDriver): Selenium Chrome driver.

    Returns:
        None
    """
    upload_wait = WebDriverWait(driver, FILE_UPLOAD_WAIT_TIMEOUT_SECONDS)

    try:
        upload_wait.until(EC.element_to_be_clickable((By.ID, SAVE_IMAGE_BUTTON))).click()
    except TimeoutException as SAVE_BUTTON_TIMEOUT:
        print(f"Could not press the save button: {SAVE_BUTTON_TIMEOUT}")
        send_error_email(f"Could not press the save button: {SAVE_BUTTON_TIMEOUT}")
        raise

    try:
        upload_wait.until(EC.presence_of_element_located((By.XPATH, IMAGE_SAVED_NOTIFICATION_XPATH)))
    except TimeoutException as IMAGE_SAVED_NOTIFICATION_POPUP_TIMEOUT:
        print(f"Could not locate the popup after pressing save 'Image Saved'. : {IMAGE_SAVED_NOTIFICATION_POPUP_TIMEOUT}")
        send_error_email(f"Could not locate the popup after pressing save 'Image Saved'. : {IMAGE_SAVED_NOTIFICATION_POPUP_TIMEOUT}")
        raise

    try:
        upload_wait.until(EC.invisibility_of_element_located((By.XPATH, IMAGE_SAVED_NOTIFICATION_XPATH)))
    except TimeoutException as IMAGE_SAVED_NOTIFICATION_POPUP_DISAPPEAR_TIMEOUT:
        print(f'Popup did not disappear: {IMAGE_SAVED_NOTIFICATION_POPUP_DISAPPEAR_TIMEOUT}')
        send_error_email(f'Popup did not disappear: {IMAGE_SAVED_NOTIFICATION_POPUP_DISAPPEAR_TIMEOUT}')
        raise

    print("Image saved successfully.")

    return None

def add_image(driver: webdriver.Chrome, wait: WebDriverWait, file_list: list) -> None:
    """
    Orchestrates the full image upload workflow: navigates to the Add Image dialog,
    uploads files, and confirms the save.

    Args:
        driver (WebDriver): Selenium Chrome driver.
        wait (WebDriverWait): WebDriverWait object for explicit waits.
        file_list (list): List of absolute local file paths to upload.

    Returns:
        None
    """
    navigate_to_add_image_dialog(driver, wait)
    upload_files(driver, wait, file_list)
    save_and_confirm(driver)

    return None

def teardown_browser(driver: webdriver.Chrome) -> None:
    """
    Closes the browser and ends the WebDriver session.

    Args:
        driver: The active Selenium WebDriver instance

    Returns:
        None
    """
    driver.quit()

# MAIN LOOP FUNCTIONS
def run_stac_script(universal_case_number: str, file_list_from_dict: list, child_dir_name: str) -> bool:
    """
    Orchestrates the full STAC workflow: launches browser, logs in, searches by UCN,
    and uploads files if a matching case is found.

    Args:
        universal_case_number (str): Universal Case Number to search in STAC.
        file_list_from_dict (list): List of absolute local file paths to upload.
        child_dir_name (str): FTP child directory name used for defendant name matching.

    Returns:
        bool: True if a matching case was found and files were uploaded, False otherwise.
    """
    is_match = False
    driver, wait = setup_browser()
    try:
        driver, wait = browser_login(driver, wait)
        driver, wait = navigate_to_search(driver, wait)
        (driver, wait), is_match = search_by_ucn(driver, wait, universal_case_number, child_dir_name)
        if is_match:
            add_image(driver, wait, file_list_from_dict)
    finally:
        teardown_browser(driver)

    return is_match

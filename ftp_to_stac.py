"""
STAC Web Scraper Module

Handles login, navigation, searching, and adding images to cases
via the STAC web interface using Selenium WebDriver automation.
"""

# Standard Library Imports
import time
import re

# Third-party Imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Local Imports
from key import *

# CONSTANTS
CHROME_PATH = 'chromedriver-win64/chromedriver.exe'
PAUSE_BETWEEN_ACTIONS_SECONDS = 1
WEBDRIVER_WAIT_TIMEOUT_SECONDS = 5
EXCLUDED_TOKENS = {"AM", "SVP", "AME", "SO", "AMSP", "JLA", "PJLA", "SP", "ALERT", "BKGRDALERT", "CP", "DO", "NOT", "USE", "GANG", "NCP", "NO", "CC", "OSCP", "SPCALERT", "TTP", "VFOSC", "HA"}

# HTML
USERNAME_FIELD_ID = 'Username'
PASSWORD_FIELD_ID = 'Password'
SUBMIT_LOGIN_BUTTON_ID = 'submitLogin'
CASES_SIDEBAR_BUTTON_CSS_SELECTOR = "[data-menuid='incident']"
SEARCH_BAR_DROPDOWN_OPTION_CSS_SELECTOR = "button[role='button'][aria-label='select']"
UCN_SEARCH_BAR_DROPDOWN_OPTION_XPATH = "//li[@role='option']//span[text()='UCN']"
SEARCH_BAR_FIELD_ID = "incidentsSearchMainSearchValue"
SEARCH_BAR_BUTTON_ID = "incidentsSearchMainButton"
IMAGES_TAB_OF_CASE_ID = "incidentsTab-tab-3"
ADD_BUTTON_BAR_OF_IMAGES_ID = "AddNewImagesTab"
ADD_IMAGE_DROPDOWN_MENU_CSS_SELECTOR = "[data-id='newImage']"
SELECT_FILES_BUTTON_CSS_SELECTOR = ".k-upload-button"
IMAGE_SUB_TYPE_FIND_BUTTON_ID = "image_sub_typeFindButton"
IMAGE_SUB_TYPE_ROW_XPATH = "//span[text()='911AUDIO']"
SELECT_BUTTON_XPATH = "//span[text()='Select']/parent::button"
ADD_IMAGE_UPLOAD_DROPBOX_CSS_SELECTOR = "input[id^='cipFileUpload_TelerikUpload']"
CASE_NAME_FROM_STAC_UCN_SEARCH = "td[data-original-column-name='Def_Name'] span.k-button-text"

def names_match(stac_name, child_dir_name):
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

    # Uncommit This to View Name Tokens
    # print(f"STAC tokens: {stac_tokens}")
    # print(f"DIR tokens: {dir_tokens}")

    return stac_tokens.issubset(dir_tokens) or dir_tokens.issubset(stac_tokens)

# FUNCTIONS
def setup_browser():
    """Open Chrome, log in to STAC website, and wait for the sidebar.

    Returns:
        tuple (WebDriver, WebDriverWait): Initialized driver and wait object.

    Raises:
        WebDriverException: If Chrome or chromedriver fails to launch.
        TimeoutException: If the sidebar element does not appear after login.
    """
    # DRIVER SET-UP
    service = Service(CHROME_PATH)
    driver = webdriver.Chrome(service=service)
    wait = WebDriverWait(driver, WEBDRIVER_WAIT_TIMEOUT_SECONDS)
    driver.get(WEBSITE) # opens to the website.
    driver.maximize_window() # maximizes the web driver
    # LOGIN PATH
    wait.until(EC.element_to_be_clickable((By.ID, USERNAME_FIELD_ID))).send_keys(STAC3_USERNAME) # finds username field enters username
    wait.until(EC.element_to_be_clickable((By.ID, PASSWORD_FIELD_ID))).send_keys(STAC3_PASSWORD) # finds password field and enters password
    driver.find_element(By.ID, SUBMIT_LOGIN_BUTTON_ID).click() # clicks submit to log in.
    # wait for the sidebar button to appear (proof login worked)
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, CASES_SIDEBAR_BUTTON_CSS_SELECTOR)))

    return (driver, wait)

def navigate_to_search(driver, wait):
    """Navigate to the search menu and prepare the dropdown for case search.

    Args:
        driver (WebDriver): Selenium Chrome driver.
        wait (WebDriverWait): WebDriverWait object for explicit waits.

    Returns:
        tuple (WebDriver, WebDriverWait): Unchanged driver and wait for chaining.

    Raises:
        TimeoutException: If any navigation element fails to become clickable.
    """
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, CASES_SIDEBAR_BUTTON_CSS_SELECTOR))).click() # clicks on cases sidebar
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, SEARCH_BAR_DROPDOWN_OPTION_CSS_SELECTOR))).click() # clicks on the dropdown menu
    wait.until(EC.element_to_be_clickable((By.XPATH, UCN_SEARCH_BAR_DROPDOWN_OPTION_XPATH))).click() # this only waits to see if any one of the options is clickable

    return (driver, wait)

def search_by_ucn(driver, wait, ucn_value, child_dir_name):
    """Search for a case by Universal Case Number (UCN).

    Args:
        driver (WebDriver): Selenium Chrome driver.
        wait (WebDriverWait): WebDriverWait object for explicit waits.
        ucn_value (str):1 HO Universal Case Number to search for.

    Returns:
        tuple (WebDriver, WebDriverWait): Unchanged driver and wait for chaining.

    Raises:
        TimeoutException: If the UCN dropdown option fails to become clickable.
        NoSuchElementException: If the search field or button cannot be found.
    """
    wait.until(EC.element_to_be_clickable((By.XPATH, UCN_SEARCH_BAR_DROPDOWN_OPTION_XPATH))).click()
    driver.find_element(By.ID, SEARCH_BAR_FIELD_ID).send_keys(ucn_value)
    driver.find_element(By.ID, SEARCH_BAR_BUTTON_ID).click()
    stac_case_name = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, CASE_NAME_FROM_STAC_UCN_SEARCH))).text
    is_match = names_match(stac_case_name, child_dir_name)
    if is_match:
        wait.until(EC.element_to_be_clickable((By.ID, IMAGES_TAB_OF_CASE_ID))).click()
        print("DEFENDANT MATCHES 911 CHILD DIRECTORY NAME")
        print("-------------------")
    else:
        print("DEFENDANT DOES NOT MATCH 911 CHILD DIRECTORY NAME")
        print("-------------------")

    # Uncommit this to View STAC & DIR Name
    # print(f"STAC name: '{stac_case_name}'")
    # print(f"DIR name: '{child_dir_name}'")

    time.sleep(PAUSE_BETWEEN_ACTIONS_SECONDS)

    return (driver, wait), is_match

def add_image(driver, wait, file_list):
    """Navigate to the Images tab and trigger the file upload dialog.

    Args:
        driver (WebDriver): Selenium Chrome driver.
        wait (WebDriverWait): WebDriverWait object for explicit waits.
        file_list (list): List of files to add.

    Returns:
        tuple (WebDriver, WebDriverWait): Unchanged driver and wait for chaining.

    Raises:
        TimeoutException: If the Images tab or Add button fails to become clickable.
        NoSuchElementException: If the dropdown menu or file upload button cannot be found.
    """

    # Testing to see if the all listview content needs to finish loading before new image can be clicked
    # wait.until(EC.element_to_be_clickable((By.ID, IMAGES_TAB_OF_CASE_ID))).click()
    # wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".k-listview-content")))
    # wait.until(EC.element_to_be_clickable((By.ID, ADD_BUTTON_BAR_OF_IMAGES_ID))).click()
    # time.sleep(PAUSE_BETWEEN_ACTIONS_SECONDS)
    # driver.execute_script("""
    #         var el = document.querySelector('[data-id="newImage"]');
    #         el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
    #     """)
    # time.sleep(PAUSE_BETWEEN_ACTIONS_SECONDS)

    wait.until(EC.element_to_be_clickable((By.ID, ADD_BUTTON_BAR_OF_IMAGES_ID))).click()
    add_image_dropdown_button = driver.find_element(By.CSS_SELECTOR, ADD_IMAGE_DROPDOWN_MENU_CSS_SELECTOR)
    driver.execute_script("arguments[0].click();", add_image_dropdown_button)

    # Finding the Correct Type and Subtype
    wait.until(EC.element_to_be_clickable((By.ID, IMAGE_SUB_TYPE_FIND_BUTTON_ID))).click()
    wait.until(EC.element_to_be_clickable((By.ID, IMAGE_SUB_TYPE_FIND_BUTTON_ID))).click()
    wait.until(EC.element_to_be_clickable((By.XPATH, IMAGE_SUB_TYPE_ROW_XPATH))).click()
    wait.until(EC.element_to_be_clickable((By.XPATH, SELECT_BUTTON_XPATH))).click()

    # Send file path directly to hidden input — bypasses OS file dialog entirely
    file_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ADD_IMAGE_UPLOAD_DROPBOX_CSS_SELECTOR)))
    driver.execute_script("arguments[0].removeAttribute('class')", file_input)  # unhide the input

    # Uploading Files to the DropBox
    file_input.send_keys("\n".join(file_list))
    time.sleep(PAUSE_BETWEEN_ACTIONS_SECONDS)

    wait.until(EC.element_to_be_clickable((By.ID, "SaveImage"))).click()

    return (driver, wait)

# MAIN LOOP FUNCTIONS
def run_stac_script(universal_case_number, file_list_from_dict, child_dir_name):
    """
    Main orchestrator: setup, navigate, search, and add files.
    Args:
         universal_case_number (str): Universal Case Number.
         file_list_from_dict (dict): Dictionary of files to add.
    """
    driver, wait = setup_browser()
    driver, wait = navigate_to_search(driver, wait)
    (driver, wait), is_match = search_by_ucn(driver, wait, universal_case_number, child_dir_name)
    if is_match:
        driver, wait = add_image(driver, wait, file_list_from_dict)
    time.sleep(WEBDRIVER_WAIT_TIMEOUT_SECONDS)
    driver.quit()

    return is_match

# LOOP TESTING
# run_stac_script(test_case)
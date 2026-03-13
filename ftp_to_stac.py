"""
STAC Web Scraper Module

Handles login, navigation, searching, and adding images to cases
via the STAC web interface using Selenium WebDriver automation.
"""

# Standard Library Imports
import time

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
WEBDRIVER_WAIT_TIMEOUT_SECONDS = 20

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
RESET_CSS_SELECTOR = "[data-menuid='mystac']"  # UNNEEDED RIGHT NOW.

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
    wait.until(EC.element_to_be_clickable((By.XPATH, UCN_SEARCH_BAR_DROPDOWN_OPTION_XPATH))) # this only waits to see if any one of the options is clickable

    return (driver, wait)

def search_by_ucn(driver, wait, ucn_value):
    """Search for a case by Universal Case Number (UCN).

    Args:
        driver (WebDriver): Selenium Chrome driver.
        wait (WebDriverWait): WebDriverWait object for explicit waits.
        ucn_value (str): Universal Case Number to search for.

    Returns:
        tuple (WebDriver, WebDriverWait): Unchanged driver and wait for chaining.

    Raises:
        TimeoutException: If the UCN dropdown option fails to become clickable.
        NoSuchElementException: If the search field or button cannot be found.
    """
    wait.until(EC.element_to_be_clickable((By.XPATH, UCN_SEARCH_BAR_DROPDOWN_OPTION_XPATH))).click()
    driver.find_element(By.ID, SEARCH_BAR_FIELD_ID).send_keys(ucn_value)
    driver.find_element(By.ID, SEARCH_BAR_BUTTON_ID).click()
    time.sleep(PAUSE_BETWEEN_ACTIONS_SECONDS)

    return (driver, wait)

def add_image(driver, wait):
    """Navigate to the Images tab and trigger the file upload dialog.

    Args:
        driver (WebDriver): Selenium Chrome driver.
        wait (WebDriverWait): WebDriverWait object for explicit waits.

    Returns:
        tuple (WebDriver, WebDriverWait): Unchanged driver and wait for chaining.

    Raises:
        TimeoutException: If the Images tab or Add button fails to become clickable.
        NoSuchElementException: If the dropdown menu or file upload button cannot be found.
    """
    wait.until(EC.element_to_be_clickable((By.ID, IMAGES_TAB_OF_CASE_ID))).click()
    wait.until(EC.element_to_be_clickable((By.ID, ADD_BUTTON_BAR_OF_IMAGES_ID))).click()
    add_image_dropdown_button = driver.find_element(By.CSS_SELECTOR, ADD_IMAGE_DROPDOWN_MENU_CSS_SELECTOR)
    driver.execute_script("arguments[0].click();", add_image_dropdown_button)
    select_files_button = driver.find_element(By.CSS_SELECTOR, SELECT_FILES_BUTTON_CSS_SELECTOR)
    driver.execute_script("arguments[0].click();", select_files_button)

    time.sleep(PAUSE_BETWEEN_ACTIONS_SECONDS)


    return (driver, wait)

# def run_stac_script(identifiers, url):
#     """
#     Main orchestrator: setup, navigate, search, and add hyperlink.
#
#     Args:
#         identifiers (dict): Dictionary with 'UCN', 'CN', 'ARN' values
#         url (str): URL to add to the case
#     """
#     driver, wait = setup_browser()
#     driver, wait = navigate_to_search(driver, wait)
#     driver, wait, rows = search_by_priority(driver, wait, identifiers)
#     if len(rows) == 1:
#         add_hyperlink(driver, wait, url)
#         print("Hyperlink added successfully")
#         is_row_length_one = True
#     elif len(rows) > 1:
#         print("Multiple Cases Found")
#         is_row_length_one = False
#     else:
#         print("No cases found with given identifiers")
#         is_row_length_one = False
#
#     time.sleep(WEBDRIVER_WAIT_TIMEOUT_SECONDS)
#     driver.quit()
#     return is_row_length_one


# if __name__ == "__main__":
#     run_stac_script(IDENTIFIERS_ALL, stac_website)

# LOOP TESTING
driver, wait = setup_browser()
driver, wait = navigate_to_search(driver, wait)
driver, wait = search_by_ucn(driver, wait, test_case)
driver, wait = add_image(driver, wait)
time.sleep(WEBDRIVER_WAIT_TIMEOUT_SECONDS)
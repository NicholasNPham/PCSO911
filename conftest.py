"""
Shared pytest setup.

Puts a stand-in `key` module in place before any test imports PCSO911 code,
so tests never read the real key.py, which holds this machine's paths, FTP
host and STAC url. Living at the repository root also puts the root on
sys.path, so tests import modules flat the way main.py does.
"""

# Standard Library Imports
import sys
import types

fake_key = types.ModuleType("key")
fake_key.FTP_LINK = "ftp.example.invalid"
fake_key.ABSOLUTE_PATH = "/example"
fake_key.WEBSITE = "https://stac.example.invalid"
fake_key.EMAIL_TO = "nobody@example.invalid"
fake_key.EMAIL_CC = "nobody@example.invalid"
fake_key.UNC_PATH_TO_H_DRIVE = r"C:\example\logs"
fake_key.CHROME_PATH = None
fake_key.UNIVERSAL_CASE_NUMBER_PATTERN = r"\d{2}-\d{4}-[A-Z]{2}-\d{6}-[A-Z0-9]{4}-[A-Z]{2}"
sys.modules["key"] = fake_key

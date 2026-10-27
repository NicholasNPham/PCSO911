"""
Reads PCSO911's secrets from Windows Credential Manager. The only file that does.

key.py holds settings that are not secret (paths, FTP host, STAC url, email
recipients). The values that grant access live in Credential Manager instead,
written there once per machine by set_credentials.py:

    PCSO911 / ftp_username     the FTP account
    PCSO911 / ftp_password     its password
    PCSO911 / stac_username    the STAC service account
    PCSO911 / stac_password    its password

Credential Manager encrypts per Windows user. Entries stored while signed in as
one account cannot be read by another, so a scheduled task running as a
different user sees none of them. The error raised here names the account that
looked, so that failure reads as what it is rather than as a wrong password.

This is storage, not an access boundary. Anything running as the same Windows
user, including a shell, can read these back exactly as PCSO911 does.
"""

# Standard Library Imports
import getpass

# Third-party Imports
import keyring
from keyring.errors import KeyringError

# Local Imports
from exceptions import SystemProblem

# CONSTANTS
SERVICE = "PCSO911"

# Key in Credential Manager -> what it is, for prompts and error messages.
# set_credentials.py walks this, so adding a secret here is the whole change.
CREDENTIALS = {
    "ftp_username": "FTP username",
    "ftp_password": "FTP password",
    "stac_username": "STAC username",
    "stac_password": "STAC password",
}

# Backends that would quietly undo the point of moving secrets out of key.py:
# one writes them to a plaintext file, the others store nothing.
REFUSED_BACKENDS = ("PlaintextKeyring", "fail.Keyring", "null.Keyring")

# FUNCTIONS
def load_credentials() -> dict[str, str]:
    """
    Returns every PCSO911 secret, keyed as in CREDENTIALS.

    All keys are checked before raising, so a machine missing two secrets is
    told about both at once rather than one run at a time.

    Returns:
        dict[str, str]: {key: value} for every key in CREDENTIALS. Values are
                        returned exactly as stored: a password with a leading
                        space keeps it.

    Raises:
        SystemProblem: If the keyring backend is unusable or unsafe, or if any
                       secret is missing or blank.
    """
    check_backend()

    found: dict[str, str] = {}
    missing: list[str] = []

    for key in CREDENTIALS:
        try:
            value = keyring.get_password(SERVICE, key)
        except KeyringError as error:
            raise SystemProblem(f"Could not read {SERVICE}/{key} from Credential Manager: {error}") from error

        if value is None or not value.strip():
            missing.append(key)
        else:
            found[key] = value

    if missing:
        user = getpass.getuser()
        raise SystemProblem(
            f"Credential Manager has no {', '.join(f'{SERVICE}/{k}' for k in missing)} "
            f"for Windows user '{user}'. Run set_credentials.py while signed in as "
            f"'{user}'. If these were stored under a different account, such as "
            "when PCSO911 runs from Task Scheduler as another user, they exist but "
            "are invisible to this one: Credential Manager is per user."
        )

    # Never the values. Only that they were found.
    print(f"Loaded {len(found)} credentials from {backend_name()}")
    return found

def check_backend() -> None:
    """
    Refuses a keyring backend that stores nothing or stores in plaintext.

    On Windows the default is the Credential Manager backend. A plaintext one
    only appears if keyrings.alt is installed and configured, and if it ever
    were, the secrets would be back in a file on disk.

    Returns:
        None

    Raises:
        SystemProblem: If the active backend is one of REFUSED_BACKENDS.
    """
    name = backend_name()
    if any(refused in name for refused in REFUSED_BACKENDS):
        raise SystemProblem(
            f"keyring is using {name}, which either stores nothing or stores "
            "secrets in a plaintext file. PCSO911 expects Windows Credential "
            "Manager (WinVaultKeyring). Check for keyrings.alt or a "
            "keyringrc.cfg overriding the default."
        )

def backend_name() -> str:
    """
    Names the active keyring backend, for checks and messages.

    Returns:
        str: The backend's module and class name, e.g. keyring.backends.Windows.WinVaultKeyring.
    """
    backend = keyring.get_keyring()
    return f"{type(backend).__module__}.{type(backend).__qualname__}"

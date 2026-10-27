"""
Stores PCSO911's secrets in Windows Credential Manager. Run once per machine.

    python set_credentials.py            set or replace each secret
    python set_credentials.py --status   show which are set, never the values
    python set_credentials.py --clear    delete all of them

Run it signed in as the Windows account PCSO911 will run as. Credential Manager
is per user: secrets stored here as one account are invisible to another,
including to a scheduled task running as a different user.

Nothing typed here is echoed, logged, or written anywhere but Credential
Manager. Passwords are typed twice, because a hidden prompt hides typos too.
"""

# Standard Library Imports
import argparse
import getpass
import sys

# Third-party Imports
import keyring
from keyring.errors import KeyringError, PasswordDeleteError

# Local Imports
import credential
from exceptions import SystemProblem

# CONSTANTS
# Keys whose value is shown while typing. Everything else is a secret.
VISIBLE_KEYS = frozenset({"ftp_username", "stac_username"})
CLEAR_CONFIRMATION_WORD = "DELETE"

# FUNCTIONS
def main() -> int:
    """
    Parses the mode and sets, shows, or clears every PCSO911 secret.

    Returns:
        int: 0 when every secret is set (or --status / --clear finished),
             1 when anything is still missing or a write failed.
    """
    parser = argparse.ArgumentParser(description="Store PCSO911 secrets in Credential Manager.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true", help="Show which secrets are set.")
    mode.add_argument("--clear", action="store_true", help="Delete every PCSO911 secret.")
    args = parser.parse_args()

    try:
        # Refusing a plaintext backend matters as much when writing as when reading.
        credential.check_backend()
    except SystemProblem as error:
        print(error, file=sys.stderr)
        return 1

    print(f"Windows user: {getpass.getuser()}")
    print(f"Backend:      {credential.backend_name()}\n")

    if args.clear:
        return clear_all()

    print_status()
    if args.status:
        return 0

    print("\nEnter leaves a secret that is already set unchanged.\n")
    for key, label in credential.CREDENTIALS.items():
        try:
            set_one(key, label)
        except KeyboardInterrupt:
            print("\nStopped. Secrets entered before this point were saved.")
            return 1
        except KeyringError as error:
            print(f"Could not write {credential.SERVICE}/{key}: {error}", file=sys.stderr)
            return 1

    print()
    print_status()
    # Non-zero while anything is still missing, so a half-done run cannot be
    # mistaken for a finished one.
    return 0 if all(is_set(key) for key in credential.CREDENTIALS) else 1

def is_set(key: str) -> bool:
    """
    Checks whether a secret is stored and not blank.

    Args:
        key (str): Key from credential.CREDENTIALS.

    Returns:
        bool: True if a non-blank value is stored, False otherwise.
    """
    value = keyring.get_password(credential.SERVICE, key)
    return bool(value and value.strip())

def print_status() -> None:
    """
    Prints set or NOT SET for every secret, never the values.

    Returns:
        None
    """
    for key in credential.CREDENTIALS:
        state = "set" if is_set(key) else "NOT SET"
        print(f"  {credential.SERVICE}/{key:<16} {state}")

def set_one(key: str, label: str) -> None:
    """
    Prompts for one value, stores it, and reads it back to confirm.

    Args:
        key (str): Key from credential.CREDENTIALS.
        label (str): What the value is, shown in the prompt.

    Returns:
        None

    Raises:
        KeyringError: If the write fails or the read-back does not match.
    """
    already = is_set(key)
    suffix = " [Enter to keep]" if already else ""

    if key in VISIBLE_KEYS:
        value = input(f"{label}{suffix}: ").strip()
    else:
        value = getpass.getpass(f"{label}{suffix}: ")
        if value and getpass.getpass("  again to confirm: ") != value:
            print("  Did not match. Not saved; run again for this one.")
            return

    if not value:
        print("  Kept." if already else "  Skipped. Still NOT SET.")
        return

    # Passwords are never stripped, since a real one can contain spaces. A
    # paste that dragged in whitespace is the likelier explanation, so ask.
    if value != value.strip():
        answer = input("  Starts or ends with whitespace. Save exactly as typed? [y/N]: ")
        if answer.strip().lower() != "y":
            print("  Not saved.")
            return

    keyring.set_password(credential.SERVICE, key, value)

    if keyring.get_password(credential.SERVICE, key) != value:
        raise KeyringError(f"read-back of {credential.SERVICE}/{key} did not match what was written")
    print("  Saved.")

def clear_all() -> int:
    """
    Deletes every PCSO911 secret after the user types the confirmation word.

    Returns:
        int: 0 if the deletes ran, 1 if the user did not confirm.
    """
    answer = input(f"Delete every {credential.SERVICE} secret for this user? Type {CLEAR_CONFIRMATION_WORD}: ")
    if answer != CLEAR_CONFIRMATION_WORD:
        print("Nothing deleted.")
        return 1

    for key in credential.CREDENTIALS:
        try:
            keyring.delete_password(credential.SERVICE, key)
            print(f"  {credential.SERVICE}/{key:<16} deleted")
        except PasswordDeleteError:
            print(f"  {credential.SERVICE}/{key:<16} was not set")
    return 0

if __name__ == "__main__":
    sys.exit(main())

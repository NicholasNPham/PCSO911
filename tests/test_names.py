"""Defendant name matching between STAC and the FTP directory name, including the one-letter typo rule."""

# Third-party Imports
import pytest

# Local Imports
from ftp_to_stac import NAME_MATCH_EXACT, NAME_MATCH_FUZZY, name_match_kind, one_edit_apart

DIR_PREFIX = "53-2026-CF-000000-A000-XX "


@pytest.mark.parametrize("stac_name, dir_name, expected", [
    # Exact, as PCSO911 has always matched.
    ("SMITH, JOHN", DIR_PREFIX + "SMITH JOHN", NAME_MATCH_EXACT),
    ("SMITH, JOHN (ALERT)", DIR_PREFIX + "JOHN SMITH", NAME_MATCH_EXACT),
    ("SMITH, JOHN MICHAEL", "SMITH JOHN", NAME_MATCH_EXACT),
    # One letter changed, added, or missing in a word of four or more letters.
    ("SMITH, JOHN", DIR_PREFIX + "SMYTH JOHN", NAME_MATCH_FUZZY),
    ("SMITH, JOHN", "SMITH JOHNN", NAME_MATCH_FUZZY),
    ("GARCIA, MARIA", "GARCIA MARA", NAME_MATCH_FUZZY),
    ("JONES, MARY", "JONAS MARY", NAME_MATCH_FUZZY),
    # Different names.
    ("SMITH, JOHN", "JONES JOHN", None),
    # No word exact, so two typos cannot make a different person match.
    ("SMITH, JOHN", "SMYTH JAHN", None),
    # Short words must be exact.
    ("LI, AMY", "LU AMY", None),
    # Two letters swapped is two edits.
    ("GARCIA, MARIA", "GRACIA MARIA", None),
    # A STAC name made only of excluded tokens used to match anything.
    ("ALERT SO", "ANYONE AT ALL", None),
    ("", "SMITH JOHN", None),
])
def test_name_match_kind(stac_name: str, dir_name: str, expected: str | None) -> None:
    """Each pair matches exactly, fuzzily, or not at all, as listed."""
    assert name_match_kind(stac_name, dir_name) == expected


def test_each_partner_word_is_used_once() -> None:
    """Two typo'd words cannot both lean on the same word on the other side.

    MARIA and MARIO are each one letter off MARIE. Letting both use it would
    match; with each partner used once, MARIO has nothing left and ROBERT
    never matched, so neither direction passes.
    """
    assert name_match_kind("SMITH, MARIA MARIO", "SMITH MARIE ROBERT") is None


@pytest.mark.parametrize("first, second, expected", [
    ("SMITH", "SMYTH", True),
    ("SMITH", "SMITHE", True),
    ("SMITH", "SMIT", True),
    ("SMITH", "SMITH", False),
    ("SMITH", "SMYTHE", False),
    ("GARCIA", "GRACIA", False),
])
def test_one_edit_apart(first: str, second: str, expected: bool) -> None:
    """Exactly one change, insertion, or deletion counts; zero or two do not."""
    assert one_edit_apart(first, second) is expected
    assert one_edit_apart(second, first) is expected

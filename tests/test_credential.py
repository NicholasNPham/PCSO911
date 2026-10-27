"""load_credentials, with Credential Manager replaced by a dict so no real secret is read."""

# Third-party Imports
import pytest

pytest.importorskip("keyring")

# Local Imports
import credential
from exceptions import SystemProblem


class FakeBackend:
    """Stands in for the keyring backend, so its class name can be checked."""


class PlaintextKeyring:
    """Named like the backend credential.py must refuse."""


def use_store(monkeypatch: pytest.MonkeyPatch, store: dict, backend: object = None) -> None:
    """
    Points credential's keyring calls at a dict instead of Credential Manager.

    Args:
        monkeypatch (MonkeyPatch): pytest's monkeypatch fixture.
        store (dict): {key: value} to serve.
        backend (object): Backend instance to report; FakeBackend by default.

    Returns:
        None
    """
    monkeypatch.setattr(credential.keyring, "get_password", lambda service, key: store.get(key))
    monkeypatch.setattr(credential.keyring, "get_keyring", lambda: backend or FakeBackend())


def test_all_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every key comes back exactly as stored, leading space included."""
    store = {key: f" value-{key}" for key in credential.CREDENTIALS}
    use_store(monkeypatch, store)
    assert credential.load_credentials() == store


def test_missing_and_blank_reported_together(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing secret and a blank one are both named in one error."""
    store = {key: "value" for key in credential.CREDENTIALS}
    del store["ftp_password"]
    store["stac_password"] = "   "
    use_store(monkeypatch, store)
    with pytest.raises(SystemProblem) as raised:
        credential.load_credentials()
    assert "PCSO911/ftp_password" in str(raised.value)
    assert "PCSO911/stac_password" in str(raised.value)


def test_plaintext_backend_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """A backend that would put secrets back in a file is refused before any read."""
    use_store(monkeypatch, {key: "value" for key in credential.CREDENTIALS}, PlaintextKeyring())
    with pytest.raises(SystemProblem, match="plaintext"):
        credential.load_credentials()

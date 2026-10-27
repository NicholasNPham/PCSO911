"""
Named error types for PCSO911.

Every PCSO911 error is either a CaseProblem (this case needs a person, the run
carries on) or a SystemProblem (PCSO911 or a service it needs is broken, the
run stops). main.py routes on which family an error belongs to, not on the
individual type, so it sends one email per failure instead of each except
block sending its own.
"""


class Pcso911Error(Exception):
    """Base class for every PCSO911-specific error."""


class CaseProblem(Pcso911Error):
    """Something is wrong with one case. Email it, leave it on FTP, keep going."""


class SystemProblem(Pcso911Error):
    """PCSO911 or a service it depends on is broken. Email it and stop the run."""


class ServiceUnreachable(SystemProblem):
    """STAC or the FTP server did not answer in time.

    Kept apart from other SystemProblems because nothing is wrong with
    PCSO911 itself, so the email can say to wait and run again rather than
    to go looking for a bug.
    """

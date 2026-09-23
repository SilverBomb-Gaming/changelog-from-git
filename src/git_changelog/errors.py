"""Expected failures. The CLI prints these without a traceback."""


class ChangelogError(Exception):
    """Base class for errors the user can act on."""


class UsageError(ChangelogError):
    """The command line or the requested range is not usable."""


class GitMissingError(ChangelogError):
    """The git executable is not installed or not on PATH."""


class NotAGitRepoError(ChangelogError):
    """The path is not a git repository."""


class GitError(ChangelogError):
    """git ran and failed."""


class LLMError(ChangelogError):
    """The model provider could not complete a request."""

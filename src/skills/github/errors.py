"""Custom errors for the GitHub integration module."""


class GitIntegrationError(RuntimeError):
    """Base error for integration failures."""


class GitCommandError(GitIntegrationError):
    """Raised when a git command fails."""


class GitHubApiError(GitIntegrationError):
    """Raised when a GitHub API request fails."""


class VersionError(GitIntegrationError):
    """Raised when version parsing or updates fail."""


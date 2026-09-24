"""Typed user-facing errors and process exit codes."""

from __future__ import annotations


__all__ = ["CartographerError", "InputError", "OutputError", "UsageError"]


class CartographerError(Exception):
    """An expected failure with a process exit code."""

    def __init__(self, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class UsageError(CartographerError):
    """An invalid command-line argument."""

    def __init__(self, message: str) -> None:
        super().__init__(message, 1)


class InputError(CartographerError):
    """An invalid scan target."""

    def __init__(self, message: str) -> None:
        super().__init__(message, 1)


class OutputError(CartographerError):
    """A failure while writing the requested report."""

    def __init__(self, message: str) -> None:
        super().__init__(message, 2)

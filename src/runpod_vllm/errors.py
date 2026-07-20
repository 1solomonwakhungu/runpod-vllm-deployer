"""Domain errors and stable process exit codes."""

from enum import IntEnum


class ExitCode(IntEnum):
    OK = 0
    USAGE = 2
    CONFIG = 3
    AUTH = 4
    NETWORK = 5
    API = 6
    TIMEOUT = 7
    STATE = 8


class RunpodVllmError(Exception):
    exit_code = ExitCode.API


class ConfigurationError(RunpodVllmError):
    exit_code = ExitCode.CONFIG


class AuthenticationError(RunpodVllmError):
    exit_code = ExitCode.AUTH


class NetworkError(RunpodVllmError):
    exit_code = ExitCode.NETWORK


class ApiError(RunpodVllmError):
    exit_code = ExitCode.API

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ReadinessTimeout(RunpodVllmError):
    exit_code = ExitCode.TIMEOUT


class StateError(RunpodVllmError):
    exit_code = ExitCode.STATE

"""Phase 5 retry, timeout, heartbeat, and error policies for Temporal workflows and activities."""

from datetime import timedelta

from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError


class NonRetryableError(ApplicationError):
    def __init__(self, message: str, error_code: str = "NON_RETRYABLE_ERROR"):
        super().__init__(message, type=error_code, non_retryable=True)
        self.error_code = error_code


class DataCorruptionError(NonRetryableError):
    def __init__(self, message: str):
        super().__init__(message, error_code="DATA_CORRUPTION")


class MaliciousFileError(NonRetryableError):
    def __init__(self, message: str):
        super().__init__(message, error_code="MALICIOUS_FILE")


class SecurityViolationError(NonRetryableError):
    def __init__(self, message: str):
        super().__init__(message, error_code="SECURITY_VIOLATION")


class OperationCancelledError(NonRetryableError):
    def __init__(self, message: str = "Operation was cancelled"):
        super().__init__(message, error_code="OPERATION_CANCELLED")


class InvalidReferenceError(NonRetryableError):
    def __init__(self, message: str):
        super().__init__(message, error_code="INVALID_REFERENCE")


class RetryableError(ApplicationError):
    def __init__(self, message: str, error_code: str = "RETRYABLE_ERROR"):
        super().__init__(message, type=error_code, non_retryable=False)
        self.error_code = error_code


class TransientServiceError(RetryableError):
    def __init__(self, message: str):
        super().__init__(message, error_code="SERVICE_UNAVAILABLE")


class ProviderTimeoutError(RetryableError):
    def __init__(self, message: str):
        super().__init__(message, error_code="PROVIDER_TIMEOUT")


class StorageUnavailableError(RetryableError):
    def __init__(self, message: str):
        super().__init__(message, error_code="STORAGE_UNAVAILABLE")


# Standard Retry Policies
COORDINATION_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=10),
    maximum_attempts=3,
    non_retryable_error_types=[
        "DATA_CORRUPTION",
        "MALICIOUS_FILE",
        "SECURITY_VIOLATION",
        "OPERATION_CANCELLED",
        "INVALID_REFERENCE",
    ],
)

SCAN_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=30),
    maximum_attempts=3,
    non_retryable_error_types=[
        "MALICIOUS_FILE",
        "SECURITY_VIOLATION",
        "INVALID_REFERENCE",
        "OPERATION_CANCELLED",
    ],
)

CONNECTOR_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=60),
    maximum_attempts=3,
    non_retryable_error_types=[
        "INVALID_REFERENCE",
        "SECURITY_VIOLATION",
        "OPERATION_CANCELLED",
    ],
)

DOCUMENT_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=3),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=30),
    maximum_attempts=3,
    non_retryable_error_types=[
        "DATA_CORRUPTION",
        "INVALID_REFERENCE",
        "OPERATION_CANCELLED",
    ],
)

EVALUATION_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=10),
    maximum_attempts=3,
    non_retryable_error_types=[
        "DATA_CORRUPTION",
        "INVALID_REFERENCE",
        "OPERATION_CANCELLED",
    ],
)

# Standard Timeouts
TIMEOUT_COORDINATION = timedelta(seconds=60)
TIMEOUT_SCAN = timedelta(seconds=180)
TIMEOUT_SCAN_HEARTBEAT = timedelta(seconds=30)
TIMEOUT_DOCUMENT = timedelta(seconds=300)
TIMEOUT_DOCUMENT_HEARTBEAT = timedelta(seconds=45)
TIMEOUT_CONNECTOR = timedelta(seconds=120)
TIMEOUT_CONNECTOR_HEARTBEAT = timedelta(seconds=30)
TIMEOUT_EVALUATION = timedelta(seconds=60)
TIMEOUT_REPORT = timedelta(seconds=120)
TIMEOUT_MEDIA = timedelta(seconds=300)
TIMEOUT_MEDIA_HEARTBEAT = timedelta(seconds=45)

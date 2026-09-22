"""Bounded retry and circuit breaker helpers for future source integrations."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar


T = TypeVar("T")


def retry(
    operation: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay_seconds: float = 0.05,
    retryable: tuple[type[Exception], ...] = (TimeoutError, ConnectionError),
) -> T:
    if attempts < 1:
        raise ValueError("attempts must be at least one")
    for attempt in range(attempts):
        try:
            return operation()
        except retryable:
            if attempt == attempts - 1:
                raise
            time.sleep(base_delay_seconds * (2**attempt))
    raise RuntimeError("unreachable")


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    failures: int = 0
    open: bool = False

    def call(self, operation: Callable[[], T]) -> T:
        if self.open:
            raise RuntimeError("circuit breaker is open")
        try:
            result = operation()
        except Exception:
            self.failures += 1
            if self.failures >= self.failure_threshold:
                self.open = True
            raise
        self.failures = 0
        return result

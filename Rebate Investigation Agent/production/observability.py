"""Local metrics primitives with no sensitive business payloads."""

from collections import Counter
from dataclasses import dataclass, field
from time import perf_counter


@dataclass
class Metrics:
    counters: Counter = field(default_factory=Counter)
    durations: dict[str, list[float]] = field(default_factory=dict)

    def increment(self, name: str, value: int = 1) -> None:
        self.counters[name] += value

    def observe(self, name: str, seconds: float) -> None:
        self.durations.setdefault(name, []).append(seconds)


class Timer:
    def __init__(self, metrics: Metrics, name: str) -> None:
        self.metrics = metrics
        self.name = name

    def __enter__(self) -> "Timer":
        self.started = perf_counter()
        return self

    def __exit__(self, *_: object) -> None:
        self.metrics.observe(self.name, perf_counter() - self.started)

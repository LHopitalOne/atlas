import statistics
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field


@dataclass
class Sample:
    name: str
    value: float
    timestamp: float
    tags: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"value": self.value, "ts": self.timestamp, "tags": self.tags}


@dataclass
class Annotation:
    text: str
    timestamp: float
    author: str | None = None


class MetricStore:
    def __init__(self, retention: int = 1000) -> None:
        self._retention = retention
        self._series: dict[str, deque[Sample]] = defaultdict(lambda: deque(maxlen=self._retention))
        self._counters: dict[str, float] = defaultdict(float)
        self.annotations: list[Annotation] = []

    def add(self, sample: Sample) -> None:
        self._series[sample.name].append(sample)

    def incr(self, name: str, amount: float = 1.0) -> None:
        self._counters[name] += amount
        self.add(Sample(name, self._counters[name], time.time()))

    def names(self) -> list[str]:
        return sorted(self._series)

    def series(self, name: str, limit: int = 100) -> list[Sample] | None:
        if name not in self._series:
            return None
        return list(self._series[name])[-limit:]

    def summary(self, name: str) -> dict | None:
        points = self.series(name, limit=self._retention)
        if not points:
            return None
        values = [p.value for p in points]
        return {
            "name": name,
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "mean": statistics.fmean(values),
            "last": values[-1],
        }

    def annotate(self, text: str, timestamp: float | None = None, author: str | None = None) -> Annotation:
        note = Annotation(text=text, timestamp=timestamp or time.time(), author=author)
        self.annotations.append(note)
        return note

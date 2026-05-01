from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlmodel import select

from backend.app.db import session_scope
from backend.app.config import get_settings
from backend.app.models.service import Service
from backend.app.core.runner import get_service_container_by_slug


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _calculate_cpu_percent(stats: dict[str, Any]) -> float:
    cpu_stats = stats.get("cpu_stats", {})
    precpu_stats = stats.get("precpu_stats", {})
    cpu_delta = cpu_stats.get("cpu_usage", {}).get("total_usage", 0) - precpu_stats.get("cpu_usage", {}).get(
        "total_usage", 0
    )
    system_delta = cpu_stats.get("system_cpu_usage", 0) - precpu_stats.get("system_cpu_usage", 0)
    cpu_count = cpu_stats.get("online_cpus") or len(cpu_stats.get("cpu_usage", {}).get("percpu_usage", []) or [1])
    if cpu_delta <= 0 or system_delta <= 0 or cpu_count <= 0:
        return 0.0
    return round((cpu_delta / system_delta) * cpu_count * 100, 2)


def _calculate_memory_percent(usage: int, limit: int) -> float:
    if limit <= 0:
        return 0.0
    return round((usage / limit) * 100, 2)


def _calculate_network_io(stats: dict[str, Any]) -> tuple[int, int]:
    networks = stats.get("networks", {}) or {}
    rx = sum(int(values.get("rx_bytes", 0)) for values in networks.values())
    tx = sum(int(values.get("tx_bytes", 0)) for values in networks.values())
    return rx, tx


def _calculate_block_io(stats: dict[str, Any]) -> tuple[int, int]:
    blkio_stats = stats.get("blkio_stats", {}) or {}
    entries = blkio_stats.get("io_service_bytes_recursive", []) or []
    read_bytes = 0
    write_bytes = 0
    for entry in entries:
        operation = str(entry.get("op", "")).lower()
        value = int(entry.get("value", 0))
        if operation == "read":
            read_bytes += value
        elif operation == "write":
            write_bytes += value
    return read_bytes, write_bytes


def parse_container_stats(stats: dict[str, Any]) -> dict[str, Any]:
    memory_stats = stats.get("memory_stats", {}) or {}
    memory_usage = int(memory_stats.get("usage", 0))
    memory_limit = int(memory_stats.get("limit", 0))
    network_rx, network_tx = _calculate_network_io(stats)
    block_read, block_write = _calculate_block_io(stats)

    return {
        "timestamp": _utcnow().isoformat(),
        "cpu_percent": _calculate_cpu_percent(stats),
        "memory_usage_bytes": memory_usage,
        "memory_limit_bytes": memory_limit,
        "memory_percent": _calculate_memory_percent(memory_usage, memory_limit),
        "network_rx_bytes": network_rx,
        "network_tx_bytes": network_tx,
        "block_read_bytes": block_read,
        "block_write_bytes": block_write,
        "pids": int((stats.get("pids_stats", {}) or {}).get("current", 0)),
    }


def parse_metrics_range(value: str) -> timedelta:
    value = value.strip().lower()
    try:
        if value.endswith("m"):
            return timedelta(minutes=max(1, int(value[:-1])))
        if value.endswith("h"):
            return timedelta(hours=max(1, int(value[:-1])))
    except ValueError as exc:
        raise ValueError("range must use the format <int>m or <int>h") from exc
    raise ValueError("range must use the format <int>m or <int>h")


class MetricsSampler:
    def __init__(self, interval_seconds: int = 5, max_samples: int = 60):
        self.interval_seconds = interval_seconds
        self.max_samples = max_samples
        self._history: dict[str, deque[dict[str, Any]]] = {}
        self._subscribers: dict[str, list[tuple[asyncio.AbstractEventLoop, asyncio.Queue[dict[str, Any]]]]] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="metrics-sampler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._thread = None

    def subscribe(
        self,
        service_id: UUID,
        loop: asyncio.AbstractEventLoop,
        queue: asyncio.Queue[dict[str, Any]],
    ) -> None:
        key = str(service_id)
        with self._lock:
            self._subscribers.setdefault(key, []).append((loop, queue))

    def unsubscribe(self, service_id: UUID, queue: asyncio.Queue[dict[str, Any]]) -> None:
        key = str(service_id)
        with self._lock:
            subscribers = self._subscribers.get(key, [])
            self._subscribers[key] = [(loop, current_queue) for loop, current_queue in subscribers if current_queue is not queue]
            if not self._subscribers[key]:
                self._subscribers.pop(key, None)

    def get_history(self, service_id: UUID, range_value: str = "5m") -> list[dict[str, Any]]:
        window = parse_metrics_range(range_value)
        cutoff = _utcnow() - window
        key = str(service_id)
        with self._lock:
            samples = list(self._history.get(key, deque()))

        return [sample for sample in samples if datetime.fromisoformat(sample["timestamp"]) >= cutoff]

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self._sample_all_services()
            self._stop_event.wait(self.interval_seconds)

    def _sample_all_services(self) -> None:
        with session_scope() as session:
            services = session.exec(select(Service)).all()

        for service in services:
            container = get_service_container_by_slug(service.slug)
            if container is None:
                continue
            try:
                sample = parse_container_stats(container.stats(stream=False))
            except Exception:
                continue
            self._record_sample(service.id, sample)

    def _record_sample(self, service_id: UUID, sample: dict[str, Any]) -> None:
        key = str(service_id)
        with self._lock:
            history = self._history.setdefault(key, deque(maxlen=self.max_samples))
            history.append(sample)
            subscribers = list(self._subscribers.get(key, []))

        for loop, queue in subscribers:
            loop.call_soon_threadsafe(queue.put_nowait, sample)


settings = get_settings()
metrics_sampler = MetricsSampler(
    interval_seconds=settings.metrics_sample_interval_seconds,
    max_samples=settings.metrics_max_samples,
)


__all__ = [
    "MetricsSampler",
    "metrics_sampler",
    "parse_container_stats",
    "parse_metrics_range",
]

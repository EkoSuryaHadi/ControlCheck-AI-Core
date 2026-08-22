"""Prometheus-compatible Metrics Exporter for ControlCheck AI."""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict
from typing import Dict, Tuple


class MetricsCollector:
    """Thread-safe lightweight in-memory Prometheus metrics collector."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._start_time = time.time()
        self._requests_total: Dict[Tuple[str, str, int], int] = defaultdict(int)
        self._request_duration_seconds_sum: Dict[Tuple[str, str], float] = defaultdict(float)
        self._request_duration_seconds_count: Dict[Tuple[str, str], int] = defaultdict(int)
        self._analysis_runs_total: Dict[str, int] = defaultdict(int)
        self._analysis_duration_seconds_sum: float = 0.0
        self._analysis_duration_seconds_count: int = 0
        self._active_requests: int = 0
        self._findings_generated_total: Dict[str, int] = defaultdict(int)

    def inc_active_requests(self) -> None:
        with self._lock:
            self._active_requests += 1

    def dec_active_requests(self) -> None:
        with self._lock:
            self._active_requests = max(0, self._active_requests - 1)

    def record_request(self, method: str, path: str, status_code: int, duration_seconds: float) -> None:
        # Normalize paths with UUIDs or numeric IDs to prevent metric cardinality explosion
        normalized_path = self._normalize_path(path)
        with self._lock:
            self._requests_total[(method, normalized_path, status_code)] += 1
            self._request_duration_seconds_sum[(method, normalized_path)] += duration_seconds
            self._request_duration_seconds_count[(method, normalized_path)] += 1

    def record_analysis_run(self, status: str, duration_seconds: float, finding_counts_by_severity: Dict[str, int] | None = None) -> None:
        with self._lock:
            self._analysis_runs_total[status] += 1
            self._analysis_duration_seconds_sum += duration_seconds
            self._analysis_duration_seconds_count += 1
            if finding_counts_by_severity:
                for severity, count in finding_counts_by_severity.items():
                    self._findings_generated_total[severity] += count

    def generate_prometheus_output(self) -> str:
        with self._lock:
            lines: list[str] = []
            
            # App Info
            lines.append("# HELP controlcheck_app_info Application metadata and version.")
            lines.append("# TYPE controlcheck_app_info gauge")
            lines.append(f'controlcheck_app_info{{version="0.2.0",env="{os.environ.get("ENV", "production")}"}} 1')

            # Uptime
            uptime = time.time() - self._start_time
            lines.append("# HELP controlcheck_process_uptime_seconds Process uptime in seconds.")
            lines.append("# TYPE controlcheck_process_uptime_seconds counter")
            lines.append(f"controlcheck_process_uptime_seconds {uptime:.2f}")

            # Active Requests
            lines.append("# HELP controlcheck_active_requests Current in-flight HTTP requests.")
            lines.append("# TYPE controlcheck_active_requests gauge")
            lines.append(f"controlcheck_active_requests {self._active_requests}")

            # HTTP Requests Total
            lines.append("# HELP controlcheck_http_requests_total Total number of HTTP requests processed.")
            lines.append("# TYPE controlcheck_http_requests_total counter")
            for (method, path, status), count in sorted(self._requests_total.items()):
                lines.append(f'controlcheck_http_requests_total{{method="{method}",path="{path}",status="{status}"}} {count}')

            # HTTP Request Duration
            lines.append("# HELP controlcheck_http_request_duration_seconds_sum Total time spent processing HTTP requests.")
            lines.append("# TYPE controlcheck_http_request_duration_seconds_sum counter")
            for (method, path), dur_sum in sorted(self._request_duration_seconds_sum.items()):
                lines.append(f'controlcheck_http_request_duration_seconds_sum{{method="{method}",path="{path}"}} {dur_sum:.4f}')

            lines.append("# HELP controlcheck_http_request_duration_seconds_count Count of HTTP requests processed for duration tracking.")
            lines.append("# TYPE controlcheck_http_request_duration_seconds_count counter")
            for (method, path), dur_count in sorted(self._request_duration_seconds_count.items()):
                lines.append(f'controlcheck_http_request_duration_seconds_count{{method="{method}",path="{path}"}} {dur_count}')

            # Analysis Runs Total
            lines.append("# HELP controlcheck_analysis_runs_total Total number of project analysis engine executions.")
            lines.append("# TYPE controlcheck_analysis_runs_total counter")
            for status, count in sorted(self._analysis_runs_total.items()):
                lines.append(f'controlcheck_analysis_runs_total{{status="{status}"}} {count}')

            # Findings Generated Total
            lines.append("# HELP controlcheck_findings_total Total findings generated categorized by severity.")
            lines.append("# TYPE controlcheck_findings_total counter")
            for severity, count in sorted(self._findings_generated_total.items()):
                lines.append(f'controlcheck_findings_total{{severity="{severity}"}} {count}')

            return "\n".join(lines) + "\n"

    @staticmethod
    def _normalize_path(path: str) -> str:
        # Group parameterized routes to maintain low Prometheus cardinality
        segments = path.strip("/").split("/")
        normalized = []
        for segment in segments:
            if len(segment) == 36 and segment.count("-") == 4:  # UUID
                normalized.append(":id")
            elif segment.isdigit():
                normalized.append(":id")
            else:
                normalized.append(segment)
        return "/" + "/".join(normalized) if normalized else "/"


metrics_collector = MetricsCollector()

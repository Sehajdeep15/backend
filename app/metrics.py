import threading
import time
from typing import Dict, List, Tuple

class Metrics:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        # Counters: (name, frozenset(labels.items())) -> value
        self.counters: Dict[Tuple[str, frozenset], float] = {}
        
        # Histograms: (name, frozenset(labels.items())) -> list of bucket counts
        # Buckets for latency in ms
        self.latency_buckets = [10, 50, 100, 200, 500, 1000, 5000]
        self.histograms: Dict[Tuple[str, frozenset], List[float]] = {}
        self.histogram_sums: Dict[Tuple[str, frozenset], float] = {}
        self.histogram_counts: Dict[Tuple[str, frozenset], int] = {}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _get_label_key(self, labels: Dict[str, str]) -> frozenset:
        return frozenset(labels.items())

    def record_http_request(self, path: str, status: int, latency_ms: float):
        labels = {"path": path, "status": str(status)}
        label_key = self._get_label_key(labels)
        
        with self._lock:
            # Increment Counter
            key = ("http_requests_total", label_key)
            self.counters[key] = self.counters.get(key, 0.0) + 1.0
            
            # Record Latency in Histogram
            hist_key = ("request_latency_ms", label_key)
            if hist_key not in self.histograms:
                self.histograms[hist_key] = [0.0] * (len(self.latency_buckets) + 1)
                self.histogram_sums[hist_key] = 0.0
                self.histogram_counts[hist_key] = 0
            
            # Update buckets (Prometheus buckets are cumulative)
            for i, le in enumerate(self.latency_buckets):
                if latency_ms <= le:
                    self.histograms[hist_key][i] += 1.0
            # +Inf bucket always increments
            self.histograms[hist_key][-1] += 1.0
            
            self.histogram_sums[hist_key] += latency_ms
            self.histogram_counts[hist_key] += 1

    def record_webhook_result(self, result: str):
        labels = {"result": result}
        label_key = self._get_label_key(labels)
        with self._lock:
            key = ("webhook_requests_total", label_key)
            self.counters[key] = self.counters.get(key, 0.0) + 1.0

    def render_metrics(self) -> str:
        lines = []
        with self._lock:
            # Render Counters
            for (name, label_key), value in self.counters.items():
                label_str = ""
                if label_key:
                    label_str = "{" + ",".join(f'{k}="{v}"' for k, v in sorted(label_key)) + "}"
                lines.append(f"{name}{label_str} {value}")

            # Render Histograms
            for (name, label_key), buckets in self.histograms.items():
                base_label_str = ",".join(f'{k}="{v}"' for k, v in sorted(label_key))
                if base_label_str:
                    base_label_str += ","
                
                for i, le in enumerate(self.latency_buckets):
                    lines.append(f'{name}_bucket{{{base_label_str}le="{le}"}} {buckets[i]}')
                
                # +Inf
                lines.append(f'{name}_bucket{{{base_label_str}le="+Inf"}} {buckets[-1]}')
                
                # Sum and Count
                suffix = base_label_str.rstrip(",")
                label_section = f"{{{suffix}}}" if suffix else ""
                lines.append(f'{name}_sum{label_section} {self.histogram_sums[(name, label_key)]}')
                lines.append(f'{name}_count{label_section} {self.histogram_counts[(name, label_key)]}')

        return "\n".join(lines) + "\n"

# For backwards compatibility or simplified access
metrics = Metrics.get_instance()

def record_http_request(path: str, status: int, latency_ms: float):
    metrics.record_http_request(path, status, latency_ms)

def record_webhook_result(result: str):
    metrics.record_webhook_result(result)

def render_metrics() -> str:
    return metrics.render_metrics()

"""
RollingZScoreDetector: rolling z-score ile gecikme/hata anomalisi tespiti - Redis'teki
"son N istek" penceresi üzerinde çalışacak şekilde, bu modül Redis'ten
bağımsız, saf istatistik mantığı içeriyor
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass
class ZScoreResult:
    z_score: float
    is_anomaly: bool
    mean: float
    std: float


class RollingZScoreDetector:
    """
    her istemci için son N gecikme değeri üzerinden ortalama/standart sapma hesaplıyor,
    varsayılan eşik 3.2 sigma
    """

    def __init__(self, window_size: int = 50, threshold: float = 3.2):
        self.window_size = window_size
        self.threshold = threshold
        self._windows: dict[str, deque[float]] = {}

    def _window_for(self, client_id: str) -> deque[float]:
        if client_id not in self._windows:
            self._windows[client_id] = deque(maxlen=self.window_size)
        return self._windows[client_id]

    def update_and_score(self, client_id: str, latency_ms: float) -> ZScoreResult:
        window = self._window_for(client_id)

        if len(window) < max(5, self.window_size // 5):
            # yeterli baseline yokken anomali işaretlemeyiz-(cold start koruması)
            window.append(latency_ms)
            return ZScoreResult(z_score=0.0, is_anomaly=False, mean=latency_ms, std=0.0)

        mean = sum(window) / len(window)
        variance = sum((x - mean) ** 2 for x in window) / len(window)
        std = variance ** 0.5

        z = 0.0 if std == 0 else (latency_ms - mean) / std
        is_anomaly = abs(z) >= self.threshold

        window.append(latency_ms)
        return ZScoreResult(z_score=round(z, 3), is_anomaly=is_anomaly, mean=round(mean, 2), std=round(std, 2))

    def set_threshold(self, threshold: float) -> None:
        self.threshold = threshold
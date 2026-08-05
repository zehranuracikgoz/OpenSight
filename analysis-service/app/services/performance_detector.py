"""
RollingZScoreDetector: rolling z-score ile gecikme/hata anomalisi tespiti - Redis'teki
"son N istek" penceresini bir Redis List'te (zscore:window:{client_id}) tutuyor,
bu modül saf istatistik mantığını içeriyor
"""
from __future__ import annotations

from dataclasses import dataclass

from redis import Redis


@dataclass
class ZScoreResult:
    z_score: float
    is_anomaly: bool
    mean: float
    std: float


class RollingZScoreDetector:
    """
    her istemci için son N gecikme değeri üzerinden ortalama/standart sapma hesaplıyor,
    varsayılan eşik 3.2 sigma - pencere verisi Redis'te client bazlı tutuluyor
    """

    def __init__(self, redis_client: Redis, window_size: int = 50, threshold: float = 3.2):
        self.redis = redis_client
        self.window_size = window_size
        self.threshold = threshold

    def _key(self, client_id: str) -> str:
        return f"zscore:window:{client_id}"

    def update_and_score(self, client_id: str, latency_ms: float) -> ZScoreResult:
        key = self._key(client_id)
        window = [float(v) for v in self.redis.lrange(key, 0, -1)]

        if len(window) < max(5, self.window_size // 5):
            # yeterli baseline yokken anomali işaretlemiyor (cold start koruması)
            self._push(key, latency_ms)
            return ZScoreResult(z_score=0.0, is_anomaly=False, mean=latency_ms, std=0.0)

        mean = sum(window) / len(window)
        variance = sum((x - mean) ** 2 for x in window) / len(window)
        std = variance ** 0.5

        z = 0.0 if std == 0 else (latency_ms - mean) / std
        is_anomaly = abs(z) >= self.threshold

        self._push(key, latency_ms)
        return ZScoreResult(z_score=round(z, 3), is_anomaly=is_anomaly, mean=round(mean, 2), std=round(std, 2))

    def _push(self, key: str, latency_ms: float) -> None:
        pipe = self.redis.pipeline()
        pipe.rpush(key, latency_ms)
        pipe.ltrim(key, -self.window_size, -1)
        pipe.execute()

    def set_threshold(self, threshold: float) -> None:
        self.threshold = threshold

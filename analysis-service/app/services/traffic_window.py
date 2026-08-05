"""
ClientTrafficWindow: her istemcinin son isteklerini (endpoint + gecikme + zaman) Redis'te
tutuyor, BehavioralAnomalyDetector'ın beklediği [istek_orani, endpoint_cesitliligi,
ortalama_gecikme] özellik vektörünü bu pencereden hesaplıyor
"""
from __future__ import annotations

import json
import time

from redis import Redis

DEFAULT_WINDOW_SECONDS = 60
DEFAULT_MAX_EVENTS = 200


class ClientTrafficWindow:
    def __init__(
        self,
        redis_client: Redis,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
        max_events: int = DEFAULT_MAX_EVENTS,
    ):
        self.redis = redis_client
        self.window_seconds = window_seconds
        self.max_events = max_events

    def _key(self, client_id: str) -> str:
        return f"behavioral:window:{client_id}"

    def record(self, client_id: str, endpoint: str, latency_ms: float, timestamp: float) -> list[float]:
        """yeni isteği pencereye ekliyor, güncel özellik vektörünü döndürüyor"""
        key = self._key(client_id)
        entry = json.dumps({"endpoint": endpoint, "latency_ms": latency_ms, "ts": timestamp})

        pipe = self.redis.pipeline()
        pipe.rpush(key, entry)
        pipe.ltrim(key, -self.max_events, -1)
        pipe.execute()

        return self.feature_vector(client_id, now=timestamp)

    def feature_vector(self, client_id: str, now: float | None = None) -> list[float]:
        """son window_seconds içindeki isteklerden [istek_orani, endpoint_cesitliligi, ortalama_gecikme] hesaplıyor"""
        now = time.time() if now is None else now
        cutoff = now - self.window_seconds
        raw = self.redis.lrange(self._key(client_id), 0, -1)
        events = [json.loads(e) for e in raw]
        recent = [e for e in events if e["ts"] >= cutoff]

        if not recent:
            return [0.0, 0.0, 0.0]

        request_rate = len(recent) / self.window_seconds
        endpoint_diversity = len({e["endpoint"] for e in recent}) / len(recent)
        avg_latency = sum(e["latency_ms"] for e in recent) / len(recent)

        return [round(request_rate, 3), round(endpoint_diversity, 3), round(avg_latency, 2)]

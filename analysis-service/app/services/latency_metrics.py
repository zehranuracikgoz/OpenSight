"""
LatencyMetrics: gecikmeleri bellekte dakikalık kovalarda topluyor (genel ve istemci bazlı, toplam + adet),
dakika dolunca tek bir özeti Redis'e yazıyor - istek başına Redis komutu yok, Upstash kotası için
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

from redis import Redis
from redis.exceptions import RedisError

logger = logging.getLogger("opensight.latency_metrics")

KEY_PREFIX = "metrics:latency:"
TTL_SECONDS = 24 * 60 * 60
ALL_KEY = "__all__"
# bellekte ve sorguda en fazla bu kadar dakika tutuluyor, Redis'ten ilk okumada da bu kadarı yükleniyor
RETENTION_MINUTES = 30


class LatencyMetrics:
    def __init__(self, redis_client: Redis, retention_minutes: int = RETENTION_MINUTES):
        self.redis = redis_client
        self.retention_minutes = retention_minutes
        self._lock = threading.Lock()
        # dakika (epoch) ->anahtar (istemci ya da __all__) -> [toplam gecikme, adet]
        self._buckets: dict[int, dict[str, list[float]]] = {}
        self._flushed: set[int] = set()
        self._loaded = False

    @staticmethod
    def _minute(timestamp: float) ->int:
        return int(timestamp // 60) * 60

    def record(self, client_id: str, latency_ms: float, timestamp: float) -> None:
        minute = self._minute(timestamp)
        with self._lock:
            bucket = self._buckets.setdefault(minute, {})
            for key in (ALL_KEY, client_id):
                entry = bucket.setdefault(key, [0.0, 0])
                entry[0] += latency_ms
                entry[1] += 1
            self._flush_completed(minute)

    def _flush_completed(self, current_minute: int) -> None:
        """şu anki dakikadan eski ve henüz yazılmamış dakikaları Redis'e yazıyor, kilit altında çağrılmalı"""
        pending = [m for m in self._buckets if m < current_minute and m not in self._flushed]
        if pending:
            try:
                # transaction=False: MULTI/EXEC eklemeden dakika başına 2 komut (HSET + EXPIRE)
                pipe = self.redis.pipeline(transaction=False)
                for minute  in pending:
                    key = f"{KEY_PREFIX}{minute}"
                    pipe.hset(key, mapping={k: f"{v[0]},{int(v[1])}" for k, v in self._buckets[minute].items()})
                    pipe.expire(key, TTL_SECONDS)
                pipe.execute()
                self._flushed.update(pending)
            except RedisError as exc:
                logger.warning("dakikalık gecikme özeti Redis'e yazılamadı (%s), bellekte kalıyor", exc)

        cutoff = current_minute - self.retention_minutes * 60
        for minute in [m for m in self._buckets if m < cutoff]:
            del self._buckets[minute]
            self._flushed.discard(minute)

    def _load_from_redis_once(self, current_minute: int) -> None:
        """servis (yeniden) başladıktan sonra ilk okumada, bellekte olmayan geçmiş dakikaları Redis'ten alıyor"""
        if self._loaded:
            return
        self._loaded = True
        minutes = [current_minute -i * 60 for i in range(1, self.retention_minutes)]
        try:
            pipe = self.redis.pipeline(transaction=False)
            for minute in minutes:
                pipe.hgetall(f"{KEY_PREFIX}{minute}")
            results = pipe.execute()
        except RedisError as exc:
            logger.warning("geçmiş gecikme özeti Redis'ten okunamadı (%s), yalnızca bellek kullanılacak", exc)
            return
        for minute, fields in zip(minutes, results):
            if not fields or minute in self._buckets:
                continue
            bucket = {}
            for key, value in fields.items():
                key = key.decode("utf-8") if isinstance(key, bytes) else key
                value = value.decode("utf-8") if isinstance(value, bytes) else value
                total, count = value.split(",")
                bucket[key]=[float(total), int(count)]
            self._buckets[minute] = bucket
            self._flushed.add(minute)

    def series(self, minutes: int = RETENTION_MINUTES, client_id: str | None = None, now: float | None = None) -> dict:
        """son N dakikanın dakikalık ortalama gecikmesi ve istek sayısı, içinde bulunulan dakika da bellekten ekleniyor"""
        minutes = max(1, min(minutes, self.retention_minutes))
        now = datetime.now(timezone.utc).timestamp() if now is None else now
        current_minute = self._minute(now)
        key = client_id or ALL_KEY

        with self._lock:
            self._load_from_redis_once(current_minute)
            self._flush_completed(current_minute)  # trafik durduysa son dakika da yazılsın
            points = []
            total_latency, total_count = 0.0, 0
            for i in range(minutes - 1, -1, -1):
                minute = current_minute - i * 60
                entry = self._buckets.get(minute, {}).get(key)
                count = int(entry[1]) if entry else 0
                average = round(entry[0] / entry[1], 2) if entry else None
                if entry:
                    total_latency += entry[0]
                    total_count += count
                points.append(
                    
                    {
                        "minute": datetime.fromtimestamp(minute, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
                        "avg_latency_ms": average,
                        "request_count": count,
                    }
                )

        return {
            "minutes": minutes,
            "client_id": client_id,
            "points": points,
            # dakikalık ortalamaların değil, tüm isteklerin ağırlıklı ortalaması
            "average_latency_ms": round(total_latency / total_count, 2) if total_count else None,
            "request_count": total_count,
            
        }
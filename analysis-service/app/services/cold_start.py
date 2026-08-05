"""
ColdStartManager: RabbitMQ'dan gelen özellik vektörlerini ilk cold_start_seconds boyunca
Redis'te (behavioral:baseline) baseline olarak biriktiriyor, süre dolunca
BehavioralAnomalyDetector.fit()'i otomatik tetikliyor ve canlı tespite geçiyor.
Simülatörün kendi cold_start_seconds'ı (varsayılan 90s, "hangi trafik profili
üretilsin" kararı) ile buradaki cold_start_seconds (varsayılan da 90s, ama "model
ne zaman eğitilsin" kararı) birbirinden bağımsız ayarlanabilir - aynı varsayılan
değer, ikisinin mantıken aynı cold start penceresine denk gelmesi için seçildi
"""
from __future__ import annotations

import logging
import time

from redis import Redis

from app.services.behavioral_detector import BehavioralAnomalyDetector

logger = logging.getLogger("opensight.cold_start")

BASELINE_KEY = "behavioral:baseline"
MIN_BASELINE_SAMPLES = 5


class ColdStartManager:
    def __init__(
        self,
        redis_client: Redis,
        behavioral_detector: BehavioralAnomalyDetector,
        cold_start_seconds: int = 90,
    ):
        self.redis = redis_client
        self.behavioral_detector = behavioral_detector
        self.cold_start_seconds = cold_start_seconds
        self.start_time = time.monotonic()
        self._completed = False

    def is_in_cold_start(self) -> bool:
        return not self._completed and (time.monotonic() - self.start_time) < self.cold_start_seconds

    def is_ready(self) -> bool:
        return self._completed

    def handle(self, feature_vector: list[float]) -> None:
        """her yeni özellik vektörü geldiğinde çağrılıyor - baseline topluyor ya da modeli eğitip canlı tespite geçiyor"""
        if self._completed:
            return

        if self.is_in_cold_start():
            self.redis.rpush(BASELINE_KEY, ",".join(str(v) for v in feature_vector))
            return

        self._finish_cold_start()

    def _finish_cold_start(self) -> None:
        raw = self.redis.lrange(BASELINE_KEY, 0, -1)
        # redis_client decode_responses=True olmadan da çağrılabilir (bytes döner), bu yüzden burada normalize ediyor
        rows = [row.decode("utf-8") if isinstance(row, bytes) else row for row in raw]
        baseline = [[float(v) for v in row.split(",")] for row in rows]

        if len(baseline) < MIN_BASELINE_SAMPLES:
            logger.warning(
                "cold start süresi doldu ama yeterli baseline verisi yok (%d örnek), süre uzatılıyor",
                len(baseline),
            )
            self.start_time = time.monotonic()
            return

        self.behavioral_detector.fit(baseline)
        self._completed = True
        logger.info("cold start tamamlandı, model %d örnekle eğitildi, canlı tespite geçiliyor", len(baseline))

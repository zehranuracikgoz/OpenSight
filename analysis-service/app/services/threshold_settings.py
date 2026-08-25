"""
ThresholdSettingsService: Z-Score eşiğini ve Isolation Forest contamination oranını
Redis'te kalıcı tutuyor, servis yeniden başlasa da korunuyor. Son 24 saatte üretilen
alarm sayısını (tip bazında, Redis Sorted Set ile zaman penceresi olarak) ve modelin
son eğitim zamanını (BehavioralAnomalyDetector'dan) buradan okunuyor.
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass

from redis import Redis
from redis.exceptions import RedisError

from app.services.behavioral_detector import BehavioralAnomalyDetector
from app.services.performance_detector import RollingZScoreDetector

logger = logging.getLogger("opensight.threshold_settings")

Z_SCORE_KEY = "settings:z_score_threshold"
CONTAMINATION_KEY = "settings:contamination"
ALERT_COUNT_KEY_PREFIX = "settings:alert_count:"
ALERT_COUNT_WINDOW_SECONDS = 24 * 60 * 60
ALERT_TYPES = ("Performans", "Davranışsal")


@dataclass
class ThresholdSettings:
    z_score_threshold: float
    contamination: float
    last_trained_at: str | None
    alert_counts_last_24h: dict[str, int]


class ThresholdSettingsService:
    def __init__(
        self,
        redis_client: Redis,
        performance_detector: RollingZScoreDetector,
        behavioral_detector: BehavioralAnomalyDetector,
    ):
        self.redis = redis_client
        self.performance_detector = performance_detector
        self.behavioral_detector = behavioral_detector
        self._apply_persisted_values()

    def _apply_persisted_values(self) -> None:
        """servis (yeniden) başlarken Redis'te kayıtlı eşik varsa detector'lara uyguluyor -
        Redis'e o an ulaşılamazsa servis çökmesin diye varsayılanlarla devam ediyor"""
        try:
            stored_threshold = self.redis.get(Z_SCORE_KEY)
            if stored_threshold is not None:
                self.performance_detector.set_threshold(float(stored_threshold))

            stored_contamination = self.redis.get(CONTAMINATION_KEY)
            if stored_contamination is not None:
                self.behavioral_detector.set_contamination(float(stored_contamination))
        except RedisError as exc:
            logger.warning("kayıtlı eşik değerleri okunamadı (%s), varsayılanlarla devam ediliyor", exc)

    def get_settings(self) -> ThresholdSettings:
        return ThresholdSettings(
            z_score_threshold=self.performance_detector.threshold,
            contamination=self.behavioral_detector.contamination,
            last_trained_at=self.behavioral_detector.last_trained_at,
            alert_counts_last_24h={t: self._count_recent_alerts(t) for t in ALERT_TYPES},
        )

    def update_settings(
        self, z_score_threshold: float | None = None, contamination: float | None = None
    ) -> ThresholdSettings:
        """yeni eşikleri hem canlı detector'lara hem Redis'e uyguluyor - servis yeniden başlasa da korunuyor"""
        if z_score_threshold is not None:
            self.performance_detector.set_threshold(z_score_threshold)
            self.redis.set(Z_SCORE_KEY, z_score_threshold)

        if contamination is not None:
            self.behavioral_detector.set_contamination(contamination)
            self.redis.set(CONTAMINATION_KEY, contamination)

        return self.get_settings()

    def record_alert(self, alert_type: str) -> None:
        """bir alarm başarıyla backend'e yazıldığında çağrılıyor - 24 saatlik sayaç için.
        member olarak uuid kullanıyor çünkü art arda çağrılarda time.time() aynı değeri
        verebiliyor, aynı member ZADD'de üzerine yazar ve bir kaydı kaybettirirdi"""
        key = f"{ALERT_COUNT_KEY_PREFIX}{alert_type}"
        now = time.time()
        self.redis.zadd(key, {str(uuid.uuid4()): now})
        self.redis.zremrangebyscore(key, 0, now - ALERT_COUNT_WINDOW_SECONDS)

    def _count_recent_alerts(self, alert_type: str) -> int:
        key = f"{ALERT_COUNT_KEY_PREFIX}{alert_type}"
        cutoff = time.time() - ALERT_COUNT_WINDOW_SECONDS
        return self.redis.zcount(key, cutoff, "+inf")

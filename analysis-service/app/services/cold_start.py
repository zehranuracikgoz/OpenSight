"""
ColdStartManager: RabbitMQ'dan gelen özellik vektörlerini ilk cold_start_seconds boyunca
Redis'te (behavioral:baseline:v2) baseline olarak biriktiriyor, süre dolunca
BehavioralAnomalyDetector.fit()'i otomatik tetikliyor ve canlı tespite geçiyor.
Simülatörün kendi cold_start_seconds'ı (varsayılan 90s, "hangi trafik profili
üretilsin" kararı) ile buradaki cold_start_seconds (varsayılan da 90s, ama "model
ne zaman eğitilsin" kararı) birbirinden bağımsız ayarlanabilir - aynı varsayılan
değer, ikisinin mantıken aynı cold start penceresine denk gelmesi için seçildi.

Redis'teki baseline kalıcıdır (servis yeniden başlasa da silinmez) - bu yüzden
başlangıçta zaten MIN_BASELINE_SAMPLES kadar örnek varsa (önceki bir çalışmadan
kalmış), cold start hiç beklenmeden model o veriyle hemen eğitiliyor. Bu, Render'da
baseline'ın bir kez toplanıp sonraki restart'larda tekrar beklenmemesini sağlıyor.
"""
from __future__ import annotations

import logging
import time

from redis import Redis
from redis.exceptions import RedisError

from app.services.behavioral_detector import BehavioralAnomalyDetector

logger = logging.getLogger("opensight.cold_start")

# v2: ikinci feature endpoint çeşitliliğinden en sık endpoint payına geçti, eski vektörlerle karışmasın
BASELINE_KEY = "behavioral:baseline:v2"
# 5 örnek yetmiyordu, model neredeyse rastgele sınır öğreniyordu; 30'da şüpheli güvenli marjla ayrışıyor
MIN_BASELINE_SAMPLES = 30
# istemci başına en fazla bu aralıkla örnek alınıyor - yoksa yoğun istemci baseline'ı basıyor, normal kayboluyor
BASELINE_MIN_GAP_SECONDS = 5.0

# istek_orani mutlak (req/s) - baseline'ı hangi ölçekte topladığımızı kaydediyoruz (demo 0.02 ≠ baseline 0.1 olabilir)
BASELINE_SCALE_KEY = "behavioral:baseline:scale"
SIMULATOR_ACTIVE_SCALE_KEY = "simulator:active_scale"


class ColdStartManager:
    def __init__(
        self,
        redis_client: Redis,
        behavioral_detector: BehavioralAnomalyDetector,
        cold_start_seconds: int = 90,
        baseline_min_gap_seconds: float = BASELINE_MIN_GAP_SECONDS,
    ):
        self.redis = redis_client
        self.behavioral_detector = behavioral_detector
        self.cold_start_seconds = cold_start_seconds
        self.start_time = time.monotonic()
        self._completed = False
        self.baseline_min_gap_seconds = baseline_min_gap_seconds
        self._last_sample_at: dict[str, float] = {}
        self._resume_from_persisted_baseline()

    def _resume_from_persisted_baseline(self) -> None:
        """Redis'te önceki bir çalışmadan kalma yeterli baseline varsa cold start'ı
        atlayıp modeli hemen o veriyle eğitiyor"""
        try:
            baseline = self._read_baseline()
        except RedisError as exc:
            # Redis o an ulaşılamıyorsa servis açılışta çökmesin, normal cold start'la devam etsin
            logger.warning("kalıcı baseline okunamadı (%s), normal cold start ile devam ediliyor", exc)
            return
        if len(baseline) >= MIN_BASELINE_SAMPLES:
            self.behavioral_detector.fit(baseline)
            self._completed = True
            logger.info(
                "Redis'te kalıcı baseline bulundu (%d örnek), cold start atlanıp model hemen eğitildi",
                len(baseline),
            )

    def read_baseline(self) -> list[list[float]]:
        return self._read_baseline()

    def _read_baseline(self) -> list[list[float]]:
        raw = self.redis.lrange(BASELINE_KEY, 0, -1)
        # redis_client decode_responses=True olmadan da çağrılabilir (bytes döner), bu yüzden burada normalize ediyor
        rows = [row.decode("utf-8") if isinstance(row, bytes) else row for row in raw]
        return [[float(v) for v in row.split(",")] for row in rows]

    def baseline_size(self) -> int:
        return self.redis.llen(BASELINE_KEY)

    def baseline_scale(self) -> float | None:
        raw = self.redis.get(BASELINE_SCALE_KEY)
        return float(raw) if raw is not None else None

    def _record_baseline_scale(self) -> None:
        """baseline'ı hangi ölçekte topladığımızı kaydediyor - anahtar yoksa hiçbir şey yazmıyor"""
        active_scale = self.redis.get(SIMULATOR_ACTIVE_SCALE_KEY)
        if active_scale is not None:
            self.redis.set(BASELINE_SCALE_KEY, active_scale)

    def is_in_cold_start(self) -> bool:
        return not self._completed and (time.monotonic() - self.start_time) < self.cold_start_seconds

    def is_ready(self) -> bool:
        return self._completed

    def handle(self, client_id: str, feature_vector: list[float], timestamp: float) -> None:
        """her yeni özellik vektörü geldiğinde çağrılıyor - baseline topluyor ya da modeli eğitip canlı tespite geçiyor"""
        if self._completed:
            return

        if self.is_in_cold_start():
            last = self._last_sample_at.get(client_id)
            if last is None or timestamp - last >= self.baseline_min_gap_seconds:
                self._last_sample_at[client_id] = timestamp
                self.redis.rpush(BASELINE_KEY, ",".join(str(v) for v in feature_vector))
            return

        self._finish_cold_start()

    def _finish_cold_start(self) -> None:
        baseline = self._read_baseline()

        if len(baseline) < MIN_BASELINE_SAMPLES:
            logger.warning(
                "cold start süresi doldu ama yeterli baseline verisi yok (%d örnek), süre uzatılıyor",
                len(baseline),
            )
            self.start_time = time.monotonic()
            return

        self.behavioral_detector.fit(baseline)
        self._record_baseline_scale()
        self._completed = True
        logger.info("cold start tamamlandı, model %d örnekle eğitildi, canlı tespite geçiliyor", len(baseline))

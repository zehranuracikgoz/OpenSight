"""
AnomalyPipeline'ın orkestrasyon mantığını (backend'e yazma, korelasyon, Ollama tabanlı
açıklama zenginleştirmesinin arka planda çalışması) mock'lanmış detector'lar, BackendClient
ve ExplanationGenerator ile doğruluyor - gerçek Redis/HTTP/Ollama gerektirmiyor
"""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

from app.services.anomaly_pipeline import AnomalyPipeline
from app.services.behavioral_detector import BehavioralScoreResult
from app.services.correlation_engine import CorrelationEngine
from app.services.performance_detector import ZScoreResult


def _wait_until(predicate, timeout: float = 2.0, interval: float = 0.02) -> bool:
    """arka plan thread'inin işini bitirmesini kısa aralıklarla kontrol ederek bekliyor -
    sabit bir sleep yerine, testin gereksiz yavaşlamasını önlemek için"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def _make_pipeline(
    perf_is_anomaly=False, behavioral_is_anomaly=False, cold_start_ready=True, with_explanation_generator=False
):
    performance_detector = MagicMock()
    performance_detector.update_and_score.return_value = ZScoreResult(
        z_score=5.0 if perf_is_anomaly else 0.5, is_anomaly=perf_is_anomaly, mean=50.0, std=2.0
    )

    behavioral_detector = MagicMock()
    behavioral_detector.score.return_value = BehavioralScoreResult(
        anomaly_score=0.9 if behavioral_is_anomaly else 0.1, is_anomaly=behavioral_is_anomaly
    )

    traffic_window = MagicMock()
    traffic_window.record.return_value = [1.0, 0.5, 40.0]

    cold_start = MagicMock()
    cold_start.is_ready.return_value = cold_start_ready

    correlation_engine = CorrelationEngine(window_seconds=1800)
    backend_client = MagicMock()

    explanation_generator = None
    if with_explanation_generator:
        explanation_generator=MagicMock()
        explanation_generator.fallback_template.side_effect = (
            lambda client_id, alert_type, severity: f"sablon: {client_id}/{alert_type}/{severity}"
        )

    pipeline = AnomalyPipeline(
        performance_detector, behavioral_detector, traffic_window, cold_start, correlation_engine, backend_client,
        explanation_generator=explanation_generator,
    )
    return pipeline, backend_client


def test_no_anomaly_does_not_post_alert():
    pipeline, backend_client = _make_pipeline()

    pipeline.process("client_a", "/v1/accounts", 50, timestamp=1000.0)

    backend_client.post_alert.assert_not_called()
    backend_client.post_correlation.assert_not_called()


def test_performance_anomaly_posts_alert_but_not_correlation():
    pipeline, backend_client = _make_pipeline(perf_is_anomaly=True)
    backend_client.post_alert.return_value = "alert-1"

    pipeline.process("client_a", "/v1/accounts", 5000, timestamp=1000.0)

    backend_client.post_alert.assert_called_once_with(
        "client_a", "Performans", "Orta", z_score=5.0, related_endpoint="/v1/accounts", request_rate_pct=1.0
    )
    backend_client.post_correlation.assert_not_called()


def test_behavioral_detection_skipped_during_cold_start():
    pipeline, backend_client = _make_pipeline(behavioral_is_anomaly=True, cold_start_ready=False)

    pipeline.process("client_a", "/v1/accounts", 50, timestamp=1000.0)

    pipeline.behavioral_detector.score.assert_not_called()
    backend_client.post_alert.assert_not_called()


def test_behavioral_anomaly_includes_request_rate_from_feature_vector():
    pipeline, backend_client = _make_pipeline(behavioral_is_anomaly=True, cold_start_ready=True)
    backend_client.post_alert.return_value = "alert-1"

    pipeline.process("client_a", "/v1/accounts", 50, timestamp=1000.0)

    backend_client.post_alert.assert_called_once_with(
        "client_a", "Davranışsal", "Yüksek" , anomaly_score=0.9, related_endpoint="/v1/accounts", request_rate_pct=1.0
    )


def test_overlapping_anomalies_post_correlation():
    pipeline, backend_client = _make_pipeline(perf_is_anomaly=True, behavioral_is_anomaly=True)
    backend_client.post_alert.side_effect = ["perf-1", "beh-1"]
    backend_client.post_correlation.return_value = "corr-1"

    pipeline.process("client_a", "/v1/accounts", 5000, timestamp=1000.0)

    assert backend_client.post_alert.call_count == 2
    backend_client.post_correlation.assert_called_once_with("perf-1", "beh-1")


def test_failed_alert_post_skips_correlation_attempt():
    pipeline, backend_client = _make_pipeline(perf_is_anomaly=True, behavioral_is_anomaly=True)
    backend_client.post_alert.return_value = None  # backend'e ulaşılamadı

    pipeline.process("client_a", "/v1/accounts", 5000, timestamp=1000.0)

    backend_client.post_correlation.assert_not_called()

def test_alert_includes_fallback_description_when_explanation_generator_configured():
    pipeline, backend_client = _make_pipeline(perf_is_anomaly=True, with_explanation_generator=True)
    backend_client.post_alert.return_value = "alert-1"
    pipeline.explanation_generator.generate_explanation.return_value = "sablon: client_a/Performans/Orta"

    pipeline.process("client_a", "/v1/accounts", 5000, timestamp=1000.0)

    _, kwargs = backend_client.post_alert.call_args
    assert kwargs["description"] =="sablon: client_a/Performans/Orta"


def test_process_does_not_block_on_slow_ollama_call():
    """Ollama 3sn'e kadar sürebiliyor ama process() bunu hiç beklememeli - RabbitMQ tüketim
    hızı Ollama'nın yanıt süresine bağlı olmamalı"""
    pipeline, backend_client = _make_pipeline(perf_is_anomaly=True, with_explanation_generator=True)
    backend_client.post_alert.return_value = "alert-1"
    ollama_release = threading.Event()

    def slow_generate_explanation(*args, **kwargs):
        ollama_release.wait(timeout=2)
        return "geç gelen açıklama"

    pipeline.explanation_generator.generate_explanation.side_effect = slow_generate_explanation

    start = time.monotonic()
    pipeline.process("client_a", "/v1/accounts", 5000, timestamp=1000.0)
    elapsed = time.monotonic() - start

    assert elapsed < 0.5
    ollama_release.set()  # arka plan thread'inin temiz bitmesi için serbest bırakıyor

def test_background_refinement_patches_description_when_ollama_succeeds():
    pipeline, backend_client = _make_pipeline(perf_is_anomaly=True, with_explanation_generator=True)
    backend_client.post_alert.return_value = "alert-1"
    pipeline.explanation_generator.generate_explanation.return_value = "Ollama'nın ürettiği zengin açıklama"

    pipeline.process("client_a", "/v1/accounts", 5000, timestamp=1000.0)

    assert _wait_until(lambda: backend_client.patch_alert_description.called)
    backend_client.patch_alert_description.assert_called_once_with(
        "alert-1", "Ollama'nın ürettiği zengin açıklama"
    )


def test_background_refinement_skips_patch_when_ollama_falls_back_to_same_template():
    """generate_explanation, ollama başarısız olduğunda zaten şablon metnini döndürüyor -
    bu durumda tekrar PATCH atmaya gerek yok"""
    pipeline, backend_client = _make_pipeline(perf_is_anomaly=True, with_explanation_generator=True)
    backend_client.post_alert.return_value = "alert-1"
    pipeline.explanation_generator.generate_explanation.return_value = "sablon: client_a/Performans/Orta"

    pipeline.process("client_a", "/v1/accounts", 5000, timestamp=1000.0)

    time.sleep(0.3)
    backend_client.patch_alert_description.assert_not_called()


def test_background_refinement_error_is_swallowed_silently():
    pipeline, backend_client = _make_pipeline(perf_is_anomaly=True, with_explanation_generator=True)
    backend_client.post_alert.return_value = "alert-1"
    pipeline.explanation_generator.generate_explanation.side_effect = RuntimeError("beklenmeyen hata")

    pipeline.process("client_a", "/v1/accounts", 5000, timestamp=1000.0)  # patlamamalı

    time.sleep(0.3)
    backend_client.patch_alert_description.assert_not_called()


def test_no_explanation_refinement_when_explanation_generator_not_configured():
    pipeline, backend_client = _make_pipeline(perf_is_anomaly=True, with_explanation_generator=False)
    backend_client.post_alert.return_value = "alert-1"

    pipeline.process ("client_a", "/v1/accounts", 5000, timestamp=1000.0)

    time.sleep(0.2)
    backend_client.patch_alert_description.assert_not_called()


def _set_anomalies(pipeline, perf: bool, behavioral: bool) -> None:
    """aynı pipeline üzerinde adım adım farklı anomali durumları simüle etmek için"""
    pipeline.performance_detector.update_and_score.return_value = ZScoreResult(
        z_score=5.0 if perf else 0.5, is_anomaly=perf, mean=50.0, std=2.0
    )
    pipeline.behavioral_detector.score.return_value = BehavioralScoreResult(
        anomaly_score=0.9 if behavioral else 0.1, is_anomaly=behavioral
    )


def test_same_type_alert_suppressed_within_cooldown():
    pipeline, backend_client = _make_pipeline(perf_is_anomaly=True)
    backend_client.post_alert.return_value = "alert-1"

    pipeline.process("client_a", "/v1/accounts", 5000, timestamp=1000.0)
    pipeline.process("client_a", "/v1/accounts", 5000, timestamp=1000.0 + 299)

    assert backend_client.post_alert.call_count == 1


def test_same_type_alert_written_again_after_cooldown_elapses():
    pipeline, backend_client = _make_pipeline(perf_is_anomaly=True)
    backend_client.post_alert.return_value = "alert-1"

    pipeline.process("client_a", "/v1/accounts", 5000, timestamp=1000.0)
    pipeline.process("client_a", "/v1/accounts", 5000, timestamp=1000.0 + 300)

    assert backend_client.post_alert.call_count == 2


def test_cooldown_is_configurable():
    pipeline, backend_client = _make_pipeline(perf_is_anomaly=True)
    pipeline.alert_cooldown_seconds = 10
    backend_client.post_alert.return_value = "alert-1"

    pipeline.process("client_a", "/v1/accounts", 5000, timestamp=1000.0)
    pipeline.process("client_a", "/v1/accounts", 5000, timestamp=1011.0)

    assert backend_client.post_alert.call_count == 2

def test_cooldown_is_tracked_per_client():
    pipeline, backend_client = _make_pipeline(perf_is_anomaly=True)
    backend_client.post_alert.return_value = "alert-1"

    pipeline.process("client_a", "/v1/accounts", 5000, timestamp=1000.0)
    pipeline.process("client_b", "/v1/accounts", 5000, timestamp=1001.0)

    assert backend_client.post_alert.call_count == 2


def test_cooldown_is_tracked_per_alert_type():
    pipeline, backend_client = _make_pipeline(perf_is_anomaly=True)
    backend_client.post_alert.side_effect = ["perf-1", "beh-1"]

    pipeline.process("client_a", "/v1/accounts", 5000, timestamp=1000.0)
    _set_anomalies(pipeline, perf=True, behavioral=True)
    pipeline.process("client_a", "/v1/accounts", 5000, timestamp=1010.0)

    # performans cooldown'da (bastirildi) ama davranışsal ilk kez geliyor, yazılmalı
    types=[c.args[1] for c in backend_client.post_alert.call_args_list]
    assert types == ["Performans", "Davranışsal"]


def test_failed_post_does_not_start_cooldown():
    pipeline, backend_client = _make_pipeline(perf_is_anomaly=True)
    backend_client.post_alert.side_effect = [None, "alert-1"]  # ilk yazım başarısız

    pipeline.process("client_a", "/v1/accounts", 5000, timestamp=1000.0)
    pipeline.process("client_a", "/v1/accounts", 5000, timestamp=1001.0)

    assert backend_client.post_alert.call_count == 2


def test_cooldown_does_not_break_correlation_with_earlier_alert_of_other_type():
    """performans alarmı yazıldıktan sonra tekrarları bastırılsa bile, aynı istemcide sonradan
    gelen davranışsal alarm hâlâ o performans alarmıyla eşleşip korelasyon üretmeli"""
    pipeline, backend_client = _make_pipeline(perf_is_anomaly=True)
    backend_client.post_alert.side_effect = ["perf-1", "beh-1"]
    backend_client.post_correlation.return_value = "corr-1"

    pipeline.process("client_a", "/v1/accounts", 5000, timestamp=1000.0)  # perf-1 yazıldı
    pipeline.process("client_a", "/v1/accounts", 5000, timestamp=1100.0)  #perf cooldown'da, bastırıldı
    _set_anomalies(pipeline, perf=False, behavioral= True)
    pipeline.process("client_a", "/v1/accounts", 50, timestamp=1200.0)  # beh-1 yazıldı

    assert backend_client.post_alert.call_count == 2
    backend_client.post_correlation.assert_called_once_with("perf-1", "beh-1")


def test_overlapping_anomalies_still_correlate_again_after_cooldown():
    pipeline, backend_client = _make_pipeline(perf_is_anomaly=True, behavioral_is_anomaly=True)
    backend_client.post_alert.side_effect = ["perf-1", "beh-1", "perf-2", "beh-2"]
    backend_client.post_correlation.return_value = "corr"

    pipeline.process("client_a", "/v1/accounts", 5000, timestamp=1000.0)
    pipeline.process("client_a", "/v1/accounts", 5000, timestamp=1100.0)  # ikisi de cooldown'da
    pipeline.process("client_a", "/v1/accounts", 5000, timestamp=1000.0 + 300)

    assert backend_client.post_alert.call_count== 4
    assert [c.args for c in backend_client.post_correlation.call_args_list] == [
        ("perf-1", "beh-1"),
        ("perf-2", "beh-2"),
    ]
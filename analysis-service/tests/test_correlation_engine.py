from datetime import datetime, timedelta, timezone

from app.services.correlation_engine import CorrelationEngine, PendingAlert


def test_overlapping_anomalies_correlate():
    """aynı client_id için performans + davranışsal anomali eş zamanlı tetiklenirse birleşik olay üretiliyor"""
    ce = CorrelationEngine(window_seconds=1800)
    t0 = datetime.now(timezone.utc)

    r1 = ce.register_alert(PendingAlert("perf-1", "client_x", "Performans", t0))
    assert r1 is None

    r2 = ce.register_alert(PendingAlert("beh-1", "client_x", "Davranışsal", t0 + timedelta(minutes=5)))
    assert r2 is not None
    assert r2.performance_alert_id == "perf-1"
    assert r2.behavioral_alert_id == "beh-1"


def test_non_overlapping_anomalies_do_not_correlate():
    """iki anomali türü farklı zaman pencerelerinde tetiklenirse korelasyon oluşmayacak"""
    ce = CorrelationEngine(window_seconds=1800)
    t0 = datetime.now(timezone.utc)

    ce.register_alert(PendingAlert("perf-1", "client_y", "Performans", t0))
    result = ce.register_alert(PendingAlert("beh-1", "client_y", "Davranışsal", t0 + timedelta(minutes=40)))
    assert result is None


def test_different_clients_do_not_correlate():
    ce = CorrelationEngine(window_seconds=1800)
    t0 = datetime.now(timezone.utc)

    ce.register_alert(PendingAlert("perf-1", "client_a", "Performans", t0))
    result = ce.register_alert(PendingAlert("beh-1", "client_b", "Davranışsal", t0))
    assert result is None


def test_same_type_alerts_do_not_correlate():
    """iki performans alert'i birbiriyle eşleşmeyecek - yalnızca zıt türler korelasyon üretiyor"""
    ce = CorrelationEngine(window_seconds=1800)
    t0 = datetime.now(timezone.utc)

    ce.register_alert(PendingAlert("perf-1", "client_z", "Performans", t0))
    result = ce.register_alert(PendingAlert("perf-2", "client_z", "Performans", t0 + timedelta(minutes=1)))
    assert result is None

def test_correlation_result_carries_descriptions_and_performance_summary():
    engine = CorrelationEngine (window_seconds=1800)
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    engine.register_alert(PendingAlert("perf-1", "c1", "Performans", t0, description="perf açıklama", summary="gecikme 320 ms, z = 4.7"))

    result=engine.register_alert(
        PendingAlert("beh-1", "c1", "Davranışsal", t0 + timedelta(seconds=5), description="beh açıklama")
    )

    assert result.performance_description == "perf açıklama"
    assert result.behavioral_description == "beh açıklama"
    assert result.performance_summary == "gecikme 320 ms, z = 4.7"
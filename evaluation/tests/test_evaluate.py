from datetime import datetime, timedelta, timezone

import pytest

import evaluate as ev

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def at(seconds: float) -> str:
    return (BASE + timedelta(seconds=seconds)).isoformat()


def gt(client_id: str, seconds: float, profile: str) -> dict:
    return {"client_id": client_id, "timestamp": at(seconds), "profile": profile}


def burst(client_id: str, seconds: float, phase: str) -> dict:
    return {"client_id": client_id, "timestamp": at(seconds), "phase": phase}


def alert(alert_id: str, client_id: str, alert_type: str, seconds: float) -> dict:
    return {"alertId": alert_id, "clientId": client_id, "type": alert_type, "severity": "Orta", "createdAt": at(seconds)}


def corr(correlation_id: str, client_id: str, perf_id: str, beh_id: str, seconds: float) -> dict:
    return {
        "correlationId": correlation_id, "clientId": client_id,
        "performanceAlertId": perf_id, "behavioralAlertId": beh_id, "detectedAt": at(seconds),
    }


def test_profile_of_extracts_profile_from_client_id():
    assert ev.profile_of("client_normal_0000") == "normal"
    assert ev.profile_of("client_yogun_0002") == "yogun"
    assert ev.profile_of("client_supheli_0001") == "supheli"
    assert ev.profile_of("garip_id") == "bilinmeyen"


def test_build_windows_only_includes_active_windows():
    records = [gt("c1", 0, "normal"), gt("c1", 100, "normal"), gt("c1", 650, "normal")]  # 350-650 arası bos

    windows = ev.build_windows(records, BASE, BASE + timedelta(seconds=900), window_seconds=300)

    assert len(windows["c1"]) == 2  # [0,300) dolu, [300,600) bos (atlaniyor), [600,900) dolu
    assert windows["c1"][0] == (BASE, BASE + timedelta(seconds=300))
    assert windows["c1"][-1] == (BASE + timedelta(seconds=600), BASE + timedelta(seconds=900))


def test_build_windows_excludes_events_outside_eval_range():
    records = [gt("c1", -100, "normal"), gt("c1", 50, "normal")]

    windows = ev.build_windows(records, BASE, BASE + timedelta(seconds=300), window_seconds=300)

    assert len(windows["c1"]) == 1  # -100'deki olay eval_start'tan once, sayilmiyor


def test_reconstruct_burst_intervals_pairs_start_and_end():
    events = [burst("y1", 300, "patlama"), burst("y1", 500, "sakin")]

    intervals = ev.reconstruct_burst_intervals(events, run_end=BASE + timedelta(seconds=1000))

    assert intervals["y1"] == [(BASE + timedelta(seconds=300), BASE + timedelta(seconds=500))]


def test_reconstruct_burst_intervals_open_burst_extends_to_run_end():
    events = [burst("y1", 300, "patlama")]  # hic "sakin" gelmemis

    intervals = ev.reconstruct_burst_intervals(events, run_end=BASE + timedelta(seconds=1000))

    assert intervals["y1"] == [(BASE + timedelta(seconds=300), BASE + timedelta(seconds=1000))]


def test_window_overlaps_burst():
    window = (BASE, BASE + timedelta(seconds=300))
    overlapping = (BASE + timedelta(seconds=100), BASE + timedelta(seconds=200))
    non_overlapping = (BASE + timedelta(seconds=400), BASE + timedelta(seconds=500))

    assert ev.window_overlaps_burst(window, [overlapping]) is True
    assert ev.window_overlaps_burst(window, [non_overlapping]) is False


def test_has_alert_in_window():
    index = ev.alert_timestamps_by_client_type([alert("a1", "c1", "Performans", 150)])
    window = (BASE, BASE + timedelta(seconds=300))

    assert ev.has_alert_in_window(index, "c1", "Performans", window) is True
    assert ev.has_alert_in_window(index, "c1", "Davranışsal", window) is False
    assert ev.has_alert_in_window(index, "c2", "Performans", window) is False


def test_confusion_metrics():
    c = ev.Confusion()
    c.add(predicted=True, actual=True)
    c.add(predicted=True, actual=False)
    c.add(predicted=False, actual=True)
    c.add(predicted=False, actual=False)

    d = c.as_dict()
    assert d["tp"] == 1 and d["fp"] == 1 and d["fn"] == 1 and d["tn"] == 1
    assert d["precision"] == pytest.approx(0.5)
    assert d["recall"] == pytest.approx(0.5)
    assert d["f1"] == pytest.approx(0.5)
    assert d["false_positive_rate"] == pytest.approx(0.5)


def test_confusion_metrics_are_none_when_undefined():
    c = ev.Confusion()
    c.add(predicted=False, actual=False)

    d = c.as_dict()
    assert d["precision"] is None
    assert d["recall"] is None
    assert d["f1"] is None
    assert d["false_positive_rate"] == pytest.approx(0.0)


def test_evaluate_correlations_computes_supheli_precision_and_flags_window_violation():
    alerts_by_id = {
        "perf-1": alert("perf-1", "client_supheli_0000", "Performans", 100),
        "beh-1": alert("beh-1", "client_supheli_0000", "Davranışsal", 150),
        "perf-2": alert("perf-2", "client_yogun_0000", "Performans", 100),
        "beh-2": alert("beh-2", "client_yogun_0000", "Davranışsal", 3000),  # fark 2900s > 1800s
    }
    correlations = [
        corr("corr-1", "client_supheli_0000", "perf-1", "beh-1", 150),
        corr("corr-2", "client_yogun_0000", "perf-2", "beh-2", 3000),
    ]

    result = ev.evaluate_correlations(correlations, alerts_by_id, correlation_window_seconds=1800)

    assert result["total"] == 2
    assert result["by_profile"] == {"supheli": 1, "yogun": 1}
    assert result["supheli_precision"] == pytest.approx(0.5)
    assert len(result["window_violations"]) == 1
    assert "corr-2" in result["window_violations"][0]


def test_evaluate_correlations_flags_missing_alert():
    correlations = [corr("corr-1", "client_yogun_0000", "perf-missing", "beh-missing", 0)]

    result = ev.evaluate_correlations(correlations, alerts_by_id={}, correlation_window_seconds=1800)

    assert result["window_violations"] == ["corr-1 (alarm bulunamadı)"]


def test_run_evaluation_end_to_end_with_synthetic_data():
    ground_truth = [
        gt("client_normal_0000", 0, "normal"), gt("client_normal_0000", 100, "normal"),
        gt("client_yogun_0000", 0, "yogun"), gt("client_yogun_0000", 350, "yogun"),
        gt("client_yogun_0000", 650, "yogun"), gt("client_yogun_0000", 950, "yogun"),
        gt("client_supheli_0000", 0, "supheli"), gt("client_supheli_0000", 350, "supheli"),
    ]
    burst_events = [burst("client_yogun_0000", 300, "patlama"), burst("client_yogun_0000", 500, "sakin")]
    alerts = [
        alert("beh-normal", "client_normal_0000", "Davranışsal", 10),  # yanlis pozitif
        alert("beh-supheli-1", "client_supheli_0000", "Davranışsal", 50),  # dogru pozitif (pencere 1)
        # supheli pencere 2'de (300-600) alarm yok -> yanlis negatif
        alert("perf-yogun", "client_yogun_0000", "Performans", 320),  # dogru pozitif (patlama pencerede)
    ]
    correlations = []

    result = ev.run_evaluation(ground_truth, burst_events, alerts, correlations, eval_start=BASE, window_seconds=300)

    assert result["window_counts_by_profile"] == {"normal": 1, "yogun": 4, "supheli": 2}

    behavioral = result["behavioral"]["overall"]
    assert (behavioral["tp"], behavioral["fp"], behavioral["fn"], behavioral["tn"]) == (1, 1, 1, 4)

    strict = result["performance_strict"]["overall"]
    assert (strict["tp"], strict["fp"], strict["fn"], strict["tn"]) == (1, 0, 0, 6)

    # genis tanimda supheli'nin 2 penceresi de pozitif ama alarm yok -> ikisi de yanlis negatif
    broad = result["performance_broad"]["overall"]
    assert (broad["tp"], broad["fp"], broad["fn"], broad["tn"]) == (1, 0, 2, 4)


def test_run_evaluation_raises_on_empty_ground_truth():
    with pytest.raises(ValueError):
        ev.run_evaluation([], [], [], [], eval_start=BASE)


def test_render_markdown_includes_key_sections():
    ground_truth = [gt("client_normal_0000", 0, "normal"), gt("client_supheli_0000", 0, "supheli")]
    result = ev.run_evaluation(ground_truth, [], [], [], eval_start=BASE, window_seconds=300)

    markdown = ev.render_markdown(result)

    assert "# OpenSight Değerlendirme Sonucu" in markdown
    assert "Davranışsal" in markdown
    assert "Performans - katı" in markdown
    assert "Korelasyon" in markdown

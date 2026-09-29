import json
import threading
import time

import pytest

import traffic_simulator as ts


def test_constant_rate_always_returns_same_value():
    rate_fn = ts.constant_rate(2.5)
    assert rate_fn() ==2.5
    assert rate_fn() == 2.5


def test_burst_rate_range_default_and_env_override(monkeypatch):
    monkeypatch.delenv("SIMULATOR_YOGUN_BURST_RATE", raising=False)
    assert ts.burst_rate_range() == ts.DEFAULT_YOGUN_BURST_RATE_RANGE

    monkeypatch.setenv("SIMULATOR_YOGUN_BURST_RATE", "10-15")
    assert ts.burst_rate_range() == (10.0, 15.0)


def test_burst_duration_and_interval_range_default_and_env_override(monkeypatch):
    monkeypatch.delenv("SIMULATOR_YOGUN_BURST_DURATION", raising=False)
    monkeypatch.delenv("SIMULATOR_YOGUN_BURST_INTERVAL", raising=False)
    assert ts.burst_duration_range() == ts.DEFAULT_YOGUN_BURST_DURATION_RANGE
    assert ts.burst_interval_range() == ts.DEFAULT_YOGUN_BURST_INTERVAL_RANGE

    monkeypatch.setenv ("SIMULATOR_YOGUN_BURST_DURATION", "5-9")
    monkeypatch.setenv("SIMULATOR_YOGUN_BURST_INTERVAL", "50-70")
    assert ts.burst_duration_range() == (5.0, 9.0)
    assert ts.burst_interval_range() == (50.0, 70.0)


def test_burst_range_rejects_invalid_format(monkeypatch):
    monkeypatch.setenv("SIMULATOR_YOGUN_BURST_RATE", "40-10")  # ters aralık
    with pytest.raises(ValueError):
        ts.burst_rate_range()


def test_yogun_burst_provider_toggles_between_calm_and_burst(monkeypatch):
    """z-score son 50 isteğe göre çalıştığı için yoğun sabit hızda kalmamalı - sağlayıcı,
    yapılandırılan aralık dolunca sakin<->patlama arasında geçiş yapmalı"""
    monkeypatch.setenv("SIMULATOR_RATE_SCALE", "1.0")
    monkeypatch.setenv("SIMULATOR_YOGUN_RATE", "5-5")
    monkeypatch.setenv("SIMULATOR_YOGUN_BURST_RATE", "50-50")
    monkeypatch.setenv("SIMULATOR_YOGUN_BURST_DURATION", "20-20")
    monkeypatch.setenv("SIMULATOR_YOGUN_BURST_INTERVAL", "30-30")

    fake_now = [1000.0]
    monkeypatch.setattr(ts.time, "monotonic", lambda: fake_now[0])

    provider = ts.YogunBurstRateProvider()
    assert provider() == pytest.approx(5.0)  # sakin fazda başlıyor

    fake_now[0] += 30.0  # sakin aralık doldu -> patlamaya geçmeli
    assert provider() == pytest.approx(50.0)

    fake_now[0] += 5.0  #patlama süresi henüz dolmadı -> patlamada kalmalı
    assert provider() == pytest.approx(50.0)

    fake_now[0] += 15.0  # patlama süresi (toplam 20s) doldu -> sakine dönmeli
    assert provider() == pytest.approx(5.0)


def test_yogun_burst_provider_scales_rates_with_rate_scale(monkeypatch):
    monkeypatch.setenv("SIMULATOR_RATE_SCALE", "0.1")
    monkeypatch.setenv("SIMULATOR_YOGUN_RATE", "5-5")
    monkeypatch.setenv("SIMULATOR_YOGUN_BURST_RATE", "50-50")
    monkeypatch.setenv("SIMULATOR_YOGUN_BURST_INTERVAL", "1000-1000")

    provider = ts.YogunBurstRateProvider()
    assert provider() == pytest.approx(0.5)  # 5 * 0.1


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, json_error=False):
        self.status_code = status_code
        self._payload = payload
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise ValueError("json değil")
        return self._payload


def _make_sim(tmp_path, **kwargs):
    return ts.TrafficSimulator("http://api", str(tmp_path / "gt.log"), analysis_url="http://analysis", **kwargs)

def test_model_is_ready_true_only_when_status_reports_model_ready(monkeypatch, tmp_path):
    sim=_make_sim(tmp_path)

    monkeypatch.setattr(ts.requests, "get", lambda url, timeout: _FakeResponse(200, {"model_ready": True}))
    assert sim.model_is_ready() is True

    monkeypatch.setattr(ts.requests, "get", lambda url, timeout: _FakeResponse(200, {"model_ready": False}))
    assert sim.model_is_ready() is False


def test_model_is_ready_false_on_errors(monkeypatch, tmp_path):
    sim = _make_sim(tmp_path)

    def boom(url, timeout):
        raise ts.requests.ConnectionError("servis kapalı")

    monkeypatch.setattr(ts.requests, "get", boom)
    assert sim.model_is_ready() is False

    monkeypatch.setattr(ts.requests, "get", lambda url, timeout: _FakeResponse(503, {"model_ready": True}))
    assert sim.model_is_ready() is False

    monkeypatch.setattr(ts.requests, "get", lambda url, timeout: _FakeResponse(200, json_error=True))
    assert sim.model_is_ready() is False


def test_wait_for_model_releases_suspicious_as_soon_as_model_ready(monkeypatch, tmp_path):
    sim = _make_sim(tmp_path, ready_poll_seconds=0.01)
    answers = iter([False, False, True])
    monkeypatch.setattr(sim, "model_is_ready", lambda: next(answers))

    sim._wait_for_model()

    assert sim._suspicious_go.is_set()


def test_wait_for_model_polls_status_endpoint(monkeypatch, tmp_path):
    sim = _make_sim(tmp_path, ready_poll_seconds=0.01)
    urls = []

    def fake_get(url, timeout):
        urls.append(url)
        return _FakeResponse(200, {"model_ready": True})

    monkeypatch.setattr(ts.requests, "get", fake_get)
    sim._wait_for_model()

    assert urls ==["http://analysis/status"]


def test_wait_for_model_gives_up_after_timeout_but_still_releases(monkeypatch, tmp_path):
    sim = _make_sim(tmp_path, ready_timeout=0.05, ready_poll_seconds=0.01)
    monkeypatch.setattr(sim, "model_is_ready", lambda: False)

    sim._wait_for_model()

    assert sim._suspicious_go.is_set()


def _run_client_briefly(sim, profile, duration=0.3):
    sent = []
    sim.send_request = lambda client_id, endpoint: sent.append(client_id)
    thread = threading.Thread(
        target=sim._client_loop, args=("c", profile, ts.constant_rate(1000.0)), daemon=True
    )
    thread.start()
    time.sleep(duration)
    return sent, thread


def test_suspicious_client_sends_nothing_until_model_ready(tmp_path):
    sim = _make_sim(tmp_path)

    sent, thread = _run_client_briefly(sim, ts.Profile.SUPHELI)
    assert sent==[]  # model hazır değil

    sim._suspicious_go.set ()
    time.sleep(0.3)
    assert len(sent) > 0

    sim.stop()
    thread.join(timeout=2)


@pytest.mark.parametrize("profile", [ts.Profile.NORMAL, ts.Profile.YOGUN])
def test_normal_and_yogun_start_immediately_without_waiting_for_model(tmp_path, profile):
    sim = _make_sim(tmp_path)

    sent, thread = _run_client_briefly(sim, profile)

    assert len(sent) > 0  #süpheli için ayrılan bekleme bunlara uygulanmıyor
    sim.stop()
    thread.join(timeout=2)


def test_stop_releases_suspicious_clients_waiting_for_model(tmp_path):
    sim = _make_sim(tmp_path)
    sim.send_request = lambda client_id, endpoint: None
    thread = threading.Thread(
        target=sim._client_loop, args=("c", ts.Profile.SUPHELI, ts.constant_rate(1.0)), daemon=True
    )
    thread.start()
    time.sleep(0.1)

    sim.stop ()
    thread.join(timeout=2)

    assert not thread.is_alive()

def test_yogun_burst_provider_calls_on_transition_on_each_phase_change(monkeypatch):
    monkeypatch.setenv("SIMULATOR_YOGUN_RATE", "5-5")
    monkeypatch.setenv("SIMULATOR_YOGUN_BURST_RATE", "50-50")
    monkeypatch.setenv("SIMULATOR_YOGUN_BURST_DURATION", "20-20")
    monkeypatch.setenv("SIMULATOR_YOGUN_BURST_INTERVAL", "30-30")

    fake_now = [1000.0]
    monkeypatch.setattr(ts.time, "monotonic", lambda: fake_now[0])
    seen = []

    provider = ts.YogunBurstRateProvider(on_transition=seen.append)
    provider()
    assert seen == []  # henüz gecis yok

    fake_now[0] += 30.0
    provider()
    fake_now[0] += 20.0
    provider()

    assert seen == [True, False]  # once patlamaya girdi, sonra sakine dondu


def test_log_burst_event_writes_client_id_and_phase(tmp_path):
    gt_path = tmp_path / "gt.log"
    sim = ts.TrafficSimulator("http://api", str(gt_path))

    sim.log_burst_event("client_yogun_0000", True)
    sim.log_burst_event("client_yogun_0000", False)

    lines = [json.loads(l) for l in open(sim.burst_log_path, encoding="utf-8")]
    assert [l["phase"] for l in lines] == ["patlama", "sakin"]
    assert all(l["client_id"] == "client_yogun_0000" for l in lines)


def test_burst_log_path_defaults_relative_to_ground_truth_path(tmp_path):
    gt_path = tmp_path / "gt.log"
    sim = ts.TrafficSimulator("http://api", str(gt_path))

    assert sim.burst_log_path == str(gt_path) + ".burst"


def test_schedule_shutdown_stops_sim_and_server_after_duration():
    class FakeSim:
        def __init__(self):
            self.stopped = False

        def stop(self):
            self.stopped = True

    class FakeServer:
        def __init__(self):
            self.shutdown_called = False

        def shutdown(self):
            self.shutdown_called = True

    sim, server = FakeSim(), FakeServer()
    ts.schedule_shutdown(0.05, sim, server)

    assert sim.stopped is False  # henüz erken
    time.sleep(0.2)
    assert sim.stopped is True
    assert server.shutdown_called is True


def test_schedule_shutdown_noop_when_duration_not_positive():
    calls = []

    class FakeServer:
        def shutdown(self):
            calls.append("shutdown")

    ts.schedule_shutdown(0, None, FakeServer())
    time.sleep(0.05)

    assert calls == []

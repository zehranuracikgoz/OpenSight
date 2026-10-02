import json
import threading
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
import requests

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


def _fake_redis():
    import fakeredis
    return fakeredis.FakeStrictRedis(decode_responses=True)


def test_rate_scale_override_takes_precedence(monkeypatch):
    monkeypatch.setenv("SIMULATOR_RATE_SCALE", "0.1")
    assert ts.rate_scale() == pytest.approx(0.1)

    ts.set_scale_override(0.02)
    try:
        assert ts.rate_scale() == pytest.approx(0.02)
    finally:
        ts.set_scale_override(None)

    assert ts.rate_scale() == pytest.approx(0.1)


def test_record_active_scale_writes_to_redis():
    r = _fake_redis()
    ts.record_active_scale(r, 0.02)
    assert r.get(ts.SIMULATOR_ACTIVE_SCALE_KEY) == "0.02"


class TestDemoQuota:
    def test_allows_first_start(self):
        quota = ts.DemoQuota(_fake_redis(), cooldown_seconds=600, daily_limit=3, monthly_limit=35)
        ok, reason = quota.check()
        assert ok is True and reason is None

    def test_blocks_within_cooldown(self):
        r = _fake_redis()
        quota = ts.DemoQuota(r, cooldown_seconds=600, daily_limit=3, monthly_limit=35)
        quota.record_start()

        ok, reason = quota.check()

        assert ok is False
        assert "sonra tekrar deneyin" in reason

    def test_allows_after_cooldown_elapses(self):
        r = _fake_redis()
        quota = ts.DemoQuota(r, cooldown_seconds=1, daily_limit=3, monthly_limit=35)
        quota.record_start()
        time.sleep(1.1)

        ok, reason = quota.check()

        assert ok is True and reason is None

    def test_blocks_after_daily_limit_reached(self):
        r = _fake_redis()
        quota = ts.DemoQuota(r, cooldown_seconds=0, daily_limit=2, monthly_limit=35)
        quota.record_start()
        quota.record_start()

        ok, reason = quota.check()

        assert ok is False
        assert "sınırına" in reason

    def test_daily_limit_is_per_calendar_day(self):
        r = _fake_redis()
        quota = ts.DemoQuota(r, cooldown_seconds=0, daily_limit=1, monthly_limit=100)
        # başka bir günün sayacı dolu ama bugünkü anahtar hâlâ boş
        r.set(quota.COUNT_KEY_PREFIX + "2000-01-01", "99")

        ok, _ = quota.check()

        assert ok is True  # farklı günün sayacı bugünü etkilemiyor

    def test_blocks_after_monthly_limit_reached(self):
        r = _fake_redis()
        quota = ts.DemoQuota(r, cooldown_seconds=0, daily_limit=100, monthly_limit=2)
        quota.record_start()
        quota.record_start()

        ok, reason = quota.check()

        assert ok is False
        assert "bu ayın demo hakkı doldu" in reason

    def test_monthly_limit_is_per_calendar_month(self):
        r = _fake_redis()
        quota = ts.DemoQuota(r, cooldown_seconds=0, daily_limit=100, monthly_limit=1)
        # başka bir ayın sayacı dolu ama bu ayın anahtarı hâlâ boş
        r.set(quota.MONTH_COUNT_KEY_PREFIX + "2000-01", "99")

        ok, _ = quota.check()

        assert ok is True  # farklı ayın sayacı bu ayı etkilemiyor

    def test_record_start_increments_both_daily_and_monthly_counters(self):
        r = _fake_redis()
        quota = ts.DemoQuota(r, cooldown_seconds=0, daily_limit=100, monthly_limit=100)

        quota.record_start()

        assert int(r.get(quota._day_key())) == 1
        assert int(r.get(quota._month_key())) == 1


class TestDemoController:
    def _controller(self, redis_client=None, **kwargs):
        redis_client = redis_client or _fake_redis()
        quota = ts.DemoQuota(
            redis_client,
            cooldown_seconds=kwargs.pop("cooldown", 600),
            daily_limit=kwargs.pop("limit", 3),
            monthly_limit=kwargs.pop("monthly", 100),
        )
        return ts.DemoController(redis_client, "http://api", "http://analysis", quota, **kwargs)

    def test_status_starts_idle(self):
        controller = self._controller()
        assert controller.status()["state"] == "bosta"

    def test_start_rejected_by_quota(self, monkeypatch):
        r = _fake_redis()
        controller = self._controller(redis_client=r, cooldown=600, limit=0)

        ok, reason = controller.start(None)

        assert ok is False
        assert "sınırına" in reason
        assert controller.status()["state"] == "bosta"

    def test_start_rejected_on_scale_mismatch(self, monkeypatch):
        r = _fake_redis()
        r.set(ts.BASELINE_SCALE_KEY, "0.1")
        monkeypatch.setenv("SIMULATOR_DEMO_RATE_SCALE", "0.02")
        controller = self._controller(redis_client=r)

        ok, reason = controller.start(None)

        assert ok is False
        assert "0.1" in reason and "0.02" in reason
        assert controller.status()["state"] == "bosta"

    def test_start_allowed_when_no_baseline_scale_recorded(self, monkeypatch):
        r = _fake_redis()
        monkeypatch.setenv("SIMULATOR_DEMO_RATE_SCALE", "0.02")
        controller = self._controller(redis_client=r)
        monkeypatch.setattr(controller, "_wait_awake", lambda base_url, deadline: False)  # uyanma testi disinda

        ok, reason = controller.start(None)

        assert ok is True and reason is None

    def test_start_rejected_when_already_running(self, monkeypatch):
        r = _fake_redis()
        controller = self._controller(redis_client=r)
        monkeypatch.setattr(controller, "_wait_awake", lambda base_url, deadline: True)
        with controller._lock:
            controller._state = "calisiyor"

        ok, reason = controller.start(None)

        assert ok is False
        assert reason == "zaten çalışıyor"

    def test_run_sets_bosta_with_error_when_services_dont_wake(self, monkeypatch):
        controller = self._controller()
        monkeypatch.setattr(controller, "_ping_once", lambda url: False)
        monkeypatch.setattr(ts, "demo_wake_timeout", lambda: 0.05)

        controller._run(60.0)

        status = controller.status()
        assert status["state"] == "bosta"
        assert "uyanmadı" in status["error"]

    def test_run_reaches_running_state_and_records_quota_when_services_awake(self, monkeypatch, tmp_path):
        r = _fake_redis()
        controller = self._controller(redis_client=r)
        monkeypatch.setattr(controller, "_ping_once", lambda url: True)
        monkeypatch.setattr(ts, "demo_wake_timeout", lambda: 5.0)
        monkeypatch.setattr(ts, "demo_keepalive_interval", lambda: 0.05)
        monkeypatch.setattr(ts, "demo_scorecard_grace", lambda: 0)
        monkeypatch.setattr(controller, "_fetch_scorecard_inputs", lambda: ([], []))

        fake_sim = MagicMock()
        fake_sim._suspicious_go = threading.Event()
        fake_sim._suspicious_go.set()  # model hemen hazir
        fake_sim._stop = threading.Event()
        monkeypatch.setattr(ts, "TrafficSimulator", lambda *a, **k: fake_sim)

        thread = threading.Thread(target=controller._run, args=(0.2,), daemon=True)
        thread.start()
        time.sleep(0.1)
        assert controller.status()["state"] == "calisiyor"
        thread.join(timeout=2)

        assert controller.status()["state"] == "bitti"
        assert r.get(ts.DemoQuota.LAST_STARTED_KEY) is not None
        fake_sim.stop.assert_called_once()
        assert controller.status()["scorecard_pending"] is False
        assert controller.status()["scorecard"]["supheli"] == {"total": 3, "behavioral": 0}

    def test_build_scorecard_uses_fetched_alerts_inside_window(self, monkeypatch):
        controller=self._controller()
        monkeypatch.setattr(ts, "demo_scorecard_grace", lambda: 0)
        now = datetime.now(timezone.utc)
        alert={"alertId": "a1", "clientId": "client_supheli_0000", "type": "Davranışsal", "createdAt": now.isoformat()}
        monkeypatch.setattr(controller, "_fetch_scorecard_inputs", lambda: ([alert], []))

        controller._build_scorecard(now - timedelta(minutes=5))

        status = controller.status()
        assert status["scorecard_pending"] is False
        assert status["scorecard"]["supheli"]["behavioral"] ==1

    def test_scorecard_stays_empty_when_api_unreachable(self, monkeypatch):
        controller = self._controller()
        monkeypatch.setattr(ts, "demo_scorecard_grace", lambda: 0)

        def boom():
            raise requests.ConnectionError("api kapalı")

        monkeypatch.setattr(controller, "_fetch_scorecard_inputs", boom)
        with controller._lock:
            controller._scorecard_pending = True

        controller._build_scorecard(datetime.now(timezone.utc))

        status = controller.status()
        assert status["scorecard"] is None
        assert status["scorecard_pending"] is False

    def test_status_reports_scorecard_pending_while_it_is_being_built(self, monkeypatch):
        controller = self._controller()
        release = threading.Event()
        monkeypatch.setattr(ts, "demo_scorecard_grace", lambda : 0)
        monkeypatch.setattr(controller, "_fetch_scorecard_inputs", lambda: (release.wait(2), ([], []))[1])
        with controller._lock:
            controller._scorecard_pending = True

        thread = threading.Thread(target=controller._build_scorecard, args=(datetime.now(timezone.utc),), daemon=True)
        thread.start()
        time.sleep (0.1)
        assert controller.status()["scorecard_pending"] is True

        release.set()
        thread.join(timeout=3)
        assert controller.status()["scorecard_pending"] is False

    def test_new_demo_start_clears_previous_scorecard(self, monkeypatch):
        controller = self._controller()
        with controller._lock :
            controller._state = "bitti "
            controller._scorecard = {"eski": True}
        monkeypatch.setattr(controller, "_run", lambda duration: None)

        ok, _ = controller.start(None)

        assert ok is True
        assert controller.status()["scorecard"] is None


class TestDemoHttpEndpoints:
    def _start_server(self, port):
        server = ts.HTTPServer(("127.0.0.1", port), ts.HealthCheckHandler)
        r = _fake_redis()
        quota = ts.DemoQuota(r, cooldown_seconds=600, daily_limit=3, monthly_limit=100)
        server.demo_controller = ts.DemoController(r, "http://api", "http://analysis", quota)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    def test_demo_status_endpoint_returns_idle_state(self):
        server, thread = self._start_server(18211)
        try:
            response = requests.get("http://127.0.0.1:18211/demo/status", timeout=3)
            assert response.status_code == 200
            assert response.json()["state"] == "bosta"
            assert response.headers["Access-Control-Allow-Origin"]
        finally:
            server.shutdown()
            thread.join(timeout=2)

    def test_options_preflight_returns_cors_headers(self):
        server, thread = self._start_server(18212)
        try:
            response = requests.options("http://127.0.0.1:18212/demo/start", timeout=3)
            assert response.status_code == 204
            assert response.headers["Access-Control-Allow-Methods"] == "GET, POST, OPTIONS"
        finally:
            server.shutdown()
            thread.join(timeout=2)

    def test_demo_start_returns_409_when_quota_exhausted(self):
        server, thread = self._start_server(18213)
        try:
            server.demo_controller.quota.daily_limit = 0
            response = requests.post("http://127.0.0.1:18213/demo/start", timeout=3)
            assert response.status_code == 409
            assert "sınırına" in response.json()["error"]
        finally:
            server.shutdown()
            thread.join(timeout=2)

    def test_unknown_path_returns_404(self):
        server, thread = self._start_server(18214)
        try:
            response = requests.get("http://127.0.0.1:18214/nope", timeout=3)
            assert response.status_code == 404
        finally:
            server.shutdown()
            thread.join(timeout=2)

    def test_demo_clients_endpoint_returns_true_profiles(self):
        server, thread = self._start_server(18215)
        try:
            response = requests.get("http://127.0.0.1:18215/demo/clients", timeout=3)
            assert response.status_code ==200
            clients = response.json()["clients"]
            assert clients["client_supheli_0001"] == "supheli "
            assert len(clients) == 9
            assert response.headers["Access-Control-Allow-Origin"]
        finally:
            server.shutdown()
            thread.join(timeout=2)


DEMO_START = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
DEMO_END = DEMO_START + timedelta(minutes=5)


def _at(seconds):
    return (DEMO_START + timedelta(seconds=seconds)).isoformat()


def _alert(client_id, alert_type, seconds):
    return {"alertId": f"{client_id}-{alert_type}-{seconds}", "clientId": client_id, "type": alert_type, "createdAt": _at(seconds)}


def _corr(client_id, seconds):
    return {"correlationId": f"c-{client_id}-{seconds}", "clientId": client_id, "detectedAt": _at(seconds)}


def test_client_profiles_maps_every_client_to_its_true_profile():
    assert ts.client_profiles(2) == {
        "client_normal_0000": "normal", "client_normal_0001": "normal",
        "client_yogun_0000": "yogun", "client_yogun_0001": "yogun",
        "client_supheli_0000": "supheli", "client_supheli_0001": "supheli",
    }


def test_scorecard_counts_distinct_clients_per_profile_and_type():
    alerts = [
        _alert("client_supheli_0000", "Davranışsal", 60),
        _alert("client_supheli_0000", "Davranışsal", 200),  #ayni istemci tek sayiliyor
        _alert("client_supheli_0001", "Davranışsal", 90),
        _alert("client_supheli_0002", "Performans", 90),  # supheli performans alarmi davranissal degil
        _alert("client_yogun_0000", "Performans", 100),
        _alert("client_yogun_0001", "Davranışsal", 100),  # yogun davranissal alarmi performans degil
        _alert("client_normal_0000", "Davranışsal", 120),
        _alert("client_normal_0000", "Performans", 130),
    ]
    correlations = [
        _corr("client_supheli_0000", 61), _corr("client_yogun_0000", 101), _corr("client_supheli_0001", 91),
        _corr("client_normal_0001", 150),
    ]

    card = ts.compute_scorecard(ts.client_profiles(3), alerts, correlations, DEMO_START, DEMO_END)

    assert card["supheli"] == {"total": 3, "behavioral" : 2}
    assert card["yogun"] == {"total": 3, "performance": 1, "behavioral_false": 1}
    assert card["normal"] == {"total": 3, "false_alerts": 2}
    assert card["correlations"] == {"total": 4, "supheli": 2, "yogun": 1, "normal": 1}


def test_scorecard_ignores_alerts_and_correlations_outside_the_demo_window():
    alerts = [
        _alert("client_supheli_0000", "Davranışsal", -60),
        _alert("client_supheli_0001", "Davranışsal", 400),
        _alert("client_normal_0000", "Davranışsal", -1),
    ]
    correlations = [_corr("client_supheli_0000", -10), _corr("client_supheli_0000", 301)]

    card = ts.compute_scorecard(ts.client_profiles(3), alerts, correlations, DEMO_START, DEMO_END)

    assert card["supheli"]["behavioral"]== 0
    assert card["normal"]["false_alerts"] ==0
    assert card["correlations"] == {"total": 0, "supheli": 0, "yogun": 0, "normal": 0}


def test_scorecard_ignores_clients_that_are_not_part_of_the_demo():
    alerts = [_alert("client_supheli_0099", "Davranışsal", 60), _alert("baska_istemci", "Performans", 60)]

    card = ts.compute_scorecard(ts.client_profiles(3), alerts, [_corr("client_supheli_0099", 61)], DEMO_START, DEMO_END)

    assert card["supheli"]["behavioral"] == 0
    assert card["correlations"]["total"] == 0


def test_scorecard_parses_z_suffixed_timestamps():
    alert ={"alertId": "a", "clientId": "client_supheli_0000", "type": "Davranışsal", "createdAt": _at(10).replace("+00:00", "Z")}

    card = ts.compute_scorecard(ts.client_profiles(3), [alert], [], DEMO_START, DEMO_END)

    assert card["supheli"]["behavioral"] == 1
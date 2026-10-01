"""
OpenSight Trafik Simülatörü - en az 3 farklı davranış profili (normal, yoğun, şüpheli)
üretiyor, her istemci kendi profilinin hızıyla bağımsız istek atıyor, ground-truth
etiketleri ayrı bir loga yazılıyor. Hızlar env değişkenleriyle ayarlanıyor
(SIMULATOR_RATE_SCALE, SIMULATOR_*_RATE, SIMULATOR_TRAFFIC_ENABLED ...)

Cold start'ta normal ve yoğun birlikte trafik üretiyor (baseline bunlardan toplanıyor), şüpheli
analiz servisinin /status'u model_ready dönene kadar bekliyor.

yoğun sabit hızla değil sakin/patlama arasında gidiyor (SIMULATOR_YOGUN_BURST_*) - sabit yüksek hız
RollingZScoreDetector'ın 50'lik penceresinde bir süre sonra normal sayılır, patlama başlangıcı ise
pencere hâlâ sakinken geldiği için z-score'u güvenilir tetikliyor.

DemoController, dashboard'daki "Canlı demoyu başlat" butonuna hizmet ediyor (POST /demo/start,
GET /demo/status): API+analiz servisini uyandırıp SIMULATOR_DEMO_RATE_SCALE ile süreli bir
TrafficSimulator koşusu başlatıyor. Kötüye kullanım koruması (cooldown + günlük limit) Redis'te.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
from redis import Redis


class Profile(str, Enum):
    NORMAL = "normal"
    YOGUN = "yogun"     # yüksek istek oranı, normal endpoint dağılımı
    SUPHELI = "supheli" # dar endpoint çeşitliliği + anormal istek oranı


ENDPOINTS = ["/v1/accounts", "/v1/payments"]

# ölçek 1.0'da istemci başına saniyedeki istek aralıkları (env ile değiştirilebiliyor)
DEFAULT_RATE_RANGES = {
    Profile.NORMAL: (0.2, 1.0),
    Profile.YOGUN: (5.0, 12.0),
    Profile.SUPHELI: (8.0, 20.0),
}
DEFAULT_RATE_SCALE = 0.1
MIN_RATE = 0.001  # ölçek çok küçükse bile hız sıfıra inmesin

# şüpheli, model_ready dönene kadar bekliyor; servis cevap vermezse bu süre dolunca yine başlıyor
DEFAULT_READY_TIMEOUT_SECONDS = 900.0
DEFAULT_READY_POLL_SECONDS = 2.0

# yoğun profilin patlama dönemindeki hız aralığı (ölçek 1.0'da, calm aralığıyla aynı birim)
DEFAULT_YOGUN_BURST_RATE_RANGE = (20.0, 40.0)
# patlama/sakin süresi gerçek saniye - SIMULATOR_RATE_SCALE bunu etkilemiyor, o sadece hacmi düşürüyor
DEFAULT_YOGUN_BURST_DURATION_RANGE = (20.0, 40.0)
DEFAULT_YOGUN_BURST_INTERVAL_RANGE = (120.0, 240.0)

# "canlı demoyu başlat" ayarları - 0.1 kasıtlı: mock API'yi bükmek yerine değerlendirdiğimiz ölçekle eşitliyoruz
DEFAULT_DEMO_RATE_SCALE = 0.1
DEFAULT_DEMO_DURATION_SECONDS = 300.0
DEFAULT_DEMO_MAX_DURATION_SECONDS = 300.0
DEFAULT_DEMO_COOLDOWN_SECONDS = 600.0
DEFAULT_DEMO_DAILY_LIMIT = 3
# ölçüm: demo başına ~22K Redis komutu (pipeline MULTI/EXEC de sayılıyor) - 20/ay güvenli, 35 taşardı
DEFAULT_DEMO_MONTHLY_LIMIT = 20
DEFAULT_DEMO_WAKE_TIMEOUT_SECONDS = 90.0
DEFAULT_DEMO_KEEPALIVE_INTERVAL_SECONDS = 300.0

# cold_start.py'deki BASELINE_SCALE_KEY/SIMULATOR_ACTIVE_SCALE_KEY ile aynı olmalı
BASELINE_SCALE_KEY = "behavioral:baseline:scale"
SIMULATOR_ACTIVE_SCALE_KEY = "simulator:active_scale"


def demo_rate_scale() -> float:
    return float(os.environ.get("SIMULATOR_DEMO_RATE_SCALE", str(DEFAULT_DEMO_RATE_SCALE)))


def demo_default_duration() -> float:
    return float(os.environ.get("SIMULATOR_DEMO_DEFAULT_SECONDS", str(DEFAULT_DEMO_DURATION_SECONDS)))


def demo_max_duration() -> float:
    return float(os.environ.get("SIMULATOR_DEMO_MAX_SECONDS", str(DEFAULT_DEMO_MAX_DURATION_SECONDS)))


def demo_cooldown_seconds() -> float:
    return float(os.environ.get("SIMULATOR_DEMO_COOLDOWN_SECONDS", str(DEFAULT_DEMO_COOLDOWN_SECONDS)))


def demo_monthly_limit() -> int:
    return int(os.environ.get("SIMULATOR_DEMO_MONTHLY_LIMIT", str(DEFAULT_DEMO_MONTHLY_LIMIT)))


def demo_daily_limit() -> int:
    return int(os.environ.get("SIMULATOR_DEMO_DAILY_LIMIT", str(DEFAULT_DEMO_DAILY_LIMIT)))


def demo_wake_timeout() -> float:
    return float(os.environ.get("SIMULATOR_DEMO_WAKE_TIMEOUT", str(DEFAULT_DEMO_WAKE_TIMEOUT_SECONDS)))


def demo_keepalive_interval() -> float:
    return float(os.environ.get("SIMULATOR_DEMO_KEEPALIVE_INTERVAL", str(DEFAULT_DEMO_KEEPALIVE_INTERVAL_SECONDS)))


def record_active_scale(redis_client: Redis, scale: float) -> None:
    """trafiğe her başladığında çağrılıyor - analiz servisi baseline'ı fit ederken bunu okuyor"""
    try:
        redis_client.set(SIMULATOR_ACTIVE_SCALE_KEY, str(scale))
    except Exception as exc:
        print(f"[simulator] aktif ölçek Redis'e yazılamadı: {exc}", flush=True)


@dataclass
class GroundTruthRecord:
    client_id: str
    timestamp: str
    profile: str


@dataclass
class BurstEvent:
    client_id: str
    timestamp: str
    phase: str  # "patlama" | "sakin"


def make_client_id(profile: Profile, index: int) -> str:
    return f"client_{profile.value}_{index:04d}"


def env_flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() not in ("0", "false", "no", "off")


def parse_rate_range(text: str) -> tuple[float, float]:
    """'5-12' gibi bir aralığı (5.0, 12.0) yapıyor"""
    low_text, _, high_text = text.partition("-")
    low, high = float(low_text), float(high_text)
    if low <= 0 or high < low:
        raise ValueError(f"geçersiz hız aralığı: {text!r} ('min-max' olmalı, 0 < min <= max)")
    return low, high


_scale_override: float | None = None  # demo çalışırken SIMULATOR_RATE_SCALE yerine bunu kullan


def set_scale_override(scale: float | None) -> None:
    global _scale_override
    _scale_override = scale


def rate_scale() -> float:
    if _scale_override is not None:
        return _scale_override
    scale = float(os.environ.get("SIMULATOR_RATE_SCALE", DEFAULT_RATE_SCALE))
    if scale <= 0:
        raise ValueError("SIMULATOR_RATE_SCALE 0'dan büyük olmalı")
    return scale


def rate_range_for(profile: Profile) -> tuple[float, float]:
    text = os.environ.get(f"SIMULATOR_{profile.name}_RATE")
    return parse_rate_range(text) if text else DEFAULT_RATE_RANGES[profile]


def request_rate_for(profile: Profile) -> float:
    """istemcinin saniyedeki istek hızını (ölçek uygulanmış) profil aralığından seçiyor"""
    low, high = rate_range_for(profile)
    return max(random.uniform(low, high) * rate_scale(), MIN_RATE)


def burst_rate_range() -> tuple[float, float]:
    text = os.environ.get("SIMULATOR_YOGUN_BURST_RATE")
    return parse_rate_range(text) if text else DEFAULT_YOGUN_BURST_RATE_RANGE


def burst_duration_range() -> tuple[float, float]:
    text = os.environ.get("SIMULATOR_YOGUN_BURST_DURATION")
    return parse_rate_range(text) if text else DEFAULT_YOGUN_BURST_DURATION_RANGE


def burst_interval_range() -> tuple[float, float]:
    text = os.environ.get("SIMULATOR_YOGUN_BURST_INTERVAL")
    return parse_rate_range(text) if text else DEFAULT_YOGUN_BURST_INTERVAL_RANGE


def pick_endpoint(profile: Profile) -> str:
    if profile is Profile.SUPHELI:
        # dar endpoint çeşitliliği: neredeyse hep aynı endpointe vuruyor
        return random.choices(ENDPOINTS, weights=[0.95, 0.05])[0]
    return random.choice(ENDPOINTS)


def constant_rate(rate: float) -> Callable[[], float]:
    """normal/şüpheli gibi sabit hızlı profiller için - her çağrıda aynı hızı döndürüyor"""
    return lambda: rate


class YogunBurstRateProvider:
    """yoğun profilin sakin<->patlama arasında salındığı hız sağlayıcısı - her çağrıldığında
    güncel hızı döndürüyor, faz değişince on_transition(in_burst) çağrılıyor"""

    def __init__(self, on_transition: Callable[[bool], None] | None = None) -> None:
        self._scale = rate_scale()
        self._calm_range = rate_range_for(Profile.YOGUN)
        self._burst_range = burst_rate_range()
        self._duration_range = burst_duration_range()
        self._interval_range = burst_interval_range()
        self._on_transition = on_transition
        self._in_burst = False
        self._current_rate = self._draw_calm()
        self._next_transition = time.monotonic() + random.uniform(*self._interval_range)

    def _draw_calm(self) -> float:
        return max(random.uniform(*self._calm_range) * self._scale, MIN_RATE)

    def _draw_burst(self) -> float:
        return max(random.uniform(*self._burst_range) * self._scale, MIN_RATE)

    def __call__(self) -> float:
        now = time.monotonic()
        if now >= self._next_transition:
            self._in_burst = not self._in_burst
            if self._in_burst:
                self._current_rate = self._draw_burst()
                self._next_transition = now + random.uniform(*self._duration_range)
            else:
                self._current_rate = self._draw_calm()
                self._next_transition = now + random.uniform(*self._interval_range)
            if self._on_transition:
                self._on_transition(self._in_burst)
        return self._current_rate


class TrafficSimulator:
    def __init__(
        self,
        base_url: str,
        ground_truth_path: str,
        analysis_url: str = "http://localhost:8001",
        ready_timeout: float = DEFAULT_READY_TIMEOUT_SECONDS,
        ready_poll_seconds: float = DEFAULT_READY_POLL_SECONDS,
        burst_log_path: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.ground_truth_path = ground_truth_path
        self.burst_log_path = burst_log_path or (ground_truth_path + ".burst")
        self.analysis_url = analysis_url.rstrip("/")
        self.ready_timeout = ready_timeout
        self.ready_poll_seconds = ready_poll_seconds
        self._stop = threading.Event()
        self._suspicious_go = threading.Event()  # model hazır olunca (ya da timeout dolunca) set ediliyor
        self._log_lock = threading.Lock()  # thread'ler aynı dosyaya yazıyor, satırlar karışmasın

    def model_is_ready(self) -> bool:
        try:
            response = requests.get(f"{self.analysis_url}/status", timeout=3)
            return response.status_code == 200 and bool(response.json().get("model_ready"))
        except (requests.RequestException, ValueError):
            return False

    def _wait_for_model(self) -> None:
        """analiz servisi modeli eğitene kadar periyodik sorguluyor, sonra şüpheli trafiğe izin veriyor"""
        deadline = time.monotonic() + self.ready_timeout
        while not self._stop.is_set():
            if self.model_is_ready():
                print("[simulator] model hazır, şüpheli trafik başlıyor", flush=True)
                break
            if time.monotonic() >= deadline:
                print(
                    f"[simulator] model {self.ready_timeout:.0f}s içinde hazır olmadı, şüpheli trafik yine de başlıyor",
                    flush=True,
                )
                break
            self._stop.wait(self.ready_poll_seconds)
        self._suspicious_go.set()

    def send_request(self, client_id: str, endpoint: str) -> None:
        method = requests.post if "payments" in endpoint else requests.get
        try:
            method(f"{self.base_url}{endpoint}", headers={"X-Client-Id": client_id}, timeout=2)
        except requests.RequestException as exc:
            print(f"[simulator] Mock API'ye ulaşılamadı: {exc}", flush=True)

    def log_ground_truth(self, client_id: str, profile: Profile) -> None:
        record = GroundTruthRecord(client_id, datetime.now(timezone.utc).isoformat(), profile.value)
        with self._log_lock:
            with open(self.ground_truth_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

    def log_burst_event(self, client_id: str, in_burst: bool) -> None:
        record = BurstEvent(client_id, datetime.now(timezone.utc).isoformat(), "patlama" if in_burst else "sakin")
        with self._log_lock:
            with open(self.burst_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

    def _client_loop(self, client_id: str, profile: Profile, rate_fn: Callable[[], float]) -> None:
        """tek bir istemci: kendi hızıyla (poisson aralıklarla) istek atıyor, diğerlerini beklemiyor.
        rate_fn güncel hızı döndürüyor - sabit profillerde hep aynı, yoğunda faza göre değişiyor"""
        if profile is Profile.SUPHELI:
            self._suspicious_go.wait()
        next_time = time.monotonic() + random.expovariate(rate_fn())
        while not self._stop.is_set():
            self._stop.wait(max(0.0, next_time - time.monotonic()))
            if self._stop.is_set():
                break
            endpoint = pick_endpoint(profile)
            print(f"[simulator] {client_id} -> {endpoint} ({profile.value})", flush=True)
            self.send_request(client_id, endpoint)
            self.log_ground_truth(client_id, profile)
            # istek yavaşladıysa geride kalınan zamanı yığıp toplu istek atmıyor
            next_time = max(next_time + random.expovariate(rate_fn()), time.monotonic())

    def run(self, n_clients_per_profile: int = 3) -> None:
        """her istemci için bir thread başlatıyor ve hemen dönüyor (thread'ler daemon)"""
        print(
            f"[simulator] başlıyor -> {self.base_url} (şüpheli, {self.analysis_url}/status model_ready "
            f"dönene kadar bekliyor, en fazla {self.ready_timeout:.0f}s; hız ölçeği: {rate_scale()}, "
            f"profil başına {n_clients_per_profile} istemci)",
            flush=True,
        )
        threading.Thread(target=self._wait_for_model, daemon=True).start()
        for profile in Profile:
            for i in range(n_clients_per_profile):
                client_id = make_client_id(profile, i)
                rate_fn = (
                    YogunBurstRateProvider(on_transition=lambda in_burst, cid=client_id: self.log_burst_event(cid, in_burst))
                    if profile is Profile.YOGUN
                    else constant_rate(request_rate_for(profile))
                )
                print(f"[simulator] {client_id}: ~{rate_fn() * 60:.1f} istek/dk", flush=True)
                threading.Thread(target=self._client_loop, args=(client_id, profile, rate_fn), daemon=True).start()

    def stop(self) -> None:
        self._stop.set()
        self._suspicious_go.set()


class DemoQuota:
    """kötüye kullanım koruması - Render'da process her uykuya geçişte sıfırlandığı için Redis'te"""

    LAST_STARTED_KEY = "demo:last_started_at"
    COUNT_KEY_PREFIX = "demo:count:"
    MONTH_COUNT_KEY_PREFIX = "demo:count:month:"

    def __init__(self, redis_client: Redis, cooldown_seconds: float, daily_limit: int, monthly_limit: int):
        self.redis = redis_client
        self.cooldown_seconds = cooldown_seconds
        self.daily_limit = daily_limit
        self.monthly_limit = monthly_limit

    def _day_key(self) -> str:
        return self.COUNT_KEY_PREFIX + datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _month_key(self) -> str:
        return self.MONTH_COUNT_KEY_PREFIX + datetime.now(timezone.utc).strftime("%Y-%m")

    def check(self) -> tuple[bool, str | None]:
        last = self.redis.get(self.LAST_STARTED_KEY)
        if last is not None:
            elapsed = time.time() - float(last)
            if elapsed < self.cooldown_seconds:
                wait = self.cooldown_seconds - elapsed
                return False, f"çok yakın zamanda bir demo çalıştı, {wait:.0f}s sonra tekrar deneyin"

        daily_count = int(self.redis.get(self._day_key()) or 0)
        if daily_count >= self.daily_limit:
            return False, f"bugünkü demo sınırına ({self.daily_limit}) ulaşıldı, yarın tekrar deneyin"

        monthly_count = int(self.redis.get(self._month_key()) or 0)
        if monthly_count >= self.monthly_limit:
            return False, f"bu ayın demo hakkı doldu (aylık sınır: {self.monthly_limit}), gelecek ay tekrar deneyin"

        return True, None

    def record_start(self) -> None:
        pipe = self.redis.pipeline()
        pipe.set(self.LAST_STARTED_KEY, str(time.time()))
        pipe.incr(self._day_key())
        pipe.expire(self._day_key(), 2 * 24 * 3600)
        pipe.incr(self._month_key())
        pipe.expire(self._month_key(), 40 * 24 * 3600)  # ay anahtarı kendinden tarihli, uzun TTL sadece temizlik için
        pipe.execute()


class DemoController:
    """dashboard'daki "Canlı demoyu başlat" butonunun sunucu tarafı - tek seferde tek demo,
    aşamalar: boşta -> uyanıyor -> model_hazirlaniyor -> calisiyor -> bitti"""

    def __init__(
        self,
        redis_client: Redis,
        base_url: str,
        analysis_url: str,
        quota: DemoQuota,
        clients_per_profile: int = 3,
    ):
        self.redis = redis_client
        self.base_url = base_url.rstrip("/")
        self.analysis_url = analysis_url.rstrip("/")
        self.quota = quota
        self.clients_per_profile = clients_per_profile
        self._lock = threading.Lock()
        self._state = "bosta"
        self._sim: TrafficSimulator | None = None
        self._started_at: float | None = None
        self._duration_seconds = 0.0
        self._error: str | None = None

    def status(self) -> dict:
        with self._lock:
            remaining = None
            if self._state == "calisiyor" and self._started_at is not None:
                remaining = max(0.0, self._duration_seconds - (time.monotonic() - self._started_at))
            return {
                "state": self._state,
                "remaining_seconds": remaining,
                "duration_seconds": self._duration_seconds if self._state == "calisiyor" else None,
                "error": self._error,
            }

    def _scale_mismatch(self) -> str | None:
        baseline_scale_raw = self.redis.get(BASELINE_SCALE_KEY)
        if baseline_scale_raw is None:
            return None  # henüz baseline yok, karşılaştırılacak bir şey yok
        baseline_scale = float(baseline_scale_raw)
        scale = demo_rate_scale()
        if abs(baseline_scale - scale) > 1e-9:
            return (
                f"baseline {baseline_scale} ölçeğinde toplanmış ama demo {scale} kullanıyor - "
                "istek_orani mutlak olduğundan ikisi eşleşmeli, önce baseline'ı bu ölçekte yeniden topla"
            )
        return None

    def start(self, duration_seconds: float | None) -> tuple[bool, str | None]:
        with self._lock:
            if self._state in ("uyaniyor", "model_hazirlaniyor", "calisiyor"):
                return False, "zaten çalışıyor"
            ok, reason = self.quota.check()
            if not ok:
                return False, reason
            mismatch = self._scale_mismatch()
            if mismatch:
                return False, mismatch
            self._state = "uyaniyor"
            self._error = None

        duration = min(max(duration_seconds or demo_default_duration(), 60.0), demo_max_duration())
        threading.Thread(target=self._run, args=(duration,), daemon=True).start()
        return True, None

    def _ping_once(self, base_url: str) -> bool:
        try:
            return requests.get(f"{base_url}/health", timeout=5).status_code == 200
        except requests.RequestException:
            return False

    def _wait_awake(self, base_url: str, deadline: float) -> bool:
        while time.monotonic() < deadline:
            if self._ping_once(base_url):
                return True
            time.sleep(2.0)
        return self._ping_once(base_url)

    def _run(self, duration: float) -> None:
        # ikisini de paralel uyandır - biri diğerini bekleyip zaman kaybetmesin
        threading.Thread(target=self._ping_once, args=(self.base_url,), daemon=True).start()
        threading.Thread(target=self._ping_once, args=(self.analysis_url,), daemon=True).start()

        deadline = time.monotonic() + demo_wake_timeout()
        api_awake = self._wait_awake(self.base_url, deadline)
        analysis_awake = self._wait_awake(self.analysis_url, deadline)
        if not (api_awake and analysis_awake):
            with self._lock:
                self._state = "bosta"
                self._error = "servisler uyanmadı, tekrar deneyin"
            return

        with self._lock:
            self._state = "model_hazirlaniyor"

        scale = demo_rate_scale()
        set_scale_override(scale)
        record_active_scale(self.redis, scale)
        sim = TrafficSimulator(
            self.base_url, ground_truth_path=os.devnull, analysis_url=self.analysis_url,
            ready_timeout=demo_wake_timeout() * 10,  # cold start uzun sürebilir, sabırlı ol
        )
        with self._lock:
            self._sim = sim
        sim.run(self.clients_per_profile)
        sim._suspicious_go.wait()  # model hazır oldu ya da ready_timeout doldu

        with self._lock:
            self._state = "calisiyor"
            self._started_at = time.monotonic()
            self._duration_seconds = duration
        self.quota.record_start()

        keepalive_stop = threading.Event()
        threading.Thread(target=self._keep_awake_loop, args=(keepalive_stop,), daemon=True).start()

        sim._stop.wait(duration)
        sim.stop()
        keepalive_stop.set()

        with self._lock:
            self._state = "bitti"
            self._sim = None

    def _keep_awake_loop(self, stop_event: threading.Event) -> None:
        """demo çalışırken API + analiz servisini uyanık tutuyor (simülatör kendi /demo/status'uyla uyanıyor)"""
        interval = demo_keepalive_interval()
        while not stop_event.wait(interval):
            self._ping_once(self.base_url)
            self._ping_once(self.analysis_url)


class HealthCheckHandler(BaseHTTPRequestHandler):
    """/, /health sabit yanıt; /demo/status, /demo/start server.demo_controller'a gidiyor.
    Tarayıcıdan çağrıldığı için CORS + OPTIONS burada elle ekleniyor"""

    def _cors_origin(self) -> str:
        return os.environ.get("CORS_ORIGIN", "http://localhost:5173")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", self._cors_origin())
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", self._cors_origin())
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        if self.path in ("/", "/health"):
            self._send_json(200, {"status": "healthy"})
        elif self.path == "/demo/status":
            self._send_json(200, self.server.demo_controller.status())
        else:
            self._send_json(404, {"error": "bulunamadı"})

    def do_POST(self) -> None:
        if self.path != "/demo/start":
            self._send_json(404, {"error": "bulunamadı"})
            return

        length = int(self.headers.get("Content-Length") or 0)
        duration_seconds = None
        if length > 0:
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
                duration_seconds = payload.get("duration_seconds")
            except (ValueError, json.JSONDecodeError):
                pass

        ok, reason = self.server.demo_controller.start(duration_seconds)
        if ok:
            self._send_json(200, self.server.demo_controller.status())
        else:
            self._send_json(409, {"error": reason})

    def log_message(self, format: str, *args) -> None:
        pass


def schedule_shutdown(duration_seconds: float, sim: TrafficSimulator | None, server: HTTPServer) -> None:
    """duration_seconds sonra sim'i durdurup health sunucusunu kapatıyor - <=0 ise hiçbir şey yapmıyor"""
    if duration_seconds <= 0:
        return

    def _shutdown() -> None:
        time.sleep(duration_seconds)
        print(f"[simulator] süre doldu ({duration_seconds:.0f}s), kapanıyor", flush=True)
        if sim is not None:
            sim.stop()
        server.shutdown()

    threading.Thread(target=_shutdown, daemon=True).start()


def build_redis_client() -> Redis:
    """analiz servisiyle aynı env var kuralları (REDIS_URL varsa Upstash gibi TLS URL'i, yoksa host/port)"""
    redis_url = os.environ.get("REDIS_URL", "")
    if redis_url:
        return Redis.from_url(redis_url, decode_responses=True)
    return Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", "6379")),
        decode_responses=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenSight trafik simülatörü")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("OPENSIGHT_API_URL", "http://localhost:8080"),
    )
    parser.add_argument("--ground-truth-path", default="ground_truth.log")
    parser.add_argument(
        "--analysis-url",
        default=os.environ.get("OPENSIGHT_ANALYSIS_URL", "http://localhost:8001"),
    )
    parser.add_argument(
        "--ready-timeout",
        type=float,
        default=float(os.environ.get("SIMULATOR_READY_TIMEOUT", str(DEFAULT_READY_TIMEOUT_SECONDS))),
    )
    parser.add_argument(
        "--clients-per-profile", type=int, default=int(os.environ.get("SIMULATOR_CLIENTS_PER_PROFILE", "3"))
    )
    parser.add_argument(
        # <=0 sınırsız (Render varsayılanı), değerlendirme koşularında set ediliyor
        "--duration-seconds",
        type=float,
        default=float(os.environ.get("SIMULATOR_DURATION_SECONDS", "0")),
    )
    args = parser.parse_args()

    redis_client = build_redis_client()

    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.demo_controller = DemoController(
        redis_client,
        args.base_url,
        args.analysis_url,
        DemoQuota(redis_client, demo_cooldown_seconds(), demo_daily_limit(), demo_monthly_limit()),
        clients_per_profile=args.clients_per_profile,
    )

    # kapalıyken yalnızca health sunucusu çalışıyor - uyanık kalmak artık demo butonuna bağlı, 7/24 keep-alive yok
    sim = None
    if env_flag("SIMULATOR_TRAFFIC_ENABLED", True):
        record_active_scale(redis_client, rate_scale())
        sim = TrafficSimulator(
            args.base_url,
            args.ground_truth_path,
            analysis_url=args.analysis_url,
            ready_timeout=args.ready_timeout,
            ready_poll_seconds=float(os.environ.get("SIMULATOR_READY_POLL_SECONDS", str(DEFAULT_READY_POLL_SECONDS))),
        )
        sim.run(args.clients_per_profile)
    else:
        print("[simulator] SIMULATOR_TRAFFIC_ENABLED=false, trafik yalnızca demo butonuyla başlıyor", flush=True)

    schedule_shutdown(args.duration_seconds, sim, server)

    print(f"[simulator] health check sunucusu -> 0.0.0.0:{port}", flush=True)
    server.serve_forever()
    print("[simulator] kapandı", flush=True)


if __name__ == "__main__":
    main()

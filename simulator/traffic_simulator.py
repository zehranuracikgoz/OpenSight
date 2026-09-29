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


def rate_scale() -> float:
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


class KeepAliveService:
    """Render gibi ücretsiz servislerde uyku moduna geçmemeleri için servisleri periyodik pingliyor"""

    def __init__(self, interval_seconds: float = 600.0):
        self.interval_seconds = interval_seconds
        api_url = os.environ.get("OPENSIGHT_API_URL", "http://localhost:8080").rstrip("/")
        analysis_url = os.environ.get("OPENSIGHT_ANALYSIS_URL", "http://localhost:8001").rstrip("/")
        simulator_url = os.environ.get("OPENSIGHT_SIMULATOR_URL", "http://localhost:10000").rstrip("/")
        self.targets = {
            "opensight-api": f"{api_url}/health",
            "opensight-analysis": f"{analysis_url}/health",
            "opensight-simulator": f"{simulator_url}/health",
        }

    def _ping(self, name: str, url: str) -> None:
        try:
            response = requests.get(url, timeout=5)
            print(f"[keep-alive] pinged {name} -> {response.status_code}", flush=True)
        except requests.RequestException as exc:
            print(f"[keep-alive] {name} adresine ulaşılamadı: {exc}", flush=True)

    def run(self) -> None:
        while True:
            for name, url in self.targets.items():
                self._ping(name, url)
            time.sleep(self.interval_seconds)


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path in ("/", "/health"):
            body = json.dumps({"status": "healthy"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type" , "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        else:
            self.send_response(404)
            self.end_headers()

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

    keep_alive = KeepAliveService()
    keep_alive_thread = threading.Thread(target=keep_alive.run, daemon=True)
    keep_alive_thread.start()

    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)

    # kapalıyken yalnızca health sunucusu + keep-alive çalışıyor, mock API'ye ve RabbitMQ'ya hiç trafik gitmiyor
    sim = None
    if env_flag("SIMULATOR_TRAFFIC_ENABLED", True):
        sim = TrafficSimulator(
            args.base_url,
            args.ground_truth_path,
            analysis_url=args.analysis_url,
            ready_timeout=args.ready_timeout,
            ready_poll_seconds=float(os.environ.get("SIMULATOR_READY_POLL_SECONDS", str(DEFAULT_READY_POLL_SECONDS))),
        )
        sim.run(args.clients_per_profile)
    else:
        print("[simulator] SIMULATOR_TRAFFIC_ENABLED=false, trafik üretilmiyor (yalnızca health + keep-alive)", flush=True)

    schedule_shutdown(args.duration_seconds, sim, server)

    print(f"[simulator] health check sunucusu -> 0.0.0.0:{port}", flush=True)
    server.serve_forever()
    print("[simulator] kapandı", flush=True)


if __name__ == "__main__":
    main()

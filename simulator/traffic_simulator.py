"""
OpenSight Trafik Simülatörü - en az 3 farklı davranış profili (normal, yoğun, şüpheli)
üretiyor, ground-truth etiketleri ayrı bir loga yazılıyor, Mock API'ye gönderilmiyor
"""
from __future__ import annotations

import argparse
import json
import os
import random
import threading
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Iterator

import requests


class Profile(str, Enum):
    NORMAL = "normal"
    YOGUN = "yogun"     # yüksek istek oranı, normal endpoint dağılımı
    SUPHELI = "supheli" # dar endpoint çeşitliliği + anormal istek oranı


ENDPOINTS = ["/v1/accounts", "/v1/payments"]


@dataclass
class GroundTruthRecord:
    client_id: str
    timestamp: str
    profile: str


def make_client_id(profile: Profile, index: int) -> str:
    return f"client_{profile.value}_{index:04d}"


def request_rate_for(profile: Profile) -> float:
    """saniyede kaç istek gönderileceğini belirliyor (client başına)"""
    if profile is Profile.NORMAL:
        return random.uniform(0.2, 1.0)
    if profile is Profile.YOGUN:
        return random.uniform(5.0, 12.0)
    return random.uniform(8.0, 20.0)  # supheli: yüksek + tekdüze endpoint


def pick_endpoint(profile: Profile) -> str:
    if profile is Profile.SUPHELI:
        # dar endpoint çeşitliliği: neredeyse hep aynı endpointe vuruyor
        return random.choices(ENDPOINTS, weights=[0.95, 0.05])[0]
    return random.choice(ENDPOINTS)


class TrafficSimulator:
    def __init__(self, base_url: str, ground_truth_path: str, cold_start_seconds: int = 90):
        self.base_url = base_url.rstrip("/")
        self.ground_truth_path = ground_truth_path
        self.cold_start_seconds = cold_start_seconds
        self.start_time = time.monotonic()
        self.session = requests.Session()

    def _in_cold_start(self) -> bool:
        """ilk 1-2 dakika yalnızca 'normal' profil üretiliyor (cold start)"""
        return (time.monotonic() - self.start_time) < self.cold_start_seconds

    def _active_profiles(self) -> list[Profile]:
        if self._in_cold_start():
            return [Profile.NORMAL]
        return [Profile.NORMAL, Profile.YOGUN, Profile.SUPHELI]

    def generate(self, n_clients_per_profile: int = 3) -> Iterator[tuple[str, Profile, str, float]]:
        """her tickte aktif profillerden istemciler için (client_id, profile, endpoint, latency_hint) üretiyor"""
        while True:
            for profile in self._active_profiles():
                for i in range(n_clients_per_profile):
                    client_id = make_client_id(profile, i)
                    endpoint = pick_endpoint(profile)
                    rate = request_rate_for(profile)
                    yield client_id, profile, endpoint, rate
            time.sleep(1.0)

    def send_request(self, client_id: str, endpoint: str) -> None:
        method = requests.post if "payments" in endpoint else requests.get
        try:
            method(f"{self.base_url}{endpoint}", headers={"X-Client-Id": client_id}, timeout=2)
        except requests.RequestException as exc:
            print(f"[simulator] Mock API'ye ulaşılamadı: {exc}")

    def log_ground_truth(self, client_id: str, profile: Profile) -> None:
        record = GroundTruthRecord(client_id, datetime.now(timezone.utc).isoformat(), profile.value)
        with open(self.ground_truth_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

    def run(self, n_clients_per_profile: int = 3) -> None:
        print(f"[simulator] başlıyor -> {self.base_url} (cold start: {self.cold_start_seconds}s)", flush=True)
        for client_id, profile, endpoint, rate in self.generate(n_clients_per_profile):
            print(f"[simulator] {client_id} -> {endpoint} ({profile.value})", flush=True)
            self.send_request(client_id, endpoint)
            self.log_ground_truth(client_id, profile)
            time.sleep(1.0 / max(rate, 0.1))


class KeepAliveService:
    """render gibi ücretsiz servislerde uyku moduna geçmemeleri için servisleri periyodik pinglemek icinn"""

    def __init__(self, interval_seconds: float = 600.0):
        self.interval_seconds = interval_seconds
        api_url = os.environ.get("OPENSIGHT_API_URL", "http://localhost:8080").rstrip("/")
        analysis_url = os.environ.get("OPENSIGHT_ANALYSIS_URL", "http://localhost:8001").rstrip("/")
        simulator_url = os.environ.get("OPENSIGHT_SIMULATOR_URL", "http://localhost:10000").rstrip("/")
        self.targets = {
            "opensight-api": f"{api_url}/health",
            "opensight-analysis": f"{analysis_url}/health",
            "opensight-simulator":f"{simulator_url}/health",
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


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenSight trafik simülatörü")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("OPENSIGHT_API_URL", "http://localhost:8080"),
    )
    parser.add_argument("--ground-truth-path", default="ground_truth.log")
    parser.add_argument("--cold-start-seconds", type=int, default=90)
    parser.add_argument("--clients-per-profile", type=int, default=3)
    args = parser.parse_args()

    keep_alive = KeepAliveService()
    keep_alive_thread = threading.Thread(target=keep_alive.run, daemon=True)
    keep_alive_thread.start()

    sim = TrafficSimulator(args.base_url, args.ground_truth_path, args.cold_start_seconds)
    sim_thread = threading.Thread(target=sim.run, args=(args.clients_per_profile,), daemon=True)
    sim_thread.start()

    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"[simulator] health check sunucusu -> 0.0.0.0:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
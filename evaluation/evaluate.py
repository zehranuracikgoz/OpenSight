"""
OpenSight değerlendirme betiği - simülatörün ground truth logunu (hangi istemci hangi profilden,
yoğun'un ne zaman patlamada olduğu) API'den çekilen alarm ve korelasyon olaylarıyla karşılaştırıp
precision/recall/F1 üretiyor.

Eşleştirme kuralları:
- Birim: istemci + zaman penceresi (varsayılan 300s, --window-seconds ile ayarlanabilir, alarm
  cooldown'uyla aynı süre). Bir istemcinin pencereleri, o istemcinin [eval_start, eval_end]
  aralığındaki İLK ground truth olayından başlayıp window_seconds aralıklarla ilerliyor. Sadece o
  istemcinin en az 1 istek ürettiği pencereler değerlendiriliyor - trafik yoksa alarm da çıkamaz,
  boş pencereyi "doğru negatif" saymak metrikleri anlamsız şişirir.
- eval_start: analiz servisinin /status'undaki last_trained_at (model bu andan önce hiç davranışsal
  tespit yapmıyordu, performans/korelasyon da bu ölçüme dahil edilmiyor - "değerlendirme yalnızca
  model hazır olduktan sonraki süreyi kapsasın" kararı gereği).
- Tahmin pozitif: o pencerede o istemciye, o türde (Performans/Davranışsal) en az 1 alarm yazılmışsa.
- Davranışsal gerçek pozitif: istemci profili şüpheli olan HER pencere (şüpheli sürekli anomalik
  davranıyor, ayrı bir "aktif" alt-dönemi yok).
- Performans (katı) gerçek pozitif: istemci profili yoğun VE pencere en az bir patlama aralığıyla
  kesişiyor (yoğun'un sakin döneminde gerçek bir performans sorunu yok).
- Performans (geniş) gerçek pozitif: katı + istemci profili şüpheli olan HER pencere (şüpheli de
  sürekli yüksek yük ürettiği için gerçek bir performans sinyali sayılıyor).
- Korelasyon: CorrelationEvent listesinin tamamı değerlendiriliyor (pencereleme yok). "şüpheli oranı"
  precision olarak raporlanıyor: şüpheliye ait korelasyon / toplam korelasyon. Ayrıca her korelasyonun
  performans ve davranışsal alarmının CreatedAt farkının --correlation-window-seconds (varsayılan
  1800, CorrelationEngine ile aynı) içinde olduğu doğrulanıyor.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import requests

DEFAULT_WINDOW_SECONDS = 300.0
DEFAULT_CORRELATION_WINDOW_SECONDS = 1800.0


def _parse_ts(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def load_jsonl(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def fetch_status(analysis_url: str) -> dict:
    response = requests.get(f"{analysis_url.rstrip('/')}/status", timeout=5)
    response.raise_for_status()
    return response.json()


def fetch_all_alerts(api_url: str, page_size: int = 500) -> list[dict]:
    items: list[dict] = []
    skip = 0
    while True:
        response = requests.get(
            f"{api_url.rstrip('/')}/api/alerts", params={"take": page_size, "skip": skip}, timeout=15
        )
        response.raise_for_status()
        data = response.json()
        items.extend(data["items"])
        skip += page_size
        if skip >= data["totalCount"] or not data["items"]:
            break
    return items


def fetch_correlations(api_url: str) -> list[dict]:
    response = requests.get(f"{api_url.rstrip('/')}/api/alerts/correlations", timeout=15)
    response.raise_for_status()
    return response.json()


def profile_of(client_id: str) -> str:
    for profile in ("normal", "yogun", "supheli"):
        if f"_{profile}_" in client_id:
            return profile
    return "bilinmeyen"


def reconstruct_burst_intervals(burst_events: list[dict], run_end: datetime) -> dict[str, list[tuple[datetime, datetime]]]:
    """istemci -> [(patlama_baslangic, patlama_bitis), ...] - açık kalan bir patlama run_end'e kadar sürüyor kabul ediliyor"""
    by_client: dict[str, list[dict]] = {}
    for ev in burst_events:
        by_client.setdefault(ev["client_id"], []).append(ev)

    intervals: dict[str, list[tuple[datetime, datetime]]] = {}
    for client_id, events in by_client.items():
        events = sorted(events, key=lambda e: e["timestamp"])
        spans: list[tuple[datetime, datetime]] = []
        start: datetime | None = None
        for ev in events:
            ts = _parse_ts(ev["timestamp"])
            if ev["phase"] == "patlama":
                start = ts
            elif ev["phase"] == "sakin" and start is not None:
                spans.append((start, ts))
                start = None
        if start is not None:
            spans.append((start, run_end))
        intervals[client_id] = spans
    return intervals


def build_windows(
    ground_truth: list[dict], eval_start: datetime, eval_end: datetime, window_seconds: float
) -> dict[str, list[tuple[datetime, datetime]]]:
    """istemci -> [(pencere_baslangic, pencere_bitis), ...] - sadece o istemcinin en az 1 olay
    ürettiği pencereler; eval_start/eval_end dışındaki olaylar hesaba katılmıyor"""
    by_client: dict[str, list[datetime]] = {}
    for rec in ground_truth:
        ts = _parse_ts(rec["timestamp"])
        if eval_start <= ts <= eval_end:
            by_client.setdefault(rec["client_id"], []).append(ts)

    step = timedelta(seconds=window_seconds)
    windows: dict[str, list[tuple[datetime, datetime]]] = {}
    for client_id, timestamps in by_client.items():
        timestamps.sort()
        first = timestamps[0]
        active: list[tuple[datetime, datetime]] = []
        w_start = first
        idx = 0
        n = len(timestamps)
        while w_start <= timestamps[-1]:
            w_end = w_start + step
            has_event = False
            while idx < n and timestamps[idx] < w_end:
                if timestamps[idx] >= w_start:
                    has_event = True
                idx += 1
            if has_event:
                active.append((w_start, w_end))
            w_start = w_end
        windows[client_id] = active
    return windows


def alert_timestamps_by_client_type(alerts: list[dict]) -> dict[tuple[str, str], list[datetime]]:
    index: dict[tuple[str, str], list[datetime]] = {}
    for a in alerts:
        key = (a["clientId"], a["type"])
        index.setdefault(key, []).append(_parse_ts(a["createdAt"]))
    return index


def has_alert_in_window(
    alert_index: dict[tuple[str, str], list[datetime]], client_id: str, alert_type: str, window: tuple[datetime, datetime]
) -> bool:
    w_start, w_end = window
    return any(w_start <= ts < w_end for ts in alert_index.get((client_id, alert_type), []))


def window_overlaps_burst(window: tuple[datetime, datetime], bursts: list[tuple[datetime, datetime]]) -> bool:
    w_start, w_end = window
    return any(w_start < b_end and b_start < w_end for b_start, b_end in bursts)


@dataclass
class Confusion:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0

    def add(self, predicted: bool, actual: bool) -> None:
        if predicted and actual:
            self.tp += 1
        elif predicted and not actual:
            self.fp += 1
        elif not predicted and actual:
            self.fn += 1
        else:
            self.tn += 1

    def as_dict(self) -> dict:
        precision = self.tp / (self.tp + self.fp) if (self.tp + self.fp) else None
        recall = self.tp / (self.tp + self.fn) if (self.tp + self.fn) else None
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision is not None and recall is not None and (precision + recall) > 0
            else None
        )
        fpr = self.fp / (self.fp + self.tn) if (self.fp + self.tn) else None
        return {
            "tp": self.tp, "fp": self.fp, "fn": self.fn, "tn": self.tn,
            "precision": precision, "recall": recall, "f1": f1, "false_positive_rate": fpr,
        }


def evaluate_alert_type(
    windows_by_client: dict[str, list[tuple[datetime, datetime]]],
    alert_index: dict[tuple[str, str], list[datetime]],
    alert_type: str,
    label_fn,
) -> dict:
    """label_fn(client_id, window) -> bool (gerçek pozitif mi) - çağıran davranışsal/performans kuralını veriyor"""
    overall = Confusion()
    by_profile: dict[str, Confusion] = {}
    for client_id, windows in windows_by_client.items():
        profile = profile_of(client_id)
        by_profile.setdefault(profile, Confusion())
        for window in windows:
            predicted = has_alert_in_window(alert_index, client_id, alert_type, window)
            actual = label_fn(client_id, window)
            overall.add(predicted, actual)
            by_profile[profile].add(predicted, actual)

    return {
        "overall": overall.as_dict(),
        "by_profile": {profile: c.as_dict() for profile, c in by_profile.items()},
    }


def evaluate_correlations(
    correlations: list[dict], alerts_by_id: dict[str, dict], correlation_window_seconds: float
) -> dict:
    by_profile: dict[str, int] = {}
    window_violations: list[str] = []
    for corr in correlations:
        profile = profile_of(corr["clientId"])
        by_profile[profile] = by_profile.get(profile, 0) + 1

        perf = alerts_by_id.get(corr["performanceAlertId"])
        beh = alerts_by_id.get(corr["behavioralAlertId"])
        if perf is None or beh is None:
            window_violations.append(corr["correlationId"] + " (alarm bulunamadı)")
            continue
        diff = abs((_parse_ts(perf["createdAt"]) - _parse_ts(beh["createdAt"])).total_seconds())
        if diff > correlation_window_seconds:
            window_violations.append(f"{corr['correlationId']} (fark {diff:.0f}s > {correlation_window_seconds:.0f}s)")

    total = len(correlations)
    supheli = by_profile.get("supheli", 0)
    return {
        "total": total,
        "by_profile": by_profile,
        "supheli_precision": (supheli / total) if total else None,
        "window_violations": window_violations,
    }


def run_evaluation(
    ground_truth: list[dict],
    burst_events: list[dict],
    alerts: list[dict],
    correlations: list[dict],
    eval_start: datetime,
    window_seconds: float = DEFAULT_WINDOW_SECONDS,
    correlation_window_seconds: float = DEFAULT_CORRELATION_WINDOW_SECONDS,
) -> dict:
    if not ground_truth:
        raise ValueError("ground truth boş, değerlendirilecek bir şey yok")

    eval_end = max(_parse_ts(r["timestamp"]) for r in ground_truth)
    windows_by_client = build_windows(ground_truth, eval_start, eval_end, window_seconds)
    burst_intervals = reconstruct_burst_intervals(burst_events, eval_end)
    alert_index = alert_timestamps_by_client_type(alerts)
    alerts_by_id = {a["alertId"]: a for a in alerts}

    behavioral = evaluate_alert_type(
        windows_by_client, alert_index, "Davranışsal",
        label_fn=lambda client_id, window: profile_of(client_id) == "supheli",
    )

    def _perf_strict(client_id: str, window: tuple[datetime, datetime]) -> bool:
        return profile_of(client_id) == "yogun" and window_overlaps_burst(window, burst_intervals.get(client_id, []))

    def _perf_broad(client_id: str, window: tuple[datetime, datetime]) -> bool:
        return _perf_strict(client_id, window) or profile_of(client_id) == "supheli"

    performance_strict = evaluate_alert_type(windows_by_client, alert_index, "Performans", label_fn=_perf_strict)
    performance_broad = evaluate_alert_type(windows_by_client, alert_index, "Performans", label_fn=_perf_broad)
    correlation = evaluate_correlations(correlations, alerts_by_id, correlation_window_seconds)

    window_counts = {profile_of(cid): 0 for cid in windows_by_client}
    for cid, windows in windows_by_client.items():
        window_counts[profile_of(cid)] = window_counts.get(profile_of(cid), 0) + len(windows)

    return {
        "eval_start": eval_start.isoformat(),
        "eval_end": eval_end.isoformat(),
        "window_seconds": window_seconds,
        "correlation_window_seconds": correlation_window_seconds,
        "window_counts_by_profile": window_counts,
        "behavioral": behavioral,
        "performance_strict": performance_strict,
        "performance_broad": performance_broad,
        "correlation": correlation,
    }


def _fmt(x) -> str:
    return f"{x:.3f}" if isinstance(x, float) else str(x)


def render_markdown(result: dict) -> str:
    lines = [
        "# OpenSight Değerlendirme Sonucu",
        "",
        f"- Değerlendirme aralığı: {result['eval_start']} -> {result['eval_end']}",
        f"- Pencere: {result['window_seconds']:.0f}s, korelasyon penceresi: {result['correlation_window_seconds']:.0f}s",
        f"- Pencere sayısı (profil bazında): {result['window_counts_by_profile']}",
        "",
        "## Davranışsal (gerçek pozitif = şüpheli)",
        "",
        "| Kırılım | TP | FP | FN | TN | Precision | Recall | F1 | FPR |",
        "|---|---|---|---|---|---|---|---|---|",
    ]

    def _rows(section: dict) -> list[str]:
        rows = []
        o = section["overall"]
        rows.append(
            f"| genel | {o['tp']} | {o['fp']} | {o['fn']} | {o['tn']} | {_fmt(o['precision'])} | "
            f"{_fmt(o['recall'])} | {_fmt(o['f1'])} | {_fmt(o['false_positive_rate'])} |"
        )
        for profile, c in section["by_profile"].items():
            rows.append(
                f"| {profile} | {c['tp']} | {c['fp']} | {c['fn']} | {c['tn']} | {_fmt(c['precision'])} | "
                f"{_fmt(c['recall'])} | {_fmt(c['f1'])} | {_fmt(c['false_positive_rate'])} |"
            )
        return rows

    lines += _rows(result["behavioral"])
    lines += ["", "## Performans - katı (gerçek pozitif = yoğun + patlama)", "",
              "| Kırılım | TP | FP | FN | TN | Precision | Recall | F1 | FPR |", "|---|---|---|---|---|---|---|---|---|"]
    lines += _rows(result["performance_strict"])
    lines += ["", "## Performans - geniş (katı + şüpheli)", "",
              "| Kırılım | TP | FP | FN | TN | Precision | Recall | F1 | FPR |", "|---|---|---|---|---|---|---|---|---|"]
    lines += _rows(result["performance_broad"])

    corr = result["correlation"]
    lines += [
        "", "## Korelasyon", "",
        f"- Toplam: {corr['total']}",
        f"- Profil dağılımı: {corr['by_profile']}",
        f"- Şüpheli oranı (precision): {_fmt(corr['supheli_precision'])}",
        f"- Pencere ihlali: {len(corr['window_violations'])}" + (
            f" ({corr['window_violations'][:5]})" if corr["window_violations"] else ""
        ),
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows konsolunun varsayılan kod sayfası Türkçe karakterleri kaçırıyor

    parser = argparse.ArgumentParser(description="OpenSight değerlendirme betiği")
    parser.add_argument("--ground-truth-path", default="ground_truth.log")
    parser.add_argument("--burst-log-path", default=None)
    parser.add_argument("--api-url", default=os.environ.get("OPENSIGHT_API_URL", "http://localhost:8080"))
    parser.add_argument("--analysis-url", default=os.environ.get("OPENSIGHT_ANALYSIS_URL", "http://localhost:8001"))
    parser.add_argument("--window-seconds", type=float, default=DEFAULT_WINDOW_SECONDS)
    parser.add_argument("--correlation-window-seconds", type=float, default=DEFAULT_CORRELATION_WINDOW_SECONDS)
    parser.add_argument("--output-dir", default=str(Path(__file__).parent / "results"))
    args = parser.parse_args()

    burst_log_path = args.burst_log_path or (args.ground_truth_path + ".burst")

    status = fetch_status(args.analysis_url)
    if not status.get("last_trained_at"):
        raise SystemExit("model hiç eğitilmemiş (last_trained_at boş) - değerlendirilecek bir şey yok")
    eval_start = _parse_ts(status["last_trained_at"])

    ground_truth = load_jsonl(args.ground_truth_path)
    burst_events = load_jsonl(burst_log_path)
    alerts = fetch_all_alerts(args.api_url)
    correlations = fetch_correlations(args.api_url)

    result = run_evaluation(
        ground_truth, burst_events, alerts, correlations, eval_start,
        window_seconds=args.window_seconds, correlation_window_seconds=args.correlation_window_seconds,
    )

    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = Path(args.output_dir) / f"eval_{stamp}.json"
    md_path = Path(args.output_dir) / f"eval_{stamp}.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown = render_markdown(result)
    md_path.write_text(markdown, encoding="utf-8")

    print(markdown)
    print(f"\n[evaluate] JSON: {json_path}")
    print(f"[evaluate] Markdown: {md_path}")


if __name__ == "__main__":
    main()

"""
ExplanationGenerator: ham anomali skorlarını insan diline çeviren açıklamalar üretiyor -
veri yerel Ollama'da işleniyor, buluta gönderilmiyor; Ollama 3sn içinde yanıt vermezse
alarmın gerçek metriklerinden kurulan kural tabanlı açıklamaya düşüyor
"""
from __future__ import annotations

import httpx

OLLAMA_TIMEOUT_SECONDS = 3.0
FALLBACK_TEMPLATE = "{client_id} için {alert_type} tipinde anomali tespit edildi, risk seviyesi: {severity}"


def _compare_to_baseline(value: float, baseline: float | None) -> str:
    """değerin baseline medyanına oranı, baseline yoksa boş"""
    if baseline is None or baseline <= 0:
        return ""
    ratio = value / baseline
    if ratio >=1.2:
        times = f"{ratio:.1f}" if ratio < 10 else f"{ratio:.0f}"
        return f" (baseline medyanının ~{times} katı)"
    if ratio <= 0.8:
        return f" (baseline medyanının ~%{ratio * 100:.0f} düzeyinde)"
    return " (baseline medyanına yakın)"


def behavioral_clause(metrics: dict) -> str | None:
    """davranışsal alarmın üç feature'ını baseline'la karşılaştırıyor"""
    rate = metrics.get("istek_orani")
    if rate is None:
        return None
    baseline = metrics.get("baseline_median") or [None, None, None]

    parts = [f"istek oranı {rate:.2f} req/s{_compare_to_baseline(rate, baseline[0])}"]

    share = metrics.get("en_sik_endpoint_payi")
    if share is not None:
        top = metrics.get("top_endpoint")
        target = f"{top} endpoint'ine" if top else "tek bir endpoint'e"
        baseline_share = f" (baseline medyanı %{baseline[1]* 100:.0f})" if baseline[1] else""
        parts.append(f"istekler %{share * 100:.0f} oranında {target} gidiyor{baseline_share}")

    latency = metrics.get("ortalama_gecikme")
    if latency is not None:
        baseline_latency = f" (baseline medyanı {baseline[2]:.0f} ms)" if baseline[2] else ""
        parts.append(f"ortalama gecikme {latency:.0f} ms{baseline_latency}")

    return ", ".join(parts)


def performance_clause(metrics: dict) -> str | None:
    """gecikmeyi pencere ortalaması ve z-score ile anlatıyor"""
    latency = metrics.get("latency_ms")
    if latency is None:
        return None
    clause = f"gecikme {latency:.0f} ms"
    window_mean = metrics.get("window_mean")
    if window_mean is not None:
        count =metrics.get("sample_count")
        window = f"son {count} isteğin" if count else "pencerenin"
        clause += f"; {window} ortalaması {window_mean:.0f} ms"
    z_score = metrics.get("z_score")
    if z_score is not None:
        clause += f", z = {z_score:.1f}"
    return clause


def performance_summary(metrics: dict) -> str | None:
    """korelasyon cümlesi için kısa performans özeti"""
    latency = metrics.get("latency_ms")
    if latency is None:
        return None
    summary = f"gecikme {latency:.0f} ms"
    z_score = metrics.get("z_score")
    if z_score is not None:
        summary += f", z = {z_score:.1f}"
    return summary


class ExplanationGenerator:
    def __init__(self, ollama_url: str = "http://ollama:11434/api/generate", model: str = "llama3.1"):
        self.ollama_url = ollama_url
        self.model = model

    @property
    def enabled(self) -> bool:
        """OLLAMA_URL verilmediyse Ollama ya hiç istek atılmıyor, sadece şablon kullanılıyor"""
        return bool(self.ollama_url)

    def clause(self, alert_type: str, metrics: dict) -> str | None:
        """alarm türüne göre metrik cümlesi"""
        return behavioral_clause(metrics) if alert_type == "Davranışsal" else performance_clause(metrics)

    def fallback_template(self, client_id: str, alert_type: str, severity: str, metrics: dict | None = None) -> str:
        clause = self.clause(alert_type, metrics) if metrics else None
        if clause:
            return f"{client_id}: {clause}."
        return FALLBACK_TEMPLATE.format(client_id=client_id, alert_type=alert_type, severity=severity)

    def summary(self, alert_type: str, metrics: dict) -> str:
        """korelasyon cümlesi için özet, sadece performans alarmında dolu"""
        return (performance_summary(metrics) or "") if alert_type == "Performans" else ""

    def combined_explanation(self, performance_summary_text: str) -> str:
        """korelasyon cümlesi"""
        return f"davranışsal ve performans anomalisi aynı pencerede oluştu ({performance_summary_text})."

    def generate_explanation(
        self,
        client_id: str,
        alert_type: str,
        severity: str,
        metrics: dict,
    ) -> str:
        prompt = (
            f"Açık bankacılık API trafiğinde bir anomali tespit edildi.\n"
            f"İstemci: {client_id}\nAnomali türü: {alert_type}\nŞiddet: {severity}\n"
            f"Metrikler: {metrics}\n"
            f"Bu durumu güvenlik/operasyon ekibine 2 cümlede, teknik ama anlaşılır şekilde açıkla."
        )
        if not self.enabled:
            return self.fallback_template(client_id, alert_type, severity, metrics)
        try:
            with httpx.Client(timeout=OLLAMA_TIMEOUT_SECONDS) as client:
                response = client.post(
                    self.ollama_url,
                    json={"model": self.model, "prompt": prompt, "stream": False},
                )
                response.raise_for_status()
                data = response.json()
                text = data.get("response", "").strip()
                return text if text else self.fallback_template(client_id, alert_type, severity, metrics)
        except (httpx.TimeoutException, httpx.HTTPError, KeyError, ValueError):
            # timeout ya da herhangi bir hata ->sistem temel işlevselliğini kaybetmez
            return self.fallback_template(client_id, alert_type, severity, metrics)
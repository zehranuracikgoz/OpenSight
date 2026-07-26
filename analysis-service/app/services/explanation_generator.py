"""
ExplanationGenerator: ham anomali skorlarını insan diline çeviren açıklamalar üretiyor -
veri yerel Ollama'da işleniyr, buluta gönderilmiyor; Ollama 3sn içinde yanıt vermezse
kural tabanlı şablona düşüyor
"""
from __future__ import annotations

import httpx

OLLAMA_TIMEOUT_SECONDS = 3.0
FALLBACK_TEMPLATE = "{client_id} için {alert_type} tipinde anomali tespit edildi, risk seviyesi: {severity}"


class ExplanationGenerator:
    def __init__(self, ollama_url: str = "http://ollama:11434/api/generate", model: str = "llama3.1"):
        self.ollama_url = ollama_url
        self.model = model

    def fallback_template(self, client_id: str, alert_type: str, severity: str) -> str:
        return FALLBACK_TEMPLATE.format(client_id=client_id, alert_type=alert_type, severity=severity)

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
        try:
            with httpx.Client(timeout=OLLAMA_TIMEOUT_SECONDS) as client:
                response = client.post(
                    self.ollama_url,
                    json={"model": self.model, "prompt": prompt, "stream": False},
                )
                response.raise_for_status()
                data = response.json()
                text = data.get("response", "").strip()
                return text if text else self.fallback_template(client_id, alert_type, severity)
        except (httpx.TimeoutException, httpx.HTTPError, KeyError, ValueError):
            # timeout ya da herhangi bir hata ->sistem temel işlevselliğini kaybetmez
            return self.fallback_template(client_id, alert_type, severity)
"""
ExplanationGenerator'ın Ollama'ya doğru payload ile istek attığını, başarılı yanıtı
işlediğini, zaman aşımı/hata/boş yanıt durumunda kural tabanlı şablona düştüğünü
mock'lanmış httpx ile doğruluyor - gerçek bir Ollama sunucusu gerektirmiyor
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from app.services.explanation_generator import ExplanationGenerator


def _mock_client_returning(response: MagicMock) -> MagicMock:
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client  # with bloğu da aynı mock'u versin
    mock_client.post.return_value = response
    return mock_client


def test_generate_explanation_returns_ollama_response_on_success():
    generator = ExplanationGenerator(ollama_url="http://ollama:11434/api/generate", model="llama3.2:1b")
    response = MagicMock()
    response.json.return_value = {"response": "İstemci client_1 için performans anomalisi tespit edildi."}
    mock_client = _mock_client_returning(response)

    with patch("app.services.explanation_generator.httpx.Client", return_value=mock_client) as mock_client_cls:
        result = generator.generate_explanation("client_1", "Performans", "Yüksek", {"z_score": 4.5})

    assert result == "İstemci client_1 için performans anomalisi tespit edildi."
    # httpx.Client 3 sn timeout ile açılıyor
    mock_client_cls.assert_called_once_with(timeout=3.0)
    # post'a giden adres, model ve payload doğru mu
    args, kwargs = mock_client.post.call_args
    assert args[0] == "http://ollama:11434/api/generate"
    assert kwargs["json"]["model"] == "llama3.2:1b"
    assert kwargs["json"]["stream"] is False
    assert "client_1" in kwargs["json"]["prompt"]


def test_generate_explanation_falls_back_on_timeout():
    generator = ExplanationGenerator()
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.side_effect = httpx.TimeoutException("zaman aşımı")

    with patch("app.services.explanation_generator.httpx.Client", return_value=mock_client):
        result = generator.generate_explanation("client_2", "Davranışsal", "Orta", {})

    # 3 sn'de cevap gelmezse hata fırlatmıyor -> şablon metne düşüyor
    assert result == generator.fallback_template("client_2", "Davranışsal", "Orta")


def test_generate_explanation_falls_back_on_http_error():
    generator = ExplanationGenerator()
    response = MagicMock()
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500", request=MagicMock(), response=MagicMock()
    )
    mock_client = _mock_client_returning(response)

    with patch("app.services.explanation_generator.httpx.Client", return_value=mock_client):
        result = generator.generate_explanation("client_3", "Performans", "Düşük", {})

    # ollama 500 dönerse de şablon metne düşüyor
    assert result == generator.fallback_template("client_3", "Performans", "Düşük")


def test_generate_explanation_falls_back_on_empty_response_text():
    generator = ExplanationGenerator()
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"response": "   "}  # sadece boşluk gelirse boş cevap sayılıyor
    mock_client = _mock_client_returning(response)

    with patch("app.services.explanation_generator.httpx.Client", return_value=mock_client):
        result = generator.generate_explanation("client_4", "Davranışsal", "Yüksek", {})

    assert result == generator.fallback_template("client_4", "Davranışsal", "Yüksek")


def test_fallback_template_formats_all_fields():
    generator = ExplanationGenerator()

    result = generator.fallback_template("client_5", "Performans", "Orta")

    # istemci, tür ve şiddet şablona birebir yerleşiyor
    assert result == "client_5 için Performans tipinde anomali tespit edildi, risk seviyesi: Orta"

def test_behavioral_explanation_compares_features_to_baseline():
    generator = ExplanationGenerator()
    metrics = {
        "istek_orani": 1.3,
        "en_sik_endpoint_payi": 0.95,
        "ortalama_gecikme": 190.0,
        "top_endpoint": "/v1/accounts",
        "baseline_median": [0.1, 0.6, 85.0],
    }

    text = generator.fallback_template("client_supheli_0001", "Davranışsal", "Orta", metrics)

    assert text.startswith("client_supheli_0001: istek oranı 1.30 req/s")
    assert "baseline medyanının ~13 katı" in text
    assert "istekler %95 oranında /v1/accounts endpoint'ine gidiyor" in text
    assert "baseline medyanı %60" in text
    assert "ortalama gecikme 190 ms (baseline medyanı 85 ms)" in text


def test_behavioral_explanation_without_baseline_omits_comparison():
    generator = ExplanationGenerator()
    metrics = {"istek_orani": 1.3, "en_sik_endpoint_payi": 0.95, "ortalama_gecikme": 190.0, "baseline_median": None}

    text = generator.fallback_template("c1", "Davranışsal", "Orta", metrics)

    assert "req/s," in text  #karşılaştırma parantezi yok
    assert "baseline" not in text

def test_behavioral_explanation_handles_rate_below_and_near_baseline():
    generator = ExplanationGenerator ()
    low = generator.fallback_template("c1", "Davranışsal", "Orta", {"istek_orani": 0.05, "baseline_median": [0.1, 0.6, 85.0]})
    near = generator.fallback_template("c1", "Davranışsal", "Orta", {"istek_orani": 0.1, "baseline_median": [0.1, 0.6, 85.0]})

    assert "baseline medyanının ~%50 düzeyinde" in low
    assert "baseline medyanına yakın" in near


def test_behavioral_explanation_without_top_endpoint_name_still_reads_well():
    generator = ExplanationGenerator()

    text = generator.fallback_template("c1", "Davranışsal", "Orta", {"istek_orani": 1.0, "en_sik_endpoint_payi": 0.9})

    assert "istekler %90 oranında tek bir endpoint'e gidiyor" in text


def test_performance_explanation_uses_latency_window_mean_and_zscore():
    generator = ExplanationGenerator()
    metrics = {"latency_ms": 320, "window_mean": 62.0, "sample_count": 50, "z_score": 4.7}

    text = generator.fallback_template("client_yogun_0000", "Performans", "Orta", metrics)

    assert text =="client_yogun_0000: gecikme 320 ms; son 50 isteğin ortalaması 62 ms, z = 4.7"


def test_fallback_template_without_metrics_keeps_generic_text():
    generator = ExplanationGenerator()

    assert generator.fallback_template("c1", "Performans", "Orta") == (
        "c1 için Performans tipinde anomali tespit edildi, risk seviyesi: Orta"
    )
    assert generator.fallback_template("c1", "Performans", "Orta", {"z_score": 4.0}) == (
        "c1 için Performans tipinde anomali tespit edildi, risk seviyesi: Orta"
    )  #latency_ms yok, zengin cümlecik kurulmuyo


def test_combined_explanation_is_one_short_sentence_without_repeating_details():
    generator = ExplanationGenerator()

    text = generator.combined_explanation("gecikme 344 ms, z = 3.5")

    assert text == "davranışsal ve performans anomalisi aynı pencerede oluştu (gecikme 344 ms, z = 3.5)"


def test_summary_is_only_filled_for_performance_alerts():
    generator=ExplanationGenerator()
    metrics = {"latency_ms": 344.0, "z_score": 3.5, "istek_orani": 1.5}

    assert generator.summary("Performans", metrics) == "gecikme 344 ms, z = 3.5"
    assert generator.summary("Davranışsal", metrics) == ""
    assert generator.summary("Performans", {"z_score": 3.5}) == ""


def test_generate_explanation_fallback_uses_rich_text_when_metrics_given():
    generator = ExplanationGenerator()
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.side_effect = httpx.ConnectError("ollama yok")
    metrics={"latency_ms": 320, "window_mean": 62.0, "sample_count": 50, "z_score": 4.7}

    with patch("app.services.explanation_generator.httpx.Client", return_value=mock_client):
        result = generator.generate_explanation("c1", "Performans", "Orta", metrics)

    assert result == generator.fallback_template("c1", "Performans", "Orta", metrics)
    assert "z = 4.7" in result
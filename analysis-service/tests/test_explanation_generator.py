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
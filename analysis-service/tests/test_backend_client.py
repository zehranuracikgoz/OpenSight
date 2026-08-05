"""
BackendClient'ın doğru endpoint'e doğru payload'la istek attığını, backend'e
ulaşılamadığında hata fırlatmak yerine None döndürdüğünü mock'lanmış httpx ile doğruluyor
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from app.messaging.backend_client import BackendClient


def test_post_alert_sends_correct_payload_and_returns_alert_id():
    client = BackendClient("http://backend:8080")
    mock_response = MagicMock()
    mock_response.json.return_value = {"alertId": "alert-123"}
    mock_response.raise_for_status.return_value = None

    with patch("app.messaging.backend_client.httpx.post", return_value=mock_response) as mock_post:
        result = client.post_alert("client_1", "Performans", "Yüksek", z_score=5.5, related_endpoint="/v1/accounts")

    assert result == "alert-123"
    args, kwargs = mock_post.call_args
    assert args[0] == "http://backend:8080/api/alerts"
    assert kwargs["json"]["clientId"] == "client_1"
    assert kwargs["json"]["type"] == "Performans"
    assert kwargs["json"]["severity"] == "Yüksek"
    assert kwargs["json"]["zScore"] == 5.5


def test_post_alert_returns_none_when_backend_unreachable():
    client = BackendClient("http://backend:8080")
    with patch("app.messaging.backend_client.httpx.post", side_effect=httpx.ConnectError("boom")):
        result = client.post_alert("client_1", "Performans", "Yüksek")

    assert result is None


def test_post_correlation_sends_correct_payload():
    client = BackendClient("http://backend:8080")
    mock_response = MagicMock()
    mock_response.json.return_value = {"correlationId": "corr-1"}
    mock_response.raise_for_status.return_value = None

    with patch("app.messaging.backend_client.httpx.post", return_value=mock_response) as mock_post:
        result = client.post_correlation("perf-1", "beh-1")

    assert result == "corr-1"
    args, kwargs = mock_post.call_args
    assert args[0] == "http://backend:8080/api/alerts/correlations"
    assert kwargs["json"] == {"performanceAlertId": "perf-1", "behavioralAlertId": "beh-1"}


def test_post_correlation_returns_none_on_http_error():
    client = BackendClient("http://backend:8080")
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "400", request=MagicMock(), response=MagicMock()
    )

    with patch("app.messaging.backend_client.httpx.post", return_value=mock_response):
        result = client.post_correlation("bad-1", "bad-2")

    assert result is None


def test_warmup_sends_get_to_health_endpoint_and_returns_true():
    client = BackendClient("http://backend:8080")
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None

    with patch("app.messaging.backend_client.httpx.get", return_value=mock_response) as mock_get:
        result = client.warmup()

    assert result is True
    args, kwargs = mock_get.call_args
    assert args[0] == "http://backend:8080/health"


def test_warmup_returns_false_when_backend_unreachable():
    client = BackendClient("http://backend:8080")
    with patch("app.messaging.backend_client.httpx.get", side_effect=httpx.ConnectError("boom")):
        result = client.warmup()

    assert result is False

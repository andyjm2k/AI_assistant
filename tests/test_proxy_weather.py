from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


def _client():
    from src.servers.proxy_server import app
    return TestClient(app)


def _auth_headers():
    from src.servers.proxy_server import create_jwt, users_db
    users_db.setdefault("weather-user", {"created_at": "2026-01-01T00:00:00Z"})
    token = create_jwt({"sub": "weather-user"})
    return {"Authorization": f"Bearer {token}"}


def test_weather_requires_auth():
    client = _client()
    response = client.get("/v1/proxy/weather?location=Sydney")
    assert response.status_code in (401, 403)


def test_weather_endpoint_success_with_mocked_bom():
    client = _client()

    location_resp = MagicMock()
    location_resp.raise_for_status = MagicMock()
    location_resp.json.return_value = {
        "data": [{"name": "Sydney", "geohash": "r3gx2f"}]
    }

    obs_resp = MagicMock()
    obs_resp.raise_for_status = MagicMock()
    obs_resp.json.return_value = {
        "data": {"observations": {"temp": 22.2, "humidity": 66, "icon_descriptor": "sunny"}}
    }

    forecast_resp = MagicMock()
    forecast_resp.raise_for_status = MagicMock()
    forecast_resp.json.return_value = {
        "data": {"daily": [{"date": "2026-01-01", "temp_min": 18, "temp_max": 27, "rain_chance": 20}]}
    }

    with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_client_cls:
        client_instance = MagicMock()
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=None)
        client_instance.get = AsyncMock(side_effect=[location_resp, obs_resp, forecast_resp])
        mock_client_cls.return_value = client_instance

        response = client.get("/v1/proxy/weather?location=Sydney&detail=summary", headers=_auth_headers())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["resolved_location"] == "Sydney"
    assert "current" in body
    assert "forecast" in body


def test_weather_endpoint_memory_fallback_when_no_location():
    client = _client()

    location_resp = MagicMock(); location_resp.raise_for_status = MagicMock(); location_resp.json.return_value = {"data": [{"name": "Melbourne", "geohash": "r1r0q"}]}
    obs_resp = MagicMock(); obs_resp.raise_for_status = MagicMock(); obs_resp.json.return_value = {"data": {"observations": {"temp": 19}}}
    forecast_resp = MagicMock(); forecast_resp.raise_for_status = MagicMock(); forecast_resp.json.return_value = {"data": {"daily": []}}

    memory_manager = MagicMock()
    memory_manager.search_memories = AsyncMock(return_value=[{"text": "I live in Melbourne VIC"}])

    with patch("src.servers.proxy_server.memory_manager", memory_manager), \
         patch("src.servers.proxy_server.MEMORY_AVAILABLE", True), \
         patch("src.servers.proxy_server.httpx.AsyncClient") as mock_client_cls:
        client_instance = MagicMock()
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=None)
        client_instance.get = AsyncMock(side_effect=[location_resp, obs_resp, forecast_resp])
        mock_client_cls.return_value = client_instance

        response = client.get("/v1/proxy/weather", headers=_auth_headers())

    assert response.status_code == 200, response.text
    assert response.json().get("location_source") == "memory"

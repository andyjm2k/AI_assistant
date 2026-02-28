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


def test_weather_endpoint_success_with_mocked_open_meteo():
    client = _client()

    location_resp = MagicMock()
    location_resp.raise_for_status = MagicMock()
    location_resp.json.return_value = {
        "results": [{"name": "Sydney", "latitude": -33.86, "longitude": 151.2}]
    }

    forecast_resp = MagicMock()
    forecast_resp.raise_for_status = MagicMock()
    forecast_resp.json.return_value = {
        "current": {
            "temperature_2m": 22.2,
            "apparent_temperature": 23.1,
            "relative_humidity_2m": 66,
            "wind_speed_10m": 15.0,
            "weather_code": 1,
            "time": "2026-01-01T10:00",
        },
        "daily": {
            "time": ["2026-01-01"],
            "temperature_2m_min": [18],
            "temperature_2m_max": [27],
            "precipitation_probability_max": [20],
            "weather_code": [3],
        },
    }

    with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_client_cls:
        client_instance = MagicMock()
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=None)
        client_instance.get = AsyncMock(side_effect=[location_resp, forecast_resp])
        mock_client_cls.return_value = client_instance

        response = client.get("/v1/proxy/weather?location=Sydney&detail=summary", headers=_auth_headers())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["resolved_location"] == "Sydney"
    assert body["source"] == "open-meteo.com"
    assert "current" in body
    assert "forecast" in body


def test_weather_endpoint_memory_fallback_when_no_location():
    client = _client()

    location_resp = MagicMock()
    location_resp.raise_for_status = MagicMock()
    location_resp.json.return_value = {"results": [{"name": "Melbourne", "latitude": -37.81, "longitude": 144.96}]}
    forecast_resp = MagicMock()
    forecast_resp.raise_for_status = MagicMock()
    forecast_resp.json.return_value = {
        "current": {"temperature_2m": 19, "weather_code": 2, "time": "2026-01-01T09:00"},
        "daily": {"time": []},
    }

    memory_manager = MagicMock()
    memory_manager.search_memories = AsyncMock(return_value=[{"text": "I live in Melbourne VIC"}])

    with patch("src.servers.proxy_server.memory_manager", memory_manager), \
         patch("src.servers.proxy_server.MEMORY_AVAILABLE", True), \
         patch("src.servers.proxy_server.httpx.AsyncClient") as mock_client_cls:
        client_instance = MagicMock()
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=None)
        client_instance.get = AsyncMock(side_effect=[location_resp, forecast_resp])
        mock_client_cls.return_value = client_instance

        response = client.get("/v1/proxy/weather", headers=_auth_headers())

    assert response.status_code == 200, response.text
    assert response.json().get("location_source") == "memory"


def test_weather_endpoint_accepts_request_type_alias():
    client = _client()

    location_resp = MagicMock()
    location_resp.raise_for_status = MagicMock()
    location_resp.json.return_value = {
        "results": [{"name": "Sydney", "latitude": -33.86, "longitude": 151.2}]
    }

    forecast_resp = MagicMock()
    forecast_resp.raise_for_status = MagicMock()
    forecast_resp.json.return_value = {
        "current": {
            "temperature_2m": 22.2,
            "relative_humidity_2m": 66,
            "weather_code": 1,
            "time": "2026-01-01T10:00",
        },
        "daily": {
            "time": ["2026-01-01"],
            "temperature_2m_min": [18],
            "temperature_2m_max": [27],
            "precipitation_probability_max": [20],
            "weather_code": [3],
        },
    }

    with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_client_cls:
        client_instance = MagicMock()
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=None)
        client_instance.get = AsyncMock(side_effect=[location_resp, forecast_resp])
        mock_client_cls.return_value = client_instance

        response = client.get("/v1/proxy/weather?location=Sydney&requestType=current", headers=_auth_headers())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["detail"] == "current"
    assert body["forecast"] == []
    assert body["current"]


def test_extract_memory_location_supports_state_format():
    from src.servers.proxy_server import _extract_memory_location

    memories = [{"text": "Preferred city: Sydney, NSW"}]
    location = _extract_memory_location(memories)
    assert location == "Sydney, NSW"

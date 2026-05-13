import base64
import json


def _base64url_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(f"{text}{padding}")


def test_default_auth_token_lifetime_is_23_hours():
    from src.servers import proxy_server as ps

    assert ps.DEFAULT_JWT_EXPIRATION_SECONDS == 23 * 60 * 60

    token = ps.create_jwt({"sub": "expiry-test"}, expires_in=ps.DEFAULT_JWT_EXPIRATION_SECONDS)
    payload = json.loads(_base64url_decode(token.split(".")[1]).decode("utf-8"))

    assert payload["exp"] - payload["iat"] == 23 * 60 * 60

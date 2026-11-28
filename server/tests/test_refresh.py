from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import jwt

from app.core.config import get_settings
from app.core.security import ACCESS_TTL, REFRESH_TTL, create_token, read_token
from tests.test_api import ApiFixture


class RefreshTests(ApiFixture):
    def token(self, **changes):
        now = datetime.now(timezone.utc)
        claims = {"sub": str(self.user_id), "type": "refresh", "iat": now, "exp": now + timedelta(days=30)}
        claims.update(changes)
        return jwt.encode(claims, get_settings().jwt_secret.get_secret_value(), algorithm="HS256")

    def test_login_refresh_and_logout(self):
        self.client.cookies.clear()
        sent = []
        with patch("app.services.auth.send_code", side_effect=lambda email, code: sent.append(code)):
            issued = self.request("POST", "/auth/request-code", json={"email": "first@example.com"})
        response = self.client.post(
            "/api/v1/auth/verify-code", json={"code_id": issued["code_id"], "code": sent[0]}
        )
        self.assertEqual(response.status_code, 200)
        cookies = {cookie.name: cookie for cookie in self.client.cookies.jar}
        self.assertEqual(cookies["access_token"].path, "/")
        self.assertEqual(cookies["refresh_token"].path, "/api/v1/auth")
        for name, ttl in (("access", ACCESS_TTL), ("refresh", REFRESH_TTL)):
            claims = read_token(cookies[f"{name}_token"].value, name)
            self.assertEqual(claims["exp"] - claims["iat"], ttl)
            header = next(h for h in response.headers.get_list("set-cookie") if h.startswith(f"{name}_token="))
            self.assertIn("HttpOnly", header)
            self.assertIn("SameSite=lax", header)
            self.assertIn(f"Max-Age={ttl}", header)
        refresh_token = cookies["refresh_token"].value
        self.client.cookies.delete("access_token")
        self.client.cookies.set(
            "access_token", self.token(type="access", exp=datetime.now(timezone.utc) - timedelta(seconds=1))
        )
        self.request("GET", "/me", expected=401)
        self.client.cookies.delete("access_token")
        response = self.client.post("/api/v1/auth/refresh")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertEqual(len(response.headers.get_list("set-cookie")), 1)
        self.assertEqual(self.client.cookies.get("refresh_token"), refresh_token)
        self.assertEqual(self.request("GET", "/me")["id"], str(self.user_id))
        self.request("POST", "/auth/logout", expected=204)
        self.assertNotIn("access_token", self.client.cookies)
        self.assertNotIn("refresh_token", self.client.cookies)
        self.request("POST", "/auth/refresh", expected=401)
        self.request("GET", "/me", expected=401)
        self.request("POST", "/auth/logout", expected=204)

    def test_refresh_rejects_invalid_tokens(self):
        valid = read_token(self.token(), "refresh")
        key = get_settings().jwt_secret.get_secret_value()
        missing_type = {k: v for k, v in valid.items() if k != "type"}
        tokens = [
            "", "broken", create_token(self.user_id),
            self.token(exp=datetime.now(timezone.utc) - timedelta(seconds=1)),
            self.token(sub=str(uuid4())), self.token(sub="invalid"),
            self.token(iat=datetime.now(timezone.utc) + timedelta(hours=1)),
            jwt.encode(valid, "wrong-key" * 8, algorithm="HS256"),
            jwt.encode(missing_type, key, algorithm="HS256"),
        ]
        for token in tokens:
            with self.subTest(token_index=tokens.index(token)):
                self.client.cookies.clear()
                self.client.cookies.set("refresh_token", token)
                self.request("POST", "/auth/refresh", expected=401)
                self.assertNotIn("access_token", self.client.cookies)

    def test_refresh_cannot_authorize_api(self):
        self.client.cookies.clear()
        self.client.cookies.set("access_token", self.token())
        self.request("GET", "/me", expected=401)

    def test_refresh_validation_and_origin(self):
        self.client.cookies.set("refresh_token", self.token())
        self.request("POST", "/auth/refresh", headers={"Origin": "https://evil.example"}, expected=403)
        self.request("POST", "/auth/refresh", json={}, expected=422)
        self.request("POST", "/auth/refresh?token=x", expected=422)

    def test_logout_does_not_revoke_refresh_without_storage(self):
        token = self.token()
        self.client.cookies.set("refresh_token", token)
        self.request("POST", "/auth/logout", expected=204)
        self.client.cookies.clear()
        self.client.cookies.set("refresh_token", token)
        self.request("POST", "/auth/refresh", expected=204)

    def test_secure_cookies(self):
        with patch.object(get_settings(), "cookie_secure", True):
            self.client.cookies.set("refresh_token", self.token())
            response = self.client.post("/api/v1/auth/refresh")
            self.assertEqual(response.status_code, 204)
            self.assertIn("Secure", response.headers["set-cookie"])

"""Small async adapter for the Nacos 3.x Console API."""

import asyncio
import time
from typing import Any

import httpx


class NacosError(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(detail)


class NacosClient:
    def __init__(self, http: httpx.AsyncClient, username: str, password: str):
        self.http = http
        self.username = username
        self.password = password
        self._token = ""
        self._expires_at = 0.0
        self._login_lock = asyncio.Lock()

    async def _login(self) -> str:
        async with self._login_lock:
            if self._token and time.monotonic() < self._expires_at:
                return self._token
            response = await self.http.post(
                "/v3/auth/user/login",
                data={"username": self.username, "password": self.password},
            )
            if response.is_error:
                raise NacosError(502, "Nacos login failed; check server credentials.")
            try:
                body = response.json()
                token = body["accessToken"]
                ttl = float(body.get("tokenTtl", 18000))
                if not isinstance(token, str) or not token:
                    raise ValueError("Missing token")
            except (ValueError, TypeError, KeyError):
                raise NacosError(502, "Invalid Nacos login response.") from None
            self._token = token
            self._expires_at = time.monotonic() + max(0, ttl - 30)
            return token

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        data: dict | None = None,
        headers: dict | None = None,
    ) -> Any:
        try:
            for attempt in range(2):
                token = await self._login()
                response = await self.http.request(
                    method,
                    path,
                    params=params,
                    data=data,
                    headers={**(headers or {}), "accessToken": token},
                )
                if response.status_code in (401, 403) and attempt == 0:
                    self._expires_at = 0
                    continue
                try:
                    body = response.json()
                except ValueError:
                    raise NacosError(502, "Nacos returned a non-JSON response.") from None
                if not isinstance(body, dict):
                    raise NacosError(502, "Invalid Nacos response.")
                if response.is_error or body.get("code") != 0:
                    # Nacos 3.3 returns HTTP 500 with RESOURCE_CONFLICT for stale CAS.
                    if body.get("code") == 20005:
                        raise NacosError(409, "Policy changed; reload before saving.")
                    status = response.status_code
                    messages = {
                        400: "Nacos rejected the configuration or query.",
                        404: "Policy or namespace not found.",
                        409: "Policy changed; reload before saving.",
                        412: "Policy changed; reload before saving.",
                    }
                    if status in (401, 403):
                        raise NacosError(502, "Nacos credentials lack the required permission.")
                    raise NacosError(
                        status if status in messages else 502,
                        messages.get(status, "Nacos could not complete the request."),
                    )
                if "data" not in body:
                    raise NacosError(502, "Nacos response is missing data.")
                return body["data"]
        except httpx.TimeoutException:
            raise NacosError(504, "Nacos request timed out.") from None
        except httpx.RequestError:
            raise NacosError(503, "Nacos is unavailable.") from None

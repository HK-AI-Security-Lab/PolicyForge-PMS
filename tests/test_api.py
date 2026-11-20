import hashlib
from dataclasses import replace
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import Settings, create_app

SETTINGS = Settings("http://nacos:8080", "nacos", "password", "m" * 32, "r" * 32)
MANAGE = {"X-API-Key": SETTINGS.api_key}
READ = {"X-API-Key": SETTINGS.read_key}


class NacosStub:
    """Contract double; real server behavior is checked by scripts/smoke.py."""

    def __init__(self):
        self.records = {}
        self.calls = []
        self.logins = 0

    def __call__(self, request):
        self.calls.append(request)
        if request.url.path == "/v3/auth/user/login":
            self.logins += 1
            return httpx.Response(200, json={"accessToken": "token", "tokenTtl": 18000})
        assert request.headers["accessToken"] == "token"
        params = dict(request.url.params)
        if request.method == "POST":
            params = {
                k: v[0]
                for k, v in parse_qs(
                    request.content.decode(),
                    keep_blank_values=True,
                ).items()
            }
        key = tuple(params.get(k, "") for k in ("namespaceId", "groupName", "dataId"))
        if request.url.path.endswith("/namespace/list"):
            return self.ok([{"namespace": "", "namespaceShowName": "public"}])
        if request.url.path.endswith(("/list", "/searchDetail")):
            return self.ok(
                {
                    "pageItems": list(self.records.values()),
                    "totalCount": len(self.records),
                    "pageNumber": int(params["pageNo"]),
                    "pagesAvailable": 1,
                }
            )
        if request.method == "POST":
            expected = request.headers.get("casMd5")
            if expected and expected != self.records.get(key, {}).get("md5"):
                return httpx.Response(500, json={"code": 20005, "message": "resource conflict"})
            self.records[key] = {
                **params,
                "md5": hashlib.md5(params["content"].encode()).hexdigest(),
            }
            return self.ok(True)
        if request.method == "DELETE":
            self.records.pop(key, None)
            return self.ok(True)
        if key not in self.records:
            return self.ok(None)
        return self.ok(self.records[key])

    @staticmethod
    def ok(data):
        return httpx.Response(200, json={"code": 0, "data": data})


@pytest.fixture
def api():
    stub = NacosStub()
    with TestClient(create_app(SETTINGS, httpx.MockTransport(stub))) as client:
        yield client, stub


@pytest.mark.parametrize(
    "name,content,fmt,storage",
    [
        ("a.yaml", "# 注释\nallow: true\n", "yaml", "yaml"),
        ("a.json", '{\n  "allow": true\n}\n', "json", "json"),
        ("a.rego", "package example\ndefault allow := false\n", "rego", "text"),
        ("a.md", "# 安全约束\n\n请先请求授权。\n", "md", "text"),
        ("a.dsl", "allow(agent, read)  # preserve spaces\n", "dsl", "text"),
        ("a.cedar", 'permit(principal, action == Action::"read", resource);\n', "cedar", "text"),
    ],
)
def test_formats_round_trip_exactly(api, name, content, fmt, storage):
    client, stub = api
    path = f"/api/v1/policies/TOOLS/{name}"
    response = client.put(
        path,
        headers=MANAGE,
        json={
            "content": content,
            "tags": ["agent-research"],
            "description": "示例",
        },
    )
    assert response.status_code == 200
    detail = client.get(path, headers=READ).json()
    assert detail["content"] == content
    assert detail["format"] == fmt
    assert detail["storage_type"] == storage
    assert detail["tags"] == ["agent-research"]
    raw = client.get(path + "/raw", headers=READ)
    assert raw.content == content.encode()
    assert raw.headers["content-type"].startswith("text/plain")
    assert raw.headers["x-content-type-options"] == "nosniff"
    assert stub.logins == 1


def test_api_auth_and_read_key_cannot_write(api):
    client, stub = api
    assert client.get("/api/v1/policies").status_code == 401
    assert client.get("/api/v1/policies", headers=READ).status_code == 200
    calls = len(stub.calls)
    assert (
        client.put("/api/v1/policies/G/a", headers=READ, json={"content": "x"}).status_code == 401
    )
    assert client.delete("/api/v1/policies/G/a", headers=READ).status_code == 401
    assert len(stub.calls) == calls


def test_filters_and_pagination_are_forwarded(api):
    client, stub = api
    params = {
        "namespace": "prod",
        "group": "NET*",
        "data_id": "*.yaml",
        "tag": "agent-research",
        "app_name": "agent-1",
        "content_contains": "example.org",
        "page": 2,
        "page_size": 10,
    }
    response = client.get("/api/v1/policies", headers=READ, params=params)
    assert response.status_code == 200
    request = stub.calls[-1]
    assert request.url.path.endswith("/searchDetail")
    assert dict(request.url.params) == {
        "namespaceId": "prod",
        "groupName": "NET*",
        "dataId": "*.yaml",
        "configTags": "agent-research",
        "appName": "agent-1",
        "configDetail": "*example.org*",
        "pageNo": "2",
        "pageSize": "10",
        "search": "blur",
    }


def test_update_conflict_delete_and_missing(api):
    client, _ = api
    path = "/api/v1/policies/G/policy"
    assert client.get(path, headers=READ).status_code == 404
    assert client.put(path, headers=MANAGE, json={"content": "v1"}).status_code == 200
    md5 = client.get(path, headers=READ).json()["md5"]
    assert (
        client.put(path, headers=MANAGE, json={"content": "v2", "expected_md5": md5}).status_code
        == 200
    )
    assert (
        client.put(path, headers=MANAGE, json={"content": "v3", "expected_md5": md5}).status_code
        == 409
    )
    assert client.get(path, headers=READ).json()["content"] == "v2"
    assert client.delete(path, headers=MANAGE).status_code == 200
    assert client.get(path, headers=READ).status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {"content": " "},
        {"content": "中" * 350000},
        {"content": "ok", "tags": ["a,b"]},
        {"content": "ok", "tags": ["format-rego"]},
        {"content": "ok", "format": "not a format"},
        {"content": "ok", "unknown_field": True},
    ],
)
def test_invalid_input_never_reaches_nacos(api, payload):
    client, stub = api
    assert client.put("/api/v1/policies/G/p", headers=MANAGE, json=payload).status_code == 422
    assert not stub.calls


def test_upstream_failure_is_sanitized():
    def handler(request):
        raise httpx.ConnectError("private upstream details", request=request)

    with TestClient(create_app(SETTINGS, httpx.MockTransport(handler))) as client:
        response = client.get("/api/v1/policies", headers=READ)
        assert response.status_code == 503
        assert "private" not in response.text
        assert client.get("/health/ready").status_code == 503
        assert client.get("/health/live").status_code == 200


def test_expired_token_is_refreshed_once():
    stub = NacosStub()
    attempts = 0

    def handler(request):
        nonlocal attempts
        if request.url.path.endswith("/config/list"):
            attempts += 1
            if attempts == 1:
                return httpx.Response(403, json={"code": 403})
        return stub(request)

    with TestClient(create_app(SETTINGS, httpx.MockTransport(handler))) as client:
        assert client.get("/api/v1/policies", headers=READ).status_code == 200
        assert stub.logins == 2


def test_namespace_list(api):
    client, _ = api
    response = client.get("/api/v1/namespaces", headers=READ)
    assert response.status_code == 200
    assert response.json()[0]["namespaceShowName"] == "public"


@pytest.mark.parametrize("default_namespace", ["policyforge-pms", "custom-policies"])
def test_all_routes_use_configured_namespace_unless_explicitly_overridden(default_namespace):
    stub = NacosStub()
    config = replace(SETTINGS, namespace=default_namespace)
    with TestClient(create_app(config, httpx.MockTransport(stub))) as client:
        path = "/api/v1/policies/TOOLS/namespaced.txt"
        for query, expected in [("", default_namespace), ("?namespace=public", "public")]:
            result = client.put(path + query, headers=MANAGE, json={"content": expected})
            assert result.status_code == 200
            assert result.json()["namespace"] == expected
            assert (expected, "TOOLS", "namespaced.txt") in stub.records
            assert client.get(path + query, headers=READ).json()["namespace"] == expected
            assert client.get(path + "/raw" + query, headers=READ).text == expected
            assert client.get("/api/v1/policies" + query, headers=READ).status_code == 200
            assert stub.calls[-1].url.params["namespaceId"] == expected
            assert client.delete(path + query, headers=MANAGE).status_code == 200
            assert stub.calls[-1].url.params["namespaceId"] == expected
        assert client.get("/health/ready").status_code == 200
        assert stub.calls[-1].url.params["namespaceId"] == default_namespace

"""Exercise a running stack; remove only the unique smoke-test group afterward."""

import json
import os
import time
import uuid
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    values = {}
    env_file = ROOT / ".env"
    if env_file.exists():
        values.update(
            line.split("=", 1)
            for line in env_file.read_text().splitlines()
            if line and not line.startswith("#")
        )
    values.update(os.environ)
    base = values.get(
        "POLICYFORGE_URL", "http://127.0.0.1:" + values.get("POLICYFORGE_PORT", "8000")
    )
    key = values["POLICYFORGE_API_KEY"]
    group = "PMS_SMOKE_" + uuid.uuid4().hex[:12]
    created = []

    def call(method, path, body=None, token=key, expected=200):
        headers = {"X-API-Key": token, "Content-Type": "application/json"}
        data = json.dumps(body).encode() if body is not None else None
        request = Request(base + path, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=15) as response:
                status, raw = response.status, response.read()
        except HTTPError as error:
            status, raw = error.code, error.read()
        assert status == expected, (
            f"{method} {path}: expected {expected}, got {status}: {raw[:300]!r}"
        )
        return raw.decode() if path.endswith("/raw") else json.loads(raw)

    for _ in range(30):
        try:
            with urlopen(base + "/health/ready", timeout=5) as response:
                if response.status == 200:
                    break
        except (URLError, HTTPException, TimeoutError):
            pass
        time.sleep(1)
    else:
        raise SystemExit("API did not become ready. Inspect docker compose logs.")

    try:
        call("GET", "/api/v1/policies", token="invalid", expected=401)
        call("GET", "/api/v1/namespaces")
        for name in ("network.yaml", "tool-access.json", "authorization.rego", "constraints.md"):
            path = f"/api/v1/policies/{group}/{name}"
            content = (ROOT / "examples" / name).read_text()
            payload = {
                "content": content,
                "description": "临时联调策略",
                "tags": ["smoke-test"],
                "app_name": "policyforge-smoke",
            }
            call("PUT", path, payload)
            created.append(path)
            detail = call("GET", path)
            assert detail["content"] == content
            assert detail["tags"] == ["smoke-test"]
            assert call("GET", path + "/raw") == content
            print(f"PASS {name}: content and metadata round trip")
        query = urlencode({"group": group, "tag": "smoke-test", "page_size": 2})
        for attempt in range(10):
            page = call("GET", "/api/v1/policies?" + query)
            if page["total"] == 4:
                break
            time.sleep(0.3)
        assert page["total"] == 4 and len(page["items"]) == 2
        query = urlencode({"group": group, "content_contains": "docs.example.com"})
        page = call("GET", "/api/v1/policies?" + query)
        assert page["total"] == 1
        path = created[0]
        before = call("GET", path)
        payload = {"content": before["content"] + "# edited\n", "expected_md5": before["md5"]}
        call("PUT", path, payload)
        call("PUT", path, payload, expected=409)
        after = call("GET", path)
        assert after["content"] == payload["content"]
        assert after["tags"] == [] and after["description"] == "" and after["app_name"] == ""
        call("DELETE", path, token=values["POLICYFORGE_READ_KEY"], expected=401)
        call("GET", path, token=values["POLICYFORGE_READ_KEY"])
        print(
            "PASS filtering, pagination, content search, updates, stale-write rejection and reader key"
        )
    finally:
        failures = []
        for path in created:
            try:
                call("DELETE", path)
                call("GET", path, expected=404)
            except (AssertionError, URLError, HTTPException, TimeoutError) as exc:
                failures.append(f"{path}: {exc}")
        if failures:
            raise RuntimeError("Cleanup failed: " + "; ".join(failures))
        print(f"Cleaned up {len(created)} smoke-test policies")


if __name__ == "__main__":
    main()

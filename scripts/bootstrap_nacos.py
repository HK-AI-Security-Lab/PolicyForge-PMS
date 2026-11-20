"""Initialize a fresh Nacos admin once; verify existing credentials on restart."""

import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def post(base, path, fields):
    request = Request(base + path, data=urlencode(fields).encode(), method="POST")
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        try:
            payload = json.loads(error.read())
        except ValueError:
            payload = {}
        return error.code, payload


def main():
    base = os.getenv("NACOS_URL", "http://nacos:8080").rstrip("/")
    password = os.environ["NACOS_PASSWORD"]
    if not password:
        raise SystemExit("NACOS_PASSWORD must not be empty.")
    login = {"username": "nacos", "password": password}
    for _ in range(90):
        try:
            status, body = post(base, "/v3/auth/user/login", login)
            if status == 200 and isinstance(body, dict) and body.get("accessToken"):
                print("Nacos credentials verified.")
                return
            if status in (401, 403):
                status, body = post(base, "/v3/auth/user/admin", {"password": password})
                if status == 409 or (isinstance(body, dict) and body.get("code") == 409):
                    raise SystemExit(
                        "Admin already exists: set NACOS_PASSWORD to its current password."
                    )
        except (URLError, TimeoutError, ValueError):
            pass
        time.sleep(2)
    raise SystemExit("Nacos bootstrap timed out. Inspect docker compose logs nacos.")


if __name__ == "__main__":
    main()

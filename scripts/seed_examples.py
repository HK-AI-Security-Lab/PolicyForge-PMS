"""Import missing demo policies into Nacos; keep existing policies unchanged."""

import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

CONFIG_PATH = "/v3/console/cs/config"
EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
NATIVE_FORMATS = {"text", "json", "xml", "yaml", "html", "properties", "toml"}


def nacos_request(base, token, method, fields):
    encoded = urlencode(fields).encode()
    url = base + CONFIG_PATH
    if method == "GET":
        url += "?" + encoded.decode()
    request = Request(
        url,
        data=encoded if method == "POST" else None,
        headers={"accessToken": token},
        method=method,
    )
    with urlopen(request, timeout=10) as response:
        payload = json.load(response)
    if not isinstance(payload, dict) or payload.get("code") != 0 or "data" not in payload:
        raise RuntimeError("Nacos could not complete the example import.")
    return payload["data"]


def seed_examples(base, token, examples_dir=EXAMPLES):
    catalog = json.loads((examples_dir / "catalog.json").read_text(encoding="utf-8"))
    created = skipped = 0
    for entry in catalog:
        identity = {"namespaceId": "public", "groupName": entry["group"], "dataId": entry["file"]}
        if nacos_request(base, token, "GET", identity) is not None:
            skipped += 1
            continue
        content = (examples_dir / entry["file"]).read_bytes().decode("utf-8")
        fmt = entry["format"]
        fields = {
            **identity,
            "content": content,
            "desc": entry["description"],
            "type": fmt if fmt in NATIVE_FORMATS else "text",
            "configTags": f"demo,agent-research,format-{fmt}",
            "appName": "policyforge-demo",
        }
        if nacos_request(base, token, "POST", fields) is not True:
            raise RuntimeError(f"Failed to import example: {entry['group']}/{entry['file']}")
        created += 1
    print(f"Example policies: created {created}, retained {skipped}.")
    return {"created": created, "skipped": skipped}


def main():
    values = {}
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if env_file.exists():
        values.update(
            line.split("=", 1)
            for line in env_file.read_text().splitlines()
            if line and not line.startswith("#")
        )
    values.update(os.environ)
    base = values.get(
        "NACOS_URL", "http://127.0.0.1:" + values.get("NACOS_CONSOLE_PORT", "8080")
    ).rstrip("/")
    request = Request(
        base + "/v3/auth/user/login",
        data=urlencode(
            {
                "username": values.get("NACOS_USERNAME", "nacos"),
                "password": values.get("NACOS_PASSWORD", "nacos"),
            }
        ).encode(),
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        payload = json.load(response)
    if not isinstance(payload, dict) or not payload.get("accessToken"):
        raise SystemExit("Nacos login failed; check NACOS_USERNAME and NACOS_PASSWORD.")
    seed_examples(base, payload["accessToken"])


if __name__ == "__main__":
    main()

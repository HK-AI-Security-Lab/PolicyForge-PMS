import base64
import hashlib
import json
import stat
import tomllib
from pathlib import Path
from xml.etree import ElementTree

import pytest

from scripts import init_env, seed_examples

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_demo_env_defaults_and_preserves_existing_file(tmp_path):
    path = tmp_path / ".env"
    init_env.main(path)
    before = path.read_bytes()
    values = dict(
        line.split("=", 1)
        for line in before.decode().splitlines()
        if line and not line.startswith("#")
    )
    assert values["NACOS_PASSWORD"] == "nacos"
    assert values["POLICYFORGE_SEED_EXAMPLES"] == "true"
    assert values["POLICYFORGE_NAMESPACE"] == "policyforge-pms"
    assert len(base64.b64decode(values["NACOS_AUTH_TOKEN"])) >= 32
    assert len(values["POLICYFORGE_API_KEY"]) >= 32
    assert values["POLICYFORGE_API_KEY"] != values["POLICYFORGE_READ_KEY"]
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    init_env.main(path)
    assert path.read_bytes() == before


def test_catalog_files_exist_and_structured_examples_parse():
    catalog = json.loads((EXAMPLES / "catalog.json").read_text())
    identities = [
        (entry["group"], entry.get("data_id", Path(entry["file"]).name)) for entry in catalog
    ]
    assert len(catalog) == 16 and len(set(identities)) == 16
    for entry in catalog:
        content = (EXAMPLES / entry["file"]).read_text()
        assert content.strip()
        if entry["format"] == "json":
            json.loads(content)
        elif entry["format"] == "toml":
            tomllib.loads(content)
        elif entry["format"] == "xml":
            ElementTree.fromstring(content)


def test_seed_retains_edits_and_only_recreates_missing_examples(monkeypatch):
    records = {}
    namespaces = []
    namespace_creations = []

    def request(base, token, method, fields, path=seed_examples.CONFIG_PATH):
        if path.endswith("/namespace/list"):
            return namespaces
        if path == seed_examples.NAMESPACE_PATH:
            namespace_creations.append(fields.copy())
            namespaces.append({"namespace": fields["customNamespaceId"]})
            return True
        assert namespaces == [{"namespace": "policyforge-pms"}]
        assert fields["namespaceId"] == "policyforge-pms"
        key = fields["groupName"], fields["dataId"]
        if method == "GET":
            return records.get(key)
        records[key] = dict(fields)
        return True

    monkeypatch.setattr(seed_examples, "nacos_request", request)
    assert seed_examples.seed_examples("http://nacos", "token", EXAMPLES) == {
        "created": 16,
        "skipped": 0,
    }
    edited = ("NETWORK", "network.yaml")
    records[edited]["content"] = "User-edited policy; retain it."
    records[edited]["configTags"] = "user-tag"
    assert seed_examples.seed_examples("http://nacos", "token", EXAMPLES) == {
        "created": 0,
        "skipped": 16,
    }
    del records[("TOOL_ACCESS", "tool-access.json")]
    assert seed_examples.seed_examples("http://nacos", "token", EXAMPLES) == {
        "created": 1,
        "skipped": 15,
    }
    assert records[edited]["content"] == "User-edited policy; retain it."
    assert records[edited]["configTags"] == "user-tag"
    assert records[("AUTHORIZATION", "authorization.rego")]["type"] == "text"
    assert records[("SANDBOX", "sandbox.toml")]["type"] == "toml"
    cedar = records[("PATHGUARD", "policies.cedar")]
    assert cedar["type"] == "text"
    assert cedar["appName"] == "pathguard"
    assert cedar["configTags"] == "project-pathguard,cedar,a2a,mcp,format-cedar"
    assert records[("OPENCLAW_TASK_AUTH", "policies.cedar")]["content"] != cedar["content"]
    assert len(namespace_creations) == 1
    assert namespace_creations[0]["namespaceName"] == "PolicyForge-PMS"


def test_seed_fails_when_nacos_does_not_save(monkeypatch):
    def request(base, token, method, fields, path=seed_examples.CONFIG_PATH):
        if path.endswith("/namespace/list"):
            return [{"namespace": "policyforge-pms"}]
        return None if method == "GET" else False

    monkeypatch.setattr(
        seed_examples,
        "nacos_request",
        request,
    )
    with pytest.raises(RuntimeError, match="Failed to import example"):
        seed_examples.seed_examples("http://nacos", "token", EXAMPLES)


def test_seed_stops_if_namespace_cannot_be_created(monkeypatch):
    calls = []

    def request(base, token, method, fields, path=seed_examples.CONFIG_PATH):
        calls.append(path)
        return [] if method == "GET" else False

    monkeypatch.setattr(seed_examples, "nacos_request", request)
    with pytest.raises(RuntimeError, match="Failed to create policy namespace"):
        seed_examples.seed_examples("http://nacos", "token", EXAMPLES)
    assert seed_examples.CONFIG_PATH not in calls


def test_imported_project_files_match_recorded_source_hashes():
    catalog = json.loads((EXAMPLES / "catalog.json").read_text())
    imported = [entry for entry in catalog if "source" in entry]
    assert len(imported) == 6
    for entry in imported:
        source = entry["source"]
        assert (
            hashlib.sha256((EXAMPLES / entry["file"]).read_bytes()).hexdigest() == source["sha256"]
        )
        assert len(source["commit"]) == 40
        assert entry["format"] in ("cedar", "cedarschema")
        assert "cedar" in entry["tags"]

"""PolicyForge PMS: raw policy text in Nacos, no second database."""

import os
import re
import secrets
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request, Security
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.nacos import NacosClient, NacosError

CONFIG_PATH = "/v3/console/cs/config"
NATIVE_FORMATS = {"text", "json", "xml", "yaml", "html", "properties", "toml"}
TAG_PREFIX = "format-"
Identifier = Annotated[str, Path(min_length=1, max_length=128, pattern=r"^[\w.:-]+$")]
Namespace = Annotated[str, Query(min_length=1, max_length=128, pattern=r"^[\w.:-]+$")]


@dataclass(frozen=True)
class Settings:
    nacos_url: str
    username: str
    password: str
    api_key: str
    read_key: str = ""
    timeout: float = 10.0

    @classmethod
    def from_env(cls):
        values = cls(
            nacos_url=os.getenv("NACOS_URL", "http://localhost:8080").rstrip("/"),
            username=os.getenv("NACOS_USERNAME", "nacos"),
            password=os.getenv("NACOS_PASSWORD", ""),
            api_key=os.getenv("POLICYFORGE_API_KEY", ""),
            read_key=os.getenv("POLICYFORGE_READ_KEY", ""),
            timeout=float(os.getenv("NACOS_TIMEOUT", "10")),
        )
        if not values.password or len(values.api_key) < 32:
            raise RuntimeError(
                "Set NACOS_PASSWORD and POLICYFORGE_API_KEY (at least 32 characters)."
            )
        if values.read_key and (len(values.read_key) < 32 or values.read_key == values.api_key):
            raise RuntimeError("POLICYFORGE_READ_KEY must be distinct and at least 32 characters.")
        return values


class PolicyWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(min_length=1, max_length=1_048_576)
    format: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_.+-]{0,31}$")
    description: str = Field(default="", max_length=256)
    tags: list[str] = Field(default_factory=list, max_length=16)
    app_name: str = Field(default="", max_length=128, pattern=r"^[\w.:-]*$")
    expected_md5: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{32}$")

    @field_validator("content")
    @classmethod
    def nonempty_utf8(cls, value):
        if not value.strip() or len(value.encode("utf-8")) > 1_048_576:
            raise ValueError("Content must be nonblank UTF-8 text no larger than 1 MiB.")
        return value

    @field_validator("tags")
    @classmethod
    def valid_tags(cls, values):
        for tag in values:
            if (
                not tag
                or len(tag) > 64
                or "," in tag
                or tag != tag.strip()
                or any(ord(c) < 32 for c in tag)
                or tag.startswith(TAG_PREFIX)
            ):
                raise ValueError(
                    "Tags: 1–64 characters, no commas/control characters; format- is reserved."
                )
        if len(",".join(values)) > 200:
            raise ValueError("Combined tags must not exceed 200 characters.")
        return list(dict.fromkeys(values))


def normalize_policy(item: dict) -> dict:
    tags = [tag for tag in (item.get("configTags") or "").split(",") if tag]
    policy_format = next((t[len(TAG_PREFIX) :] for t in tags if t.startswith(TAG_PREFIX)), None)
    result = {
        "data_id": item.get("dataId"),
        "group": item.get("groupName"),
        "namespace": item.get("namespaceId") or "public",
        "format": policy_format or item.get("type") or "text",
        "storage_type": item.get("type") or "text",
        "description": item.get("desc") or "",
        "tags": [t for t in tags if not t.startswith(TAG_PREFIX)],
        "app_name": item.get("appName") or "",
        "md5": item.get("md5"),
        "created_at": item.get("createTime"),
        "updated_at": item.get("modifyTime"),
    }
    if "content" in item:
        result["content"] = item["content"]
    return result


def create_app(settings: Settings | None = None, transport=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        config = settings or Settings.from_env()
        async with httpx.AsyncClient(
            base_url=config.nacos_url,
            timeout=config.timeout,
            transport=transport,
        ) as http:
            app.state.settings = config
            app.state.nacos = NacosClient(http, config.username, config.password)
            yield

    app = FastAPI(
        title="PolicyForge PMS",
        version="0.1.0",
        lifespan=lifespan,
        description="Lightweight policy storage over Nacos. Saving publishes immediately.",
    )
    key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

    def authorize(request: Request, key: str | None = Security(key_header)):
        cfg = request.app.state.settings
        if key and secrets.compare_digest(key.encode(), cfg.api_key.encode()):
            return
        if (
            key
            and cfg.read_key
            and secrets.compare_digest(key.encode(), cfg.read_key.encode())
            and request.method in ("GET", "HEAD")
        ):
            return
        raise HTTPException(401, "A valid X-API-Key with the required access is needed.")

    @app.exception_handler(NacosError)
    async def handle_nacos_error(request, exc):
        return JSONResponse(status_code=exc.status, content={"detail": exc.detail})

    @app.get("/health/live", tags=["health"])
    async def live():
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    async def ready(request: Request):
        try:
            await request.app.state.nacos.request(
                "GET",
                CONFIG_PATH + "/list",
                params={
                    "namespaceId": "public",
                    "dataId": "",
                    "groupName": "",
                    "pageNo": 1,
                    "pageSize": 1,
                },
            )
        except NacosError:
            return JSONResponse(status_code=503, content={"status": "not_ready"})
        return {"status": "ready"}

    secured = [Depends(authorize)]

    @app.get("/api/v1/namespaces", dependencies=secured, tags=["organization"])
    async def namespaces(request: Request):
        return await request.app.state.nacos.request("GET", "/v3/console/core/namespace/list")

    @app.get("/api/v1/policies", dependencies=secured, tags=["policies"])
    async def list_policies(
        request: Request,
        namespace: Namespace = "public",
        data_id: str = Query(default="", max_length=128),
        group: str = Query(default="", max_length=128),
        tag: str = Query(default="", max_length=64, pattern=r"^[^,]*$"),
        app_name: str = Query(default="", max_length=128),
        content_contains: str = Query(default="", max_length=256),
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=20, ge=1, le=100),
    ):
        params = {
            "namespaceId": namespace,
            "dataId": data_id,
            "groupName": group,
            "configTags": tag,
            "appName": app_name,
            "search": "blur",
            "pageNo": page,
            "pageSize": page_size,
        }
        path = CONFIG_PATH + "/list"
        if content_contains:
            params["configDetail"] = f"*{content_contains}*"
            path = CONFIG_PATH + "/searchDetail"
        data = await request.app.state.nacos.request("GET", path, params=params)
        return {
            "items": [normalize_policy(x) for x in data["pageItems"]],
            "total": data["totalCount"],
            "page": data["pageNumber"],
            "pages": data["pagesAvailable"],
        }

    async def fetch(request, group, data_id, namespace):
        data = await request.app.state.nacos.request(
            "GET",
            CONFIG_PATH,
            params={
                "namespaceId": namespace,
                "groupName": group,
                "dataId": data_id,
            },
        )
        if data is None:
            raise NacosError(404, "Policy not found.")
        return normalize_policy(data)

    @app.get("/api/v1/policies/{group}/{data_id}/raw", dependencies=secured, tags=["policies"])
    async def raw(
        request: Request, group: Identifier, data_id: Identifier, namespace: Namespace = "public"
    ):
        item = await fetch(request, group, data_id, namespace)
        return PlainTextResponse(
            item["content"],
            headers={
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-store",
            },
        )

    @app.get("/api/v1/policies/{group}/{data_id}", dependencies=secured, tags=["policies"])
    async def get_policy(
        request: Request, group: Identifier, data_id: Identifier, namespace: Namespace = "public"
    ):
        return await fetch(request, group, data_id, namespace)

    @app.put("/api/v1/policies/{group}/{data_id}", dependencies=secured, tags=["policies"])
    async def save_policy(
        request: Request,
        group: Identifier,
        data_id: Identifier,
        policy: PolicyWrite,
        namespace: Namespace = "public",
    ):
        policy_format = policy.format or PurePosixPath(data_id).suffix.lstrip(".").lower() or "text"
        policy_format = {"yml": "yaml", "txt": "text"}.get(policy_format, policy_format)
        if not re.fullmatch(r"[a-z][a-z0-9_.+-]{0,31}", policy_format):
            policy_format = "text"
        storage_type = policy_format if policy_format in NATIVE_FORMATS else "text"
        data = {
            "namespaceId": namespace,
            "groupName": group,
            "dataId": data_id,
            "content": policy.content,
            "type": storage_type,
            "desc": policy.description,
            "configTags": ",".join([*policy.tags, TAG_PREFIX + policy_format]),
            "appName": policy.app_name,
        }
        headers = {"casMd5": policy.expected_md5.lower()} if policy.expected_md5 else {}
        success = await request.app.state.nacos.request(
            "POST", CONFIG_PATH, data=data, headers=headers
        )
        if success is not True:
            raise NacosError(409, "Nacos did not save the policy; reload and retry.")
        return {
            "saved": True,
            "data_id": data_id,
            "group": group,
            "namespace": namespace,
            "format": policy_format,
        }

    @app.delete("/api/v1/policies/{group}/{data_id}", dependencies=secured, tags=["policies"])
    async def delete_policy(
        request: Request, group: Identifier, data_id: Identifier, namespace: Namespace = "public"
    ):
        success = await request.app.state.nacos.request(
            "DELETE",
            CONFIG_PATH,
            params={
                "namespaceId": namespace,
                "groupName": group,
                "dataId": data_id,
            },
        )
        if success is not True:
            raise NacosError(502, "Nacos did not acknowledge deletion.")
        return {"deleted": True}

    return app


app = create_app()

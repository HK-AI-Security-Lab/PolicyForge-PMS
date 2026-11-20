# PolicyForge PMS

轻量策略管理后端：**Nacos 保存策略并提供编辑界面，FastAPI 提供统一的策略 API**。

面向智能体的安全约束、工具访问规则、网络限制和其他文本策略。正文原样保存，
不要求统一策略语言，不额外部署数据库，不自行开发前端。

```text
管理员 ── Nacos 控制台 ──┐
                       ├── Nacos 3.3.0 / 内嵌存储 / 持久化卷
程序 ── PolicyForge API ─┘
```

## 能做什么

- 保存、覆盖编辑、读取和删除策略；获取正文时保留注释、空白和换行。
- JSON、YAML、XML、Properties、TOML 使用 Nacos 原生类型；Rego、Markdown、自定义 DSL 使用 TEXT。
- 用 Namespace 区分环境，Group 分类，Tags 交叉组织，App Name 标识所属智能体或应用。
- 按名称/分组模式、单个标签、应用、正文关键词查询，支持分页。
- 直接使用 Nacos 控制台编辑、查看历史、比较版本及回滚。
- 管理 API Key 和可选只读 API Key；Nacos 账号密码只在服务端使用。
- 可选 `expected_md5` 透传到 Nacos CAS，避免正文已变更时覆盖旧版本。

**保存即发布，没有独立草稿或审批状态。PMS 不执行策略，也不判断某次操作是否允许。**

## 三步启动

要求：Docker Engine / Docker Desktop、Docker Compose v2，以及宿主机 Python 3。

```bash
cd PolicyForge-PMS
python3 scripts/init_env.py
docker compose up -d --build
```

首次启动会拉取 Nacos 镜像并初始化管理员。`nacos-init` 完成后 API 才启动；
这个初始化容器退出码为 0 是正常状态。

| 入口 | 地址 / 说明 |
| --- | --- |
| Nacos 策略编辑界面 | http://localhost:8080 |
| API 交互文档 | http://localhost:8000/docs |
| API 就绪检查 | http://localhost:8000/health/ready |
| Nacos 用户名 | `nacos` |
| Nacos 密码 | 本机 `.env` 中的 `NACOS_PASSWORD` |
| API 管理密钥 | 本机 `.env` 中的 `POLICYFORGE_API_KEY` |
| API 只读密钥 | 本机 `.env` 中的 `POLICYFORGE_READ_KEY` |

在 `/docs` 点击 **Authorize**，填入 API Key 后即可调用。
密钥由初始化脚本随机生成，`.env` 权限为 0600，Git 和 Docker 构建上下文都忽略它。
脚本不会覆盖已有 `.env`。已有 Nacos 数据卷时应保留原密码，修改 `.env` 不会自动修改 Nacos 密码。

```bash
docker compose ps -a
docker compose logs --tail=80 nacos nacos-init api
```

默认只绑定本机回环地址。本 Compose 用于单机 / 可信内网部署，不是高可用方案。
需要远程访问时，在前面部署自己的 HTTPS 网关和身份接入。

## 在控制台组织策略

打开 Nacos 的配置管理，按以下约定创建配置：

| 字段 | 例子 | 用途 |
| --- | --- | --- |
| Namespace | `public`、`dev`、`prod` | 环境；新命名空间在控制台创建 |
| Group | `NETWORK`、`TOOL_ACCESS`、`SANDBOX` | 策略类别 |
| Data ID | `research-network.yaml` | 唯一名称，建议带扩展名 |
| Tags | `agent-research,team-security,format-yaml` | 适用对象、团队、原始格式 |
| App Name | `research-agent` | 所属应用 / Agent |
| Description | `研究智能体的外网访问限制` | 人类可读说明 |
| Content | 原始策略文本 | 不要再包进另一份 JSON / YAML |

策略唯一键是 `(namespace, group, data_id)`。同名策略可以在不同组和命名空间存在。
API 的名称、组和命名空间接受字母、数字、下划线、点、冒号和短横线，不接受斜线或空格。

API 自动维护一个保留标签 `format-<格式>`，例如 `format-rego`。
从 API 返回的 `tags` 不包含这个标签，`format` 字段包含它的值；
在 Nacos 控制台编辑时请保留该标签。控制台新建自定义格式时选择 TEXT，并手工添加对应格式标签。
没有格式标签的配置会按 Nacos 的 `type` 返回。

## API

除健康检查和文档外，请求都需要 `X-API-Key`。

| 方法 | 路径 | 含义 |
| --- | --- | --- |
| GET | `/api/v1/namespaces` | 列出可用命名空间（保留 Nacos 原始响应字段） |
| GET | `/api/v1/policies` | 查询策略列表 |
| GET | `/api/v1/policies/{group}/{data_id}` | 读取正文和元数据 |
| GET | `/api/v1/policies/{group}/{data_id}/raw` | 读取原始 UTF-8 文本 |
| PUT | `/api/v1/policies/{group}/{data_id}` | 创建或完整替换并发布 |
| DELETE | `/api/v1/policies/{group}/{data_id}` | 删除策略 |

单条策略接口接受 `?namespace=public`，省略时使用 `public`。

### 写入任意文本策略

在项目根目录执行。示例使用 Python 标准库，自动读取本机生成的管理密钥。

```python
import json
from pathlib import Path
from urllib.request import Request, urlopen

env = dict(line.split('=', 1) for line in Path('.env').read_text().splitlines()
           if line and not line.startswith('#'))
payload = {
    'content': Path('examples/authorization.rego').read_text(),
    'format': 'rego',
    'description': '研究智能体工具授权',
    'tags': ['agent-research', 'team-security'],
    'app_name': 'research-agent',
}
request = Request(
    'http://localhost:8000/api/v1/policies/TOOL_ACCESS/research.rego',
    data=json.dumps(payload).encode(),
    headers={'X-API-Key': env['POLICYFORGE_API_KEY'], 'Content-Type': 'application/json'},
    method='PUT',
)
with urlopen(request) as response:
    print(response.read().decode())
```

`format` 省略时由扩展名推断；无扩展名使用 `text`。
正文不校验为 JSON/YAML/Rego 等特定语言，只校验非空 UTF-8 文本和 1 MiB 上限。
原文不会被解析再序列化，因此保留注释和换行。

PUT 是**完整替换**：省略 `description`、`tags`、`app_name` 就清空对应值。
编辑时建议先 GET，保留要保留的元数据，再 PUT。
对更新可附带上次 GET 返回的 `md5` 作为 `expected_md5`；
正文版本冲突返回 HTTP 409。MD5 是 Nacos 的内容版本标记，不是安全完整性证明；
它不能检测仅元数据修改，也不提供跨多个策略的事务。

### 查询

`GET /api/v1/policies` 支持这些参数：

| 参数 | 例子 | 说明 |
| --- | --- | --- |
| `namespace` | `public` | 命名空间 ID，非显示名称 |
| `data_id` | `research*` | Nacos 名称匹配模式 |
| `group` | `NETWORK` | 分组匹配模式 |
| `tag` | `agent-research` | 单个标签，避免多标签 AND/OR 歧义 |
| `app_name` | `research-agent` | 所属应用 |
| `content_contains` | `example.com` | Nacos 正文模糊搜索；不是语义查询 |
| `page` | `1` | 从 1 开始 |
| `page_size` | `20` | 1–100 |

查自定义格式也可以用 `tag=format-rego`。
返回 `items / total / page / pages`；列表不包含正文，按需读取详情。
底层沿用 Nacos 的匹配语义，正文搜索适合管理检索，不建议用于每次工具调用的实时鉴权路径。

只读密钥可访问查询、详情和原文接口，不能保存或删除。
当前是共享服务密钥模型，没有用户级审计、逐 Agent 授权或逐命名空间 API Key 权限。
这些密钥控制的是 PMS 的访问权限，与正文中描述的 Agent 权限是两回事。

## Docker 镜像与现有 Nacos

```bash
docker build -t policyforge-pms:0.1.0 .
```

Dockerfile 只封装轻量 API；Nacos 作为独立容器运行。Compose 合并管理两者和一个一次性初始化容器。
不把两个进程塞进同一个镜像。运行时使用非 root 用户，Compose 中 API 根文件系统只读。

已有 Nacos **3.3.0** 时无需启动本项目的 Nacos。准备私有 `api.env`：

```dotenv
NACOS_URL=http://your-nacos-console:8080
NACOS_USERNAME=your-service-account
NACOS_PASSWORD=your-service-account-password
POLICYFORGE_API_KEY=replace-with-at-least-32-random-characters
POLICYFORGE_READ_KEY=replace-with-a-different-random-key
```

```bash
docker run -d --name policyforge-pms \
  --env-file api.env \
  -p 127.0.0.1:8000:8000 \
  policyforge-pms:0.1.0
```

`NACOS_URL` 是 **Console API 地址**，不是 SDK 的 8848 端口；不要添加旧版 `/nacos` 前缀。
其他 Nacos 版本需要自行做兼容验证。该适配器使用默认用户名/密码登录，未实现 OIDC 登录。
已有部署建议使用具有相应命名空间读写权限的服务账号；就绪检查目前查询 `public`，需允许读取它。
`POLICYFORGE_READ_KEY` 可省略；管理密钥和 Nacos 密码必须设置。

## 开发与验证

```bash
uv sync --locked
uv run pytest -q
uv run ruff check app scripts tests
uv run ruff format --check app scripts tests
docker compose config --quiet
```

本地不使用 Docker 运行 API 时，导出环境变量后启动：

```bash
set -a
. ./.env
set +a
NACOS_URL=http://localhost:8080 uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

真实容器联调（会创建唯一临时分组中的四条样例，最后删除）：

```bash
python3 scripts/smoke.py
```

脚本验证多格式原文往返、元数据、查询、分页、修改、CAS 冲突、只读密钥和删除。
单元测试使用 Nacos HTTP 替身，不等同于真实服务器联调。

2026-11-20 验证记录：17 项单元测试通过；Ruff 检查和 Compose 配置校验通过；
已在本机构建 `policyforge-pms:0.1.0`（Linux ARM64），并与 Nacos 3.3.0 真实容器联调。
多格式原文、标签查询、内容搜索、分页、CAS 冲突、只读权限、删除均通过；
另验证 XML / Properties / TOML / HTML / DSL 与 CRLF 换行保留，以及 Nacos 重启后的数据持久化。
测试结束已删除临时策略。AMD64 镜像未在本机验证。
当前测试依赖有一条 Starlette 关于未来更换测试 HTTP 客户端的弃用提示，不影响这 17 项测试结果。

`uv.lock` 锁定开发依赖，`requirements.txt` 包含部署依赖版本和包哈希。更新依赖后重新导出：

```bash
uv lock
uv export --locked --no-dev --no-emit-project --format requirements-txt --output-file requirements.txt
```

## 数据持久化

Nacos 内嵌存储在 `nacos-data` 命名卷中；`docker compose down` 不删除它。
**`docker compose down -v` 会删除策略和账号数据**，不要用于日常停机。
备份应包含数据卷及安全保存的 `.env`；单机内嵌存储建议停机后做卷备份。
API 无本地业务数据，也没有独立索引需要同步。

## 参考

- [Nacos Console API](https://nacos.io/docs/latest/manual/admin/console-api/)
- [Nacos 鉴权](https://nacos.io/docs/latest/manual/admin/auth/)
- [Nacos 3.3.0 发布](https://github.com/alibaba/nacos/releases/tag/3.3.0)
- [Nacos 官方 Docker 部署](https://github.com/nacos-group/nacos-docker)

项目首次实现：2026-11-20。

# PolicyForge PMS 部署交接

交付完整 Git 仓库即可。开发人员在目标机器生成自己的 `.env`，然后使用 Compose 启动。
无需提供原部署机器的 API Key，也无需另外申请 Nacos 密钥。

## 首次部署

准备 Git、Docker Engine / Docker Desktop、Docker Compose v2 和 Python 3.10+。
需要能够拉取 Docker 镜像和 Python 依赖，8000 / 8080 端口未被占用，并具有仓库读取权限。

```bash
git clone git@github.com:xingx2/PolicyForge-PMS.git
cd PolicyForge-PMS
python3 scripts/init_env.py
docker compose config --quiet
docker compose up -d --build
docker compose ps -a
```

**不要先把 `.env.example` 复制为 `.env`**：模板里的 API Key 是空值，初始化脚本不会覆盖已有文件。
直接运行 `init_env.py`，它会生成完整 `.env`，设置示例账号 `nacos / nacos`，并随机生成其他密钥。

| 服务 | 成功状态 | 职责 |
| --- | --- | --- |
| `nacos` | `Up` | 配置存储和编辑控制台 |
| `nacos-init` | `Exited (0)` | 初始化管理员、创建策略空间、导入 16 份配置后正常退出 |
| `api` | `Up (healthy)` | 策略查询、读写 API |

首次拉取、启动和初始化需要时间。`up -d` 返回后检查健康状态：

```bash
curl --fail 'http://127.0.0.1:8000/health/ready'
docker compose logs --tail=80 nacos-init api
```

就绪接口应返回 `status=ready`。在 `http://localhost:8080` 用 `nacos / nacos` 登录，
选择 `PolicyForge-PMS` 命名空间，再进入“配置管理 → 配置列表”，应有 16 份初始配置。

## 环境变量在哪里

`.env` 是**宿主机文件**，本项目没有将它复制或挂载进容器。Compose 读取它，
把 `compose.yaml` 的 `environment` 中明确声明的值注入对应容器进程。
不是把 `.env` 的全部变量无差别注入每个容器。

| 变量 | 来源 | 使用位置 / 用途 |
| --- | --- | --- |
| `NACOS_PASSWORD` | 示例默认 `nacos` | `nacos-init` 创建/验证管理员，`api` 向 Nacos 登录 |
| `NACOS_AUTH_TOKEN` | 随机生成的 Base64 值 | 只注入 `nacos`；这是签名密钥，不是 PMS API Key |
| `NACOS_AUTH_IDENTITY_VALUE` | 随机生成 | 只注入 `nacos`，配合固定身份 key `policyforge` |
| `POLICYFORGE_API_KEY` | 随机生成 | 注入 `api`；查询、写入和删除权限 |
| `POLICYFORGE_READ_KEY` | 独立随机生成 | 注入 `api`；查询、详情和原文读取权限 |
| `POLICYFORGE_NAMESPACE` | 默认 `policyforge-pms` | 注入 `api` 和 `nacos-init` |
| `POLICYFORGE_SEED_EXAMPLES` | 默认 `true` | 只注入 `nacos-init`；是否补充缺失示例 |
| `POLICYFORGE_PORT` / `NACOS_CONSOLE_PORT` | 默认 8000 / 8080 | 宿主机端口映射，不注入应用容器 |

`NACOS_URL`、`NACOS_USERNAME` 等在 Compose 服务定义中设置；API 用容器网络地址
`http://nacos:8080` 连接 Nacos。API 会自行登录并缓存 Nacos 访问 token，调用方不需要手动获取它。

Dockerfile 构建的是 **API 镜像**，`.env` 被 `.dockerignore` 排除，密钥没有写进镜像。
只交付 `policyforge-pms:0.1.0` 镜像，还不足以启动全套系统：仍需要 Nacos、连接参数、
初始化脚本和示例文件。建议交付完整仓库，按首次部署步骤启动。
本项目 API 镜像在部署机器本地构建，目前没有配置公共镜像仓库发布。

## 开发人员如何取得密钥

部署人员可以查看目标机器仓库下的 `.env`。只显示两个 API Key：

```bash
grep '^POLICYFORGE_.*KEY=' .env
```

也可确认正在运行的 API 容器实际使用的值（需要 Docker 管理权限）：

```bash
docker compose exec -T api printenv POLICYFORGE_READ_KEY
docker compose exec -T api printenv POLICYFORGE_API_KEY
```

普通调用方不会通过 HTTP 接口自动领取密钥；由部署管理员把对应 Key 配置给调用服务。
只读客户端使用 `POLICYFORGE_READ_KEY`，管理客户端使用 `POLICYFORGE_API_KEY`。
在请求头携带 `X-API-Key`，或在 `http://localhost:8000/docs` 点击 Authorize 后输入。
Nacos 控制台用账号密码登录；把 `nacos` 当作 API Key 不会通过认证。

## 验证密钥和查询

在仓库目录运行以下代码，读取本机密钥验证 Cedar 标签查询，不打印密钥：

```bash
python3 - <<'PY'
import json
from pathlib import Path
from urllib.request import Request, urlopen
env = dict(line.split('=', 1) for line in Path('.env').read_text().splitlines()
           if line and not line.startswith('#'))
base = 'http://127.0.0.1:' + env.get('POLICYFORGE_PORT', '8000')
request = Request(base + '/api/v1/policies?tag=format-cedar',
                  headers={'X-API-Key': env['POLICYFORGE_READ_KEY']})
with urlopen(request, timeout=10) as response:
    data = json.load(response)
print('Cedar 策略数量：', data['total'])
PY
```

首次部署预期返回 5；以后新增或删除策略时数量会相应改变。

## 服务器部署后的访问

默认端口只绑定 `127.0.0.1`：部署机器本地可以访问，
其他电脑直接访问 `服务器IP:8000` 或 `服务器IP:8080` 不会连通。
浏览器中的 localhost 指浏览器所在电脑。远程演示可建立 SSH 隧道：

```bash
ssh -N -L 8000:127.0.0.1:8000 -L 8080:127.0.0.1:8080 user@your-server
```

保持隧道终端运行，再在自己电脑打开 `http://localhost:8080` 或 `http://localhost:8000/docs`。
本机端口已被占用时修改 `-L` 中最前面的本地端口。正式对外提供 API 时，由开发人员接入 HTTPS 反向代理。

## 重启、更新和更换密钥

- 每台新部署机器生成独立 API Key，新 Key 不能访问另一套部署。
- `init_env.py` 保留已有 `.env`；日常更新不需要重新生成。
- 改了 `.env` 的 API Key 后，执行 `docker compose up -d --force-recreate api` 才能让容器使用新值。
- `docker compose restart api` 不会重新读取 `.env` 的新值。
- shell 已导出的同名变量优先于 `.env`；建议在干净 shell 中部署，容器内的值才是实际生效值。
- 只改 `.env` 的 `NACOS_PASSWORD` 不会修改已存在的 Nacos 账号密码；应先在控制台改密码，再同步 `.env` 并重建相应服务。
- 保留 `.env` 和 `nacos-data` 数据卷；`docker compose down` 保留卷，`down -v` 会删除策略和账号数据。

示例默认 Nacos 账号密码按项目约定为 `nacos / nacos`。
部署目录读取权限或 Docker 管理权限持有者能够读取密钥；普通 API 调用方不能自动获取。

## 首次部署验证记录

2026-11-20 已用仓库导出的全新目录、独立 Compose 项目和空 Nacos 数据卷验证此流程。
新生成的 API Key 与 API 容器环境一致；管理员初始化和命名空间创建成功；
自动导入 16 份配置，只读 Key 可按标签查询 5 份 Cedar 策略。
真实 API 的读写、只读权限限制、分页、搜索、CAS 冲突和删除均通过。
测试完成后仅清理该临时项目，既有实例保持运行。验证平台为 Linux ARM64 容器；AMD64 未实测。

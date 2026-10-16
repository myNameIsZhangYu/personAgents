# PersonAgents

生产级个人智能体系统，支持多 Agent 编排、MCP 工具层、持久化记忆、权限治理、可观测性和评估框架。

## 架构总览

```
┌─────────────────────────────────────────────────────┐
│                    CLI (Typer + Rich)                │
│          run / chat / eval / doctor / version         │
└────────────────────────┬────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────┐
│              LangGraph 编排引擎                      │
│  intent → planner → executor → critic → memory_write│
└──┬────────────┬────────────┬────────────┬───────────┘
   ▼            ▼            ▼            ▼
┌──────┐  ┌──────────┐  ┌─────────┐  ┌──────────────┐
│ 意图  │  │   LLM    │  │  工具层  │  │   记忆系统    │
│ 识别  │  │ 降级链   │  │MCP+沙箱 │  │SQLite+Chroma │
└──────┘  └──────────┘  └────┬────┘  └──────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────┐
│                    治理层                            │
│        权限策略 · 限流 · 审计日志                     │
└────────────────────────┬────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────┐
│                    可观测性                          │
│      Langfuse (自托管) · structlog · 成本追踪        │
└─────────────────────────────────────────────────────┘
```

## 核心功能

### 多 Agent 编排（LangGraph）

使用 LangGraph 状态机驱动 Agent 循环：

| 节点 | 职责 |
|---|---|
| **intent** | 将用户输入分类为 `chat` / `task` / `memory_write` / `tool_use` |
| **planner** | 注入工具 schema 与记忆上下文，输出结构化步骤 |
| **executor** | 按步骤调用注册表工具或 LLM，工具参数来自规划结果 |
| **critic** | 评估执行结果，返回 `success` / `retry` / `fail` |
| **memory_write** | 成功后将经验写入长期记忆 |

支持条件路由、失败重试（最多 3 次）、SQLite 检查点持久化。

### LLM 调用与降级链

统一 LLM 接口，支持多种 provider 自动降级：

```
主模型（如 glm-5.3-flash）
  ↓ 超时 / 429 / 5xx
降级模型（如 gpt-4o-mini）
  ↓ 全部失败
本地 Ollama（兜底）
  ↓ 仍失败
返回结构化错误
```

- 连接超时 5s 显式设置（`httpx.Timeout`），避免挂起
- 无 API Key 时自动跳过 OpenAI provider
- 本地 Ollama 先做健康预检（`/api/tags`）
- 每级降级自动记录 `llm_degraded` 日志

### 记忆系统

| 层 | 存储 | 用途 |
|---|---|---|
| **短期** | 内存 | 当前对话上下文 |
| **长期** | SQLite（WAL 模式） | 用户偏好、事实、决策 |
| **语义** | ChromaDB | 向量相似度检索 |

- SQLite WAL 模式保证并发安全
- ChromaDB 零配置本地持久化
- Alembic 管理 schema 迁移
- Critic 评估成功后自动写入经验记忆

### MCP 工具层

统一工具注册表（`ToolRegistry`），支持 OpenAI function calling 格式：

- **filesystem**：沙箱内读/写/列/删（路径逃逸保护）
- **Docker sandbox**：一次性容器执行 shell，限制网络/CPU/内存
- 所有工具调用经过权限策略校验和审计日志

### 治理（Governance）

| 模块 | 功能 |
|---|---|
| **PolicyEngine** | 权限分级（read/write/shell/network）+ 危险命令黑名单（regex 匹配） |
| **RateLimiter** | 令牌桶限流（LLM 和工具分别独立） |
| **AuditLogger** | SQLite 审计日志，记录每次工具调用的输入/输出/状态 |

危险命令检测支持变形绕过（如 `rm -r -f /`、`git push --force`）。

### 可观测性

- **Langfuse**（自托管 Docker）: 记录每次 LLM 调用的 input/output/token/延迟/降级状态，并按 `intent` / `planner` / `executor` / `critic` 生成嵌套节点 span
- **structlog**: 结构化 JSON 日志，支持 console/JSON 切换
- **CostTracker**: 按 session 追踪 token 消耗和调用次数

## 快速开始

### 1. 安装依赖

```bash
uv sync --all-extras
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`：

```env
OPENAI_API_KEY=your-key-here
OPENAI_BASE_URL=https://api.openai.com/v1   # 或本地代理
OPENAI_MODEL=gpt-4o                         # 或任意兼容模型
```

### 3. 运行

```bash
# 单次提问
uv run person-agents run "你好"

# 交互式对话
uv run person-agents chat

# 评估（baseline 用例，可输出 JSON 报告）
uv run person-agents eval --output eval-report.json

# 健康检查（LLM API / 数据目录 / Ollama 连通性）
uv run person-agents doctor
```

### 4. 启动 Langfuse 监控（可选）

```bash
docker compose up -d
# 构建并启动应用与自托管监控栈（生产建议先移除 app 服务的 --help 命令）
docker compose up -d --build app

# 打开 http://localhost:3000 → 注册账号 → 创建项目 → 获取 API Key
# 将 pk-lf-xxx / sk-lf-xxx 填入 .env 的 LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY
```

## 测试

```bash
# 运行全部 23 个测试（memory / tools / governance / fallback）
uv run pytest -q

# 代码检查
uv run ruff check src tests
```

## 项目结构

```
src/person_agents/
├── cli.py                 # Typer 入口（version/doctor/run/chat/eval）
├── config/
│   ├── settings.py        # pydantic-settings 多环境配置
│   └── fallback.yaml      # LLM 降级链配置
├── llm/
│   ├── client.py          # 统一 LLM 调用接口（OpenAI + Ollama）
│   ├── fallback.py        # 降级链（健康预检 + 重试）
│   └── router.py          # 简单/复杂任务路由
├── memory/
│   ├── sqlite_store.py    # SQLite WAL 存储（CRUD + session）
│   ├── vector_store.py    # ChromaDB 向量检索
│   └── migrations/        # Alembic schema 迁移
├── graph/
│   ├── state.py           # AgentState TypedDict
│   ├── nodes.py           # 意图/规划/执行/评估/记忆 节点
│   ├── edges.py           # 条件路由（含 max-retry）
│   └── checkpoint.py      # SQLite 检查点
├── tools/
│   ├── mcp_filesystem.py  # 沙箱文件操作（路径逃逸保护）
│   ├── registry.py        # 工具注册表（OpenAI schema）
│   ├── sandbox.py         # Docker 沙箱执行器
│   └── mcp_client.py      # MCP 协议客户端
├── governance/
│   ├── policy.py          # 权限 + 危险命令 regex 黑名单
│   ├── rate_limiter.py    # 令牌桶限流
│   └── audit.py           # SQLite 审计日志
├── observability/
│   ├── langfuse.py        # Langfuse trace 与嵌套节点 span
│   ├── logging.py         # structlog 配置
│   └── cost.py            # token 成本追踪
└── eval/
    ├── runner.py          # 评估运行器
    └── cases/             # 基准测试用例
```

## Docker 服务

| 服务 | 端口 | 用途 |
|---|---|---|
| app | — | 编译后的 LangGraph agent 应用 |
| langfuse | 3000 | Web UI + API |
| langfuse-db | 5432 | PostgreSQL（元数据） |
| langfuse-clickhouse | 8123/9000 | ClickHouse（trace 存储） |
| langfuse-minio (SeaweedFS) | 9000 | S3 兼容对象存储 |
| langfuse-redis | 6379 | 队列（BullMQ） |
| langfuse-worker | — | 后台任务处理 |

## 技术栈

| 组件 | 选型 | 版本 |
|---|---|---|
| Python | ≥3.11 | — |
| 编排 | LangGraph | ≥0.2 |
| 向量库 | ChromaDB | ≥0.5 |
| 数据库 | SQLite + Alembic | — |
| LLM | OpenAI SDK（兼容任意 base_url） | ≥1.0 |
| 监控 | Langfuse | ≥2.0（自托管） |
| CLI | Typer + Rich | ≥0.9 |
| 沙箱 | Docker | — |
| 校验 | Pydantic v2 | ≥2.0 |

## 工程化与部署

- **应用镜像**：`Dockerfile.app` 使用非 root 运行时和独立数据卷。
- **CI**：`.github/workflows/ci.yml` 在 push/PR 时执行 `ruff check` 和 `pytest`。
- **治理配置**：通过 `PERSON_AGENTS_GRANTED_PERMISSIONS=read,write` 控制默认权限；生产环境不应直接授予 `shell`。
- **沙箱**：shell 工具使用一次性容器，默认禁网并限制 CPU / 内存。
- **数据持久化**：agent 数据、Langfuse 元数据、trace 与对象存储均使用 named volumes。
- **评估**：`person-agents eval` 直接调用当前 fallback chain，并生成 JSON pass rate / token 报告。

## License

MIT

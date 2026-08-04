# RSS-AI

RSS-AI 是一个面向单用户的 AI RSS 阅读器。FreshRSS 仍是订阅和原始文章的唯一数据源；本仓库的 Phase 0 仅提供可部署的基础工程、单用户登录、健康检查、数据库迁移链和后台任务运行时。

## 当前阶段

已具备：FastAPI、React/Vite、PostgreSQL、Redis、Celery、Alembic、Caddy 反向代理、会话认证与 CI。

尚未实现：FreshRSS 同步、文章阅读器、AI Provider、翻译、总结与简报。这些内容从 Phase 1 起逐步交付。

## 支持的平台

- Linux AMD64 (`linux/amd64`)
- Linux ARM64 (`linux/arm64`)

核心服务不依赖 CUDA、AVX 或任何本地 AI 模型容器。后续的 Ollama、LibreTranslate 等本地 Provider 会通过 HTTP 接入，且其硬件支持取决于所选 Provider，而非 RSS-AI 核心服务。

## 快速开始

1. 安装 Docker Engine 与 Docker Compose Plugin。
2. 复制配置并替换全部示例 Secret：

   ```bash
   cp .env.example .env
   ```

3. 启动服务：

   ```bash
   docker compose up -d --build
   ```

4. 打开 `http://localhost:8080`，使用 `.env` 中的 `ADMIN_USERNAME` 和 `ADMIN_PASSWORD` 登录。

首次启动会运行 `alembic upgrade head`。PostgreSQL 和 Redis 只在 Docker 内部网络中可访问；唯一暴露的服务是 Caddy。

## 健康检查

- `GET /health`：API 进程存活。
- `GET /ready`：PostgreSQL 与 Redis 可用。

两者都可通过 Caddy 访问，例如 `http://localhost:8080/ready`。AI Provider 的将来状态不会影响这两个核心端点。

## 本地开发与测试

后端：

```bash
cd backend
python -m pip install -e '.[dev]'
pytest
```

前端：

```bash
cd frontend
corepack enable
pnpm install --frozen-lockfile
pnpm run test:run
pnpm run build
```

## 多架构镜像发布

本地 `docker compose build` 会为当前主机架构构建镜像。发布到镜像仓库时使用 Buildx 创建同一标签下的多架构 manifest：

```bash
docker buildx create --name rss-ai-builder --use
docker buildx inspect --bootstrap

docker buildx build --platform linux/amd64,linux/arm64 \
  -t <registry>/rss-ai-api:<version> -t <registry>/rss-ai-api:latest --push ./backend

docker buildx build --platform linux/amd64,linux/arm64 \
  -t <registry>/rss-ai-web:<version> -t <registry>/rss-ai-web:latest --push ./frontend
```

CI 使用 QEMU 构建两个平台，但正式发布前仍应在真实 ARM64 Linux 设备上执行集成测试。

## 安全说明

- 不要提交 `.env`，并在生产环境中更换管理员密码、PostgreSQL 密码和会话密钥。
- `APP_ENVIRONMENT=production` 时，示例管理员密码与会话密钥会导致应用拒绝启动。
- 在 HTTPS 反向代理后部署时，将 `SESSION_COOKIE_SECURE=true`；若跨域部署，明确设置 `APP_ALLOWED_ORIGINS`。
- 应用不会把凭据写入 API 响应或日志。

# RSS-AI

单用户、自托管的 RSS 阅读器。FreshRSS 负责订阅与原文；RSS-AI 提供三栏阅读、OPML、异步 AI 处理和应用内通知。

## 启动

```bash
cp .env.example .env
docker compose up -d --build
```

打开 `http://localhost:8080`，使用 `.env` 中的管理员账户登录。首次启动会执行 Alembic 迁移。PostgreSQL 与 Redis 不映射到宿主机；Caddy 是唯一入口。

## FreshRSS 同步

1. 在左栏底部展开“连接与同步”。
2. 输入 **FreshRSS 本身的地址**，而不是 RSS-AI 地址。例如 FreshRSS 位于 `http://server:8081/` 时填写该地址；`http://server:8084/` 若显示 RSS-AI 登录页，则不能填写在这里。
3. 输入 FreshRSS 用户名和在 FreshRSS 中启用 Google Reader API 后取得的 API 密码。
4. 点击“测试连接”；成功时会显示发现的订阅源数。点击“保存并同步”后，左栏会立即刷新文件夹和订阅源。

每个连接也会由 Celery Scheduler 按设置的同步间隔自动同步。同步失败时，连接条目会显示已脱敏的错误信息；密码和 API Key 永远不返回给浏览器。

## OPML

“连接与同步”中可以导入或导出 OPML：

- 导入会把文件夹和订阅源加入 RSS-AI 的资料库，不上传到第三方。
- 导出会包含 RSS-AI 已知的本地订阅和 FreshRSS 已同步的订阅，适合作为备份或迁移文件。

OPML 只携带订阅元数据；若要下载文章，请连接 FreshRSS 并完成同步。

## AI 设置

左栏底部的“AI 设置与任务”提供：

- OpenAI-compatible、Ollama、DeepL、LibreTranslate、Google Cloud Translation Provider 配置与测试；
- Provider 下的模型登记；内置函数、工作流、最近任务和应用内通知；
- 打开文章自动翻译/总结开关与月度预算设置。

AI 任务由 Celery 异步处理，原文阅读不依赖 Provider。配置了带 `input_per_million` / `output_per_million` 价格的模型后，月度预算会在新任务提交时硬性拦截超额请求。

## 开发验证

```bash
cd backend && python -m pip install -e '.[dev]' && pytest
cd frontend && pnpm install --frozen-lockfile && pnpm run test:run && pnpm run build
```

## 多架构镜像

```bash
docker buildx build --platform linux/amd64,linux/arm64 -t <registry>/rss-ai-api:<version> --push ./backend
docker buildx build --platform linux/amd64,linux/arm64 -t <registry>/rss-ai-web:<version> --push ./frontend
```

QEMU/Buildx 的 ARM64 构建只验证镜像可构建；发布前仍应在真实 ARM64 Linux 主机执行 Compose 集成验收。

## 安全

生产部署必须替换管理员密码、会话密钥、PostgreSQL 密码和 `APP_ENCRYPTION_KEY`。生成 Fernet 密钥：

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

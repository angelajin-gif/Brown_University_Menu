# Backend (FastAPI + Supabase + OpenRouter)

为 `Frontend/` 的个性化大学食堂助手提供后端服务。

## 1. 技术栈

- FastAPI（全异步 `async/await`）
- Supabase PostgreSQL（关系数据）
- pgvector（私有知识库向量检索）
- OpenRouter（Embeddings + Chat Completion）
- Railway 部署（Docker）

## 2. 目录结构

```text
Backend/
├── app/
│   ├── api/
│   │   ├── routes/
│   │   ├── deps.py
│   │   └── router.py
│   ├── core/
│   ├── db/
│   │   └── repositories/
│   ├── models/
│   ├── services/
│   └── main.py
├── scripts/
│   ├── ingest_embeddings.py
│   ├── sync_brown_menu.py
│   └── run_menu_sync.sh
├── sql/
│   ├── schema.sql
│   └── seed.sql
├── .env.example
├── Dockerfile
├── railway.toml
├── railway.cron.toml
└── requirements.txt
```

## 3. 本地运行

1. 安装依赖

```bash
cd Backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. 配置环境变量

```bash
cp .env.example .env
# 填写 SUPABASE_DB_URL、OPENROUTER_API_KEY 等
```

3. 初始化 Supabase 数据库（在 Supabase SQL Editor 执行）

```sql
-- 先执行
sql/schema.sql
-- 再执行
sql/seed.sql
```

4. 生成知识库向量（将 seed 的文本写入 pgvector）

```bash
python -m scripts.ingest_embeddings
```

5. 启动服务

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

6. 手动执行一次“菜单同步入库”（独立脚本，可脱机运行）

```bash
python -m scripts.sync_brown_menu
# 或
./scripts/run_menu_sync.sh
```

## 4. API 概览

基础前缀：`/api/v1`

- `GET /health`
- `GET /menus`
- `GET /menus/{item_id}`
- `GET /users/{user_id}/preferences`
- `PUT /users/{user_id}/preferences`
- `GET /users/{user_id}/notifications`
- `PUT /users/{user_id}/notifications`
- `GET /users/{user_id}/favorites`
- `PUT /users/{user_id}/favorites`
- `POST /rag/chunks/upsert`
- `POST /rag/search`
- `POST /insights/daily`
- `POST /insights/chat`

## 5. 与前端逻辑映射

- 菜单页：`GET /menus` 支持 `meal_slot`、`hall_id`、`query`，默认仅返回当天（`MENU_SYNC_TIMEZONE`）的菜单数据。
- 偏好页：`/users/{user_id}/preferences`、`/favorites`。
- 提醒页：`/users/{user_id}/notifications`。
- AI 每日洞察：`POST /insights/daily`。
- AI 聊天推荐：`POST /insights/chat`。

## 6. Railway 部署建议

1. Railway 服务根目录设置为 `Backend/`。
2. 使用 `Dockerfile` 构建。
3. API 服务使用 `railway.toml`（健康检查：`/api/v1/health`）。
4. 在 Railway Variables 配置 `.env.example` 中的变量。
5. 确保 `CORS_ALLOWED_ORIGINS` 包含你的 Cloudflare Pages 域名。
6. 再创建一个独立的 Railway Cron Service（同样指向 `Backend/` 目录），使用 `railway.cron.toml`：

```toml
[deploy]
startCommand = "python -m scripts.sync_brown_menu"
cronSchedule = "0 5 * * *"
```

`0 5 * * *` 表示每天 `05:00 UTC` 执行，对应 `EST 00:00`（固定东部标准时）。

## 7. CORS 严格策略

后端不会使用 `*`，只允许 `CORS_ALLOWED_ORIGINS` 中的明确来源。

示例：

```env
CORS_ALLOWED_ORIGINS=https://your-frontend.pages.dev,https://your-domain.com
```

# 多智能体旅行规划助手

## Config

项目运行时只读取一个本地配置文件：`config.yaml`。

```powershell
Copy-Item config.example.yaml config.yaml
```

`config.yaml` 用于填写 LLM key、数据库、Redis、携程/飞猪/美团 cookie、高德地图 key、天气 key 以及 Agent-Reach 渠道 cookie。这个文件已被 `.gitignore` 忽略，不要提交真实凭证。

`config.example.yaml` 是仓库模板，不包含真实 cookie 或 key。环境变量只保留少量覆盖入口，例如 `APP_CONFIG_FILE` 可以指定其他 YAML 路径。

## Frontend
The consumer chat frontend lives in `frontend/`.

```powershell
cd frontend
npm install
npm run dev
```

The frontend reads `VITE_API_BASE_URL`; when it is not set, it calls `http://127.0.0.1:8000`.

## Auth
The backend exposes:
- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`

Authenticated frontend requests use `Authorization: Bearer <token>`.

# 多智能体旅行规划助手 - 前端

这是一个使用 React + TypeScript + Vite 构建的现代 Web 前端应用。

## 功能特性

- 🔐 用户认证系统（注册/登录）
- 💬 智能聊天对话界面
- 📋 历史记录管理
- 🗺️ 完整旅行方案展示
- 🎨 美观的 UI 设计
- 📱 响应式布局

## 快速开始

### 安装依赖

```bash
npm install
```

### 启动开发服务器

```bash
npm run dev
```

应用将在 http://127.0.0.1:3000 运行

### 构建生产版本

```bash
npm run build
```

### 预览构建结果

```bash
npm run preview
```

## 技术栈

- React 19
- TypeScript
- Vite
- Tailwind CSS
- React Router（内嵌在组件中）
- Testing Library

## 项目结构

```
src/
├── api/          # API 客户端
├── auth/         # 认证上下文
├── components/   # 可复用组件
│   ├── ChatComposer.tsx
│   ├── HistoryDrawer.tsx
│   ├── MessageList.tsx
│   └── PlanDrawer.tsx
├── pages/        # 页面组件
│   ├── ChatPage.tsx
│   ├── LoginPage.tsx
│   └── RegisterPage.tsx
├── index.css     # 全局样式
└── main.tsx      # 应用入口
```

## 环境变量

在 `.env` 文件中配置：

```
VITE_API_BASE_URL=http://127.0.0.1:8000  # 后端 API 地址
VITE_DEV=true                            # 开发模式
VITE_DEBUG=false                         # 调试模式
```

## 开发指南

### 添加新页面

1. 在 `src/pages/` 创建新组件
2. 在 `App.tsx` 中添加路由逻辑
3. 添加相应的样式到 `src/index.css`

### 添加新 API

1. 在 `src/api/client.ts` 中定义类型
2. 实现 API 函数
3. 在组件中使用

### 样式开发

项目使用 Tailwind CSS，可以直接在组件中使用 utility 类。

## 测试

```bash
npm test
```

或者运行带 UI 的测试：

```bash
npm run test:ui
```

## 部署

构建后的文件在 `dist/` 目录，可以直接部署到静态文件服务器。

## 贡献

欢迎提交 Issue 和 Pull Request！

## 注意事项

- 确保 `.env` 中的 `VITE_API_BASE_URL` 指向正确的后端服务
- 后端需要在 http://127.0.0.1:8000 运行
- 开发时确保前后端都处于运行状态
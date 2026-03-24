# BiliDigest — B站视频知识资产系统

输入一个B站视频URL，自动提取转写文本、关键帧、结构化知识，沉淀为可复用的"知识资产"。区别于一次性总结工具，BiliDigest 将视频信息资产化持久存储，支持随时回看、多种输出模态再生成、跨视频融合分析和自然语言 prompt 定制。

---

## 功能展示

### 视频提取
粘贴B站视频链接，后台自动完成：下载 → 转写 → 关键帧截取 → LLM知识提取，全程状态实时可见。

### 全文总结
带关键帧配图的章节式总结笔记。摘要始终可见，章节支持折叠/展开的渐进式阅读，时间戳点击可跳转视频对应位置。

### 小红书图文
一键生成小红书风格图文，每段配关键帧，底部带话题标签，支持一键复制全文。

### 知识树
将视频知识结构可视化为交互式树形图，多层级可展开折叠，快速把握视频脉络。

### AI 对话
基于视频内容的多轮问答，回答附带时间戳引用，点击可跳转视频原文。

### 多视频融合
勾选多个视频资产，合并知识后生成综合总结，支持跨视频对比分析。

### 用户 Prompt 定制
输入自然语言侧重点（如"侧重可行动建议"、"只关注技术细节"），生成内容随之调整。

---

## 快速启动

**环境要求**：Python ≥ 3.10 | Node.js ≥ 18 | ffmpeg | yt-dlp

```bash
# 1. 克隆项目
git clone <repo-url> && cd bilidigest

# 2. 后端
cd backend
pip install -r requirements.txt
pip install faster-whisper
cp .env.example .env          # 编辑 .env 填入 LLM_API_KEY
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# 3. 前端（新终端）
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev

# 4. 打开浏览器访问 http://localhost:3000
```

> **注意**：需要配置 `LLM_API_KEY`。默认使用 MiniMax API，也可切换为 DeepSeek、OpenAI 等任何 OpenAI 兼容接口（修改 `.env` 中的 `LLM_BASE_URL` 和 `LLM_MODEL`）。

---

## 技术选型

| 层 | 选择 | 理由 |
|----|------|------|
| 前端 | Next.js 16 + TailwindCSS 4 | SSR + 路由内置，Tailwind 快速出 UI |
| 后端 | FastAPI | 原生 async，Swagger 自动文档，Python 生态丰富 |
| 数据库 | SQLite + FTS5 | 零配置，clone 即用，FTS5 支持全文检索 |
| 视频下载 | yt-dlp | B站支持最完善的开源下载工具 |
| 音频转写 | faster-whisper (base) | CPU 上比 openai-whisper 快 2x，int8 量化省内存 |
| 关键帧 | ffmpeg | 工业标准，稳定可靠 |
| LLM | MiniMax API (OpenAI 兼容) | 上下文长、中文能力强、接口通用可替换 |

---

## 系统架构

```
┌─────────────┐     ┌──────────────────────────────────────────┐
│   Browser    │────▶│  Next.js Frontend (localhost:3000)        │
│  (React SPA) │◀────│  左侧导航 + 右侧内容 / 左右分屏详情页    │
└─────────────┘     └──────────────┬───────────────────────────┘
                                   │ REST API
                    ┌──────────────▼───────────────────────────┐
                    │  FastAPI Backend (localhost:8000)          │
                    │  /api/assets  /api/generate  /api/query   │
                    │  /api/history /api/generate/cache          │
                    └──┬────────┬────────┬────────┬────────────┘
                       │        │        │        │
                  ┌────▼──┐ ┌──▼───┐ ┌──▼──┐ ┌──▼────────┐
                  │yt-dlp │ │faster│ │ffmpeg│ │ MiniMax   │
                  │下载    │ │whisper│ │截帧  │ │ LLM API  │
                  └───┬───┘ └──┬───┘ └──┬──┘ └──┬────────┘
                      │        │        │        │
                  ┌───▼────────▼────────▼────────▼────────┐
                  │  SQLite (bilidigest.db)                 │
                  │  assets | transcripts(+FTS5) | keyframes│
                  │  structured_knowledge | generation_history│
                  └────────────────────────────────────────┘
```

**数据流**：URL提交 → 后台异步任务（下载→转写→截帧→知识提取）→ 状态轮询 → 前端展示 → 按需生成输出（缓存优先，避免重复调LLM）

---

## 核心取舍

**做了什么：**
- 完整的 URL → 资产抽取 → 多模态输出闭环
- 3种输出模态：全文总结（带关键帧配图）、小红书图文、知识树
- 视觉内容贯穿全链路：关键帧截取→知识提取配图→总结内嵌→小红书配图
- AI 对话查询，回答溯源到视频时间点
- 用户自然语言 prompt 定制输出侧重点
- 多视频融合生成
- 资产产出历史保存与复用
- 渐进式阅读（章节折叠/展开，先看结构再看细节）
- 左右分屏学习体验（视频固定+内容滚动+时间戳联动）
- 生成结果缓存，首次生成后秒级加载

**没做什么 + 为什么：**
- **没用向量数据库**：48h 内 SQLite + FTS5 全文检索够用，关键词匹配 + 均匀采样兜底已能满足 QA 需求
- **没做弹幕分析**：优先保证核心抽取链路完整，弹幕是锦上添花
- **没做场景变化检测截帧**：固定间隔(60s/帧)更稳定可靠，场景检测增加复杂度但收益有限
- **没做用户系统**：本地运行的工具型产品，单用户足够

---

## 降级处理

| 场景 | 处理策略 |
|------|----------|
| 视频无字幕 | 自动降级到 faster-whisper 本地转写（base 模型，CPU 可跑） |
| 下载失败 | yt-dlp 自动重试3次 + 标准化URL避免格式问题 + 明确错误信息 |
| LLM 调用失败 | 5次重试 + 指数退避；最终失败则资产降级为 partial 状态（转写和截帧已保存，可重试知识提取） |
| Whisper 转写卡死 | 30分钟超时保护，自动中断并标记失败 |
| 超长视频 (>4h) | 配置 MAX_VIDEO_DURATION 限制，只处理前2小时 |
| 后端崩溃重启 | 自动将所有 processing 状态资产标记为 failed，可一键重新处理 |
| 前端后端断连 | 红色横幅提示"后端连接异常" + 重试按钮（不再静默吞错） |

---

## 如果再给1周

1. **向量数据库替换 FTS5**：引入 ChromaDB，支持语义检索而非纯关键词匹配
2. **GPU 部署 Whisper large-v3**：转写速度提升 10x，准确率大幅提升
3. **更多输出模态**：理解测验题集、Podcast 脚本、会议纪要格式
4. **用户系统 + 资产分享**：多用户 + 公开资产库 + 协作标注
5. **B站 Cookie 集成**：获取 AI 字幕和更高画质视频流
6. **流式输出 (SSE)**：生成过程实时流式展示，不用干等
7. **批量导入**：支持 UP 主主页批量抓取、收藏夹批量处理
8. **导出能力**：PDF / Notion / 飞书文档一键导出

---

## 项目结构

```
bilidigest/
├── backend/
│   ├── main.py              # FastAPI 入口，CORS + 路由注册
│   ├── config.py            # 环境变量配置
│   ├── database.py          # SQLite 建表 + 迁移 + 重启清理
│   ├── models.py            # Pydantic 请求/响应模型
│   ├── llm_client.py        # LLM 调用封装（重试+退避）
│   ├── .env                 # 环境变量（LLM_API_KEY 等）
│   ├── routers/
│   │   ├── assets.py        # 资产 CRUD + 后台处理流水线
│   │   ├── generate.py      # 内容生成 + 缓存查询 + 历史记录
│   │   └── query.py         # AI 对话查询
│   └── services/
│       ├── bilibili.py      # B站 API + yt-dlp 下载
│       ├── transcriber.py   # 字幕获取 + faster-whisper 转写
│       ├── keyframe.py      # ffmpeg 关键帧截取
│       ├── knowledge.py     # Map-Reduce 知识提取
│       └── generator.py     # 总结/小红书/知识树生成
├── frontend/
│   ├── app/
│   │   ├── layout.tsx       # 根布局
│   │   └── page.tsx         # 全部页面组件（SPA）
│   └── lib/
│       └── api.ts           # 后端 API 调用封装（含超时保护）
├── data/
│   ├── bilidigest.db        # SQLite 数据库
│   └── assets/              # 视频资产文件（关键帧等）
└── docs/
    ├── REQUIREMENTS.md      # 题目原始要求
    ├── PRD_BiliDigest.md    # 产品需求文档
    └── PROGRESS.md          # 开发进度记录
```

---

## 开发迭代记录（共 11 次有效迭代）

| 迭代 | 内容 | 反馈 → 改动 |
|------|------|-------------|
| 1 | 脚手架 + 最小数据流 | 端口冲突 → 换端口 |
| 2 | 核心抽取链路（下载 + 转写 + 截帧 + LLM） | 关键帧路由修复、Whisper 安装、字幕 API 降级 |
| 3 | 输出生成 API（5 个端点） | 全部验证通过 |
| 4 | 前端 UI 重构（参考 BibiGPT） | JSON 展示 → 渐进式章节、砍掉低价值 Tab |
| 5 | 体验优化（缓存 + 视频嵌入 + 跳转） | 重复生成 → 缓存优先、视频滚走 → sticky 固定 |
| 6 | 左右分屏布局 | 6:4 不佳 → 恢复 50:50、视频位置居中 |
| 7 | 补齐硬性要求（prompt + 多视频融合） | 验证通过 |
| 8 | README + 测试 + 收尾 | — |
| 9 | Bug 修复：URL 解析丢 `?` 导致 yt-dlp 404、资产库摘要来源从 generation_history 读取 | B站分享链接格式修复、旧进程未正确终止 → 强制 kill 重启 |
| 10 | Whisper → faster-whisper 提速、LLM chunk 扩大到 8000+ tokens | 转写速度 2-4x 提升，总流水线从 3.5min → 2.2min |
| 11 | UI 全面重设计：Fraunces + Plus Jakarta Sans 字体、橙色强调色、奶白侧边栏、暖色调背景 | 深色侧栏 → 奶白；蓝色 → 橙色；冷色调 → 暖米白 |

> 每次迭代的定义：完成一个功能闭环并通过验收，或发现问题并修复验证。

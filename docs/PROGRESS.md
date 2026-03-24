# BiliDigest 开发进度记录

> 更新时间：2026-03-24
> **状态：✅ 项目完成，全部功能已交付**

---

## 1. 已完成功能

### 阶段一：脚手架 + 最小数据流 ✅

| 功能 | 状态 | 说明 |
|------|------|------|
| Next.js + TailwindCSS 前端脚手架 | ✅ | Next.js 16 + React 19 + Tailwind 4 |
| FastAPI 后端项目结构 | ✅ | 含 routers/services 分层 |
| SQLite 初始化 + 全部建表 | ✅ | assets/transcripts/keyframes/structured_knowledge/generation_history + FTS5 |
| B站 API 获取 metadata | ✅ | bilibili.py: get_metadata() |
| 资产 CRUD 路由 | ✅ | POST/GET/DELETE /api/assets |
| 前端首页 + 资产列表 | ✅ | 卡片展示 + 状态标签 + 6s 轮询 |
| Swagger 文档 | ✅ | /docs 可访问 |

### 阶段二：核心抽取链路 ✅

| 功能 | 状态 | 说明 |
|------|------|------|
| yt-dlp 下载视频 + 音频 | ✅ | bilibili.py: download_video(), download_audio() |
| 字幕获取 + Whisper 降级转写 | ✅ | transcriber.py: 带30分钟超时保护 |
| ffmpeg 关键帧截取 | ✅ | keyframe.py: extract_keyframes(), 每60s一帧 |
| LLM Client 封装 | ✅ | llm_client.py: MiniMax API (OpenAI 兼容), 5次重试+指数退避 |
| Map-Reduce 知识提取 | ✅ | knowledge.py: 4种知识类型(arguments/timeline/concepts/conclusions) |
| 异步后台任务 + 状态流转 | ✅ | pending→downloading→transcribing→extracting_frames→analyzing→ready |
| 服务重启自动清理卡死任务 | ✅ | database.py: init_db() 标记 processing→failed |
| POST /api/assets/{bv_id}/reprocess | ✅ | 重新处理失败的资产 |

### 阶段三：输出生成 + 查询 ✅

| 功能 | 状态 | 说明 |
|------|------|------|
| POST /api/generate mode=summary | ✅ | 返回结构化JSON: title + abstract + sections(含keyframe_url/time_refs) |
| POST /api/generate mode=xiaohongshu | ✅ | 返回结构化JSON: title + sections + tags |
| POST /api/generate mode=mindmap | ✅ | 返回树状JSON: tree.name + tree.children |
| POST /api/query | ✅ | LIKE关键词检索 + 均匀采样兜底 + LLM回答 + 引用来源 |
| GET /api/history | ✅ | 历史生成记录, 支持 ?mode= 筛选 |
| GET /api/history/{id} | ✅ | 单条历史详情 |
| GET /api/generate/cache | ✅ | 查询已有缓存结果, 避免重复调LLM |
| 生成结果自动保存 + 去重 | ✅ | 同视频同模式只保留最新一条 |

### 阶段四：前端重构 ✅

| 功能 | 状态 | 说明 |
|------|------|------|
| 左侧导航 + 右侧内容布局 | ✅ | 深色sidebar(220px) + 导航动画 |
| 新总结页（URL输入） | ✅ | BV号验证 + 提交 + 进度提示 |
| 资产库页（视频卡片列表） | ✅ | 封面+标题+状态+删除, hover动画 |
| 资产产出历史页 | ✅ | 按模式筛选, 内容预览(前100字), 点击查看完整内容 |
| 视频详情页 - 左右分屏 | ✅ | 左侧52%: B站iframe播放器(居中) + 视频信息, sticky固定 |
|                        |    | 右侧48%: Tab内容区, 独立滚动 |
| 全文总结 - 渐进式阅读 | ✅ | 摘要(蓝色左边框) + 章节折叠/展开 + 全部展开按钮 |
| 小红书图文 | ✅ | 标题卡 + 分段内容 + 关键帧配图 + tags + 一键复制 |
| 知识树 | ✅ | 交互式可展开树形图, 多层级彩色节点 |
| AI对话 (独立Tab) | ✅ | 多轮对话, 聊天气泡, 预设问题, 引用来源时间戳 |
| 时间戳点击跳转 | ✅ | 更新iframe src实现页内跳转(不开新页面) |
| 内容缓存 | ✅ | 进入Tab自动查缓存, 有则秒加载; 无则显示生成按钮 |
| 重新生成按钮 | ✅ | 每个Tab右上角, 确认后重新调LLM覆盖旧记录 |
| 自定义全屏按钮 | ✅ | hover显示, 调用requestFullscreen() API |
| 后端连接异常提示 | ✅ | 红色横幅 + 重试按钮(不再静默吞掉错误) |
| fetch请求超时保护 | ✅ | 30s默认, 生成180s, 查询120s |

---

## 2. 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| 前端 | Next.js 16 + React 19 + Tailwind 4 | App Router, 单页面应用 |
| 后端 | FastAPI + SQLite + FTS5 | 异步, Swagger自动文档 |
| LLM | MiniMax API (OpenAI兼容) | 5次重试, 指数退避, 120s超时 |
| 视频下载 | yt-dlp | 720p视频 + mp3音频 |
| 转写 | B站字幕API + Whisper base | 优先字幕, 无字幕降级AI转写 |
| 关键帧 | ffmpeg | 每60秒截取一帧 |

## 3. 数据库表

| 表 | 用途 |
|----|------|
| assets | 视频元数据 + 处理状态 |
| transcripts | 转写文本段(含FTS5全文索引) |
| keyframes | 关键帧图片 |
| structured_knowledge | 结构化知识(4种类型) |
| generation_history | 生成历史(summary/xiaohongshu/mindmap) |

## 4. API 端点

| 端点 | 方法 | 用途 |
|------|------|------|
| /api/assets | POST | 提交视频URL, 触发后台处理 |
| /api/assets | GET | 列出所有资产 |
| /api/assets/{bv_id} | GET | 资产详情(含transcripts/keyframes/knowledge) |
| /api/assets/{bv_id} | DELETE | 删除资产 |
| /api/assets/{bv_id}/reprocess | POST | 重新处理失败资产 |
| /api/generate | POST | 生成内容(summary/xiaohongshu/mindmap) |
| /api/generate/cache | GET | 查询缓存的生成结果 |
| /api/query | POST | AI对话查询 |
| /api/history | GET | 历史生成记录(?mode=筛选) |
| /api/history/{id} | GET | 单条历史详情 |
| /health | GET | 健康检查 |

## 5. 当前数据

- 3个已处理视频资产(status=ready)
- BV1P54y1D76p: 288条转写, 12个关键帧, 4种知识
- BV1ge4y1i7k5: 172条转写, 8个关键帧, 4种知识
- BV1PbAczPEiZ: 849条转写, 67个关键帧, 4种知识
- 6条生成历史记录(每视频每模式最新一条)

## 6. 设计特点

- **配色**: 蓝色主色调(#3B82F6) + B站粉色(#fb7299)时间戳强调 + 深色侧边栏
- **渐进式阅读**: 全文总结章节默认折叠, 快速扫描结构后按需展开
- **内容缓存**: 首次生成后缓存, 不重复调LLM, 秒级加载
- **左右分屏**: 视频固定左侧, 内容右侧独立滚动, 时间戳页内跳转
- **多轮AI对话**: 基于视频内容问答, 对话历史保留, 引用来源可追溯

## 7. 已知限制

| 问题 | 说明 |
|------|------|
| B站iframe不支持原生全屏按钮 | 已用requestFullscreen() API替代 |
| Whisper转写速度较慢 | 已加30分钟超时保护 |
| 单视频模式 | 暂不支持多视频合并分析 |

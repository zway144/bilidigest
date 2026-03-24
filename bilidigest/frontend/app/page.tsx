"use client";

import { useState, useEffect, useCallback } from "react";
import {
  createAsset, listAssets, getAsset, deleteAsset,
  generateContent, queryAsset, listHistory, getCachedGeneration, BASE_URL,
} from "@/lib/api";

/* ─── Constants ─────────────────────────────────────── */
const STATUS_LABEL: Record<string, string> = {
  ready: "已就绪", pending: "待处理", downloading: "下载中",
  transcribing: "转写中", extracting_frames: "截帧中",
  analyzing: "分析中", partial: "部分完成", failed: "失败",
};
const STATUS_COLOR: Record<string, string> = {
  ready: "bg-[var(--green)]", partial: "bg-[var(--amber)]", failed: "bg-[var(--red)]",
};
const PROCESSING = ["pending", "downloading", "transcribing", "extracting_frames", "analyzing"];

function fmtDur(sec: number) {
  const m = Math.floor(sec / 60), s = sec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

type Page = "new" | "library" | "detail" | "history";

/* ═══════════════════════════════════════════════════════
   ROOT APP
   ═══════════════════════════════════════════════════════ */
export default function App() {
  const [page, setPage] = useState<Page>("new");
  const [assets, setAssets] = useState<any[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedAsset, setSelectedAsset] = useState<any>(null);
  const [connError, setConnError] = useState("");
  const [historyMode, setHistoryMode] = useState<string | undefined>(undefined);

  const refreshList = useCallback(async () => {
    try {
      const d = await listAssets();
      setAssets(d.assets || []);
      setConnError("");
    } catch (e: any) {
      setConnError(e.message || "无法连接后端");
    }
  }, []);

  useEffect(() => {
    refreshList();
    const t = setInterval(refreshList, 6000);
    return () => clearInterval(t);
  }, [refreshList]);

  const goDetail = useCallback(async (id: string) => {
    setSelectedId(id);
    setPage("detail");
    try { setSelectedAsset(await getAsset(id)); } catch {}
  }, []);

  // Poll detail while processing
  useEffect(() => {
    if (page !== "detail" || !selectedId || !selectedAsset) return;
    if (!PROCESSING.includes(selectedAsset.status)) return;
    const t = setInterval(async () => {
      try { setSelectedAsset(await getAsset(selectedId)); } catch {}
    }, 3000);
    return () => clearInterval(t);
  }, [page, selectedId, selectedAsset?.status]);

  return (
    <div className="h-full flex">
      {/* ── SIDEBAR ── */}
      <aside className="w-[220px] flex-shrink-0 flex flex-col" style={{ background: "var(--sidebar-bg)" }}>
        {/* Logo */}
        <div className="px-5 pt-6 pb-5">
          <h1 className="text-[22px] font-bold tracking-tight gradient-text">BiliDigest</h1>
          <p className="text-[11px] mt-1" style={{ color: "var(--sidebar-text)" }}>B站视频知识资产系统</p>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 space-y-0.5">
          <NavItem
            icon={<IconPen />} label="新总结"
            active={page === "new"}
            onClick={() => setPage("new")}
          />
          <NavItem
            icon={<IconLib />} label="资产库"
            active={page === "library"}
            onClick={() => setPage("library")}
            badge={assets.length || undefined}
          />

          <div className="pt-5 pb-2 px-3">
            <p className="text-[10px] font-medium uppercase tracking-[0.15em]" style={{ color: "var(--sidebar-text)" }}>
              资产产出
            </p>
          </div>
          <NavItem
            icon={<IconDoc />} label="图文总结笔记"
            active={page === "history" && historyMode === "summary"}
            onClick={() => { setHistoryMode("summary"); setPage("history"); }}
          />
          <NavItem
            icon={<IconBook />} label="小红书图文"
            active={page === "history" && historyMode === "xiaohongshu"}
            onClick={() => { setHistoryMode("xiaohongshu"); setPage("history"); }}
          />
          <NavItem
            icon={<IconTree />} label="知识树"
            active={page === "history" && historyMode === "mindmap"}
            onClick={() => { setHistoryMode("mindmap"); setPage("history"); }}
          />
        </nav>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-white/5">
          <p className="text-[10px]" style={{ color: "var(--sidebar-text)" }}>v0.3.0 · BiliDigest</p>
        </div>
      </aside>

      {/* ── MAIN ── */}
      <main className="flex-1 overflow-y-auto">
        {connError && (
          <div className="mx-6 mt-4 bg-red-50 border border-red-200 text-red-600 text-sm px-4 py-3 rounded-xl flex items-center gap-2 animate-in">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M8 1a7 7 0 100 14A7 7 0 008 1zm0 10.5a.75.75 0 110-1.5.75.75 0 010 1.5zM8.75 4.5v4a.75.75 0 01-1.5 0v-4a.75.75 0 011.5 0z"/></svg>
            <span>后端连接异常：{connError}</span>
            <button onClick={refreshList} className="ml-auto text-xs text-red-500 hover:text-red-700 underline">重试</button>
          </div>
        )}

        <div className="animate-in">
          {page === "new" && <NewSummaryPage onCreated={(id) => { refreshList(); goDetail(id); }} />}
          {page === "library" && <LibraryPage assets={assets} onSelect={goDetail} onRefresh={refreshList} />}
          {page === "detail" && selectedAsset && (
            <DetailPage
              asset={selectedAsset}
              onBack={() => setPage("library")}
              onDelete={() => { setSelectedId(null); setSelectedAsset(null); setPage("library"); refreshList(); }}
              onRefresh={() => selectedId && goDetail(selectedId)}
            />
          )}
          {page === "history" && <HistoryPage mode={historyMode} assets={assets} />}
        </div>
      </main>
    </div>
  );
}

/* ── Nav Item ── */
function NavItem({ icon, label, active, onClick, badge }: {
  icon: React.ReactNode; label: string; active: boolean; onClick: () => void; badge?: number;
}) {
  return (
    <button
      onClick={onClick}
      className={`nav-item w-full flex items-center gap-3 px-4 py-2.5 rounded-lg text-[13px] ${
        active
          ? "active text-white font-medium"
          : "hover:bg-white/[0.04]"
      }`}
      style={{
        color: active ? "var(--sidebar-text-active)" : "var(--sidebar-text)",
        background: active ? "var(--sidebar-active)" : undefined,
      }}
    >
      <span className="w-5 h-5 flex items-center justify-center opacity-80">{icon}</span>
      <span className="flex-1 text-left truncate">{label}</span>
      {badge !== undefined && (
        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-white/10">{badge}</span>
      )}
    </button>
  );
}

/* ── SVG Icons ── */
function IconPen() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>;
}
function IconLib() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>;
}
function IconDoc() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>;
}
function IconBook() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M2 3h6a4 4 0 014 4v14a3 3 0 00-3-3H2z"/><path d="M22 3h-6a4 4 0 00-4 4v14a3 3 0 013-3h7z"/></svg>;
}
function IconTree() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="5" r="2"/><line x1="12" y1="7" x2="12" y2="12"/><line x1="12" y1="12" x2="6" y2="16"/><line x1="12" y1="12" x2="18" y2="16"/><circle cx="6" cy="18" r="2"/><circle cx="18" cy="18" r="2"/></svg>;
}


/* ═══════════════════════════════════════════════════════
   PAGE: 新总结
   ═══════════════════════════════════════════════════════ */
function NewSummaryPage({ onCreated }: { onCreated: (id: string) => void }) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    if (!/BV[a-zA-Z0-9]{10}/.test(url)) { setError("请输入包含 BV 号的 B 站视频链接"); return; }
    setError(""); setSubmitting(true);
    try {
      const d = await createAsset(url);
      setUrl("");
      onCreated(d.id);
    } catch (e: any) { setError(e.message); } finally { setSubmitting(false); }
  };

  return (
    <div className="max-w-2xl mx-auto px-8 py-20">
      <div className="mb-10">
        <h2 className="text-3xl font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>
          提取视频知识
        </h2>
        <p className="text-sm mt-2" style={{ color: "var(--text-secondary)" }}>
          粘贴 B 站视频链接，自动提取转写文本、关键帧和结构化知识
        </p>
      </div>

      <div className="bg-white rounded-2xl border p-7 shadow-sm" style={{ borderColor: "var(--border)" }}>
        <textarea
          className="w-full border rounded-xl px-4 py-3.5 text-sm outline-none resize-none h-28 input-glow transition-all"
          style={{ borderColor: "var(--border)" }}
          placeholder="粘贴 B 站视频链接，例如 https://www.bilibili.com/video/BVxxxxxxxxxx&#10;&#10;也可以直接粘贴 B 站分享文本"
          value={url}
          onChange={e => { setUrl(e.target.value); setError(""); }}
          onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
        />
        {error && (
          <p className="mt-3 text-sm text-[var(--red)] flex items-center gap-1.5">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M8 1a7 7 0 100 14A7 7 0 008 1zm0 10.5a.75.75 0 110-1.5.75.75 0 010 1.5zM8.75 4.5v4a.75.75 0 01-1.5 0v-4a.75.75 0 011.5 0z"/></svg>
            {error}
          </p>
        )}
        <button
          onClick={submit}
          disabled={submitting}
          className="mt-5 w-full py-3 rounded-xl text-white text-sm font-medium transition-all"
          style={{
            background: submitting ? "var(--text-muted)" : "var(--accent)",
            cursor: submitting ? "not-allowed" : "pointer",
          }}
          onMouseOver={e => !submitting && ((e.target as HTMLElement).style.background = "var(--accent-hover)")}
          onMouseOut={e => !submitting && ((e.target as HTMLElement).style.background = "var(--accent)")}
        >
          {submitting ? (
            <span className="flex items-center justify-center gap-2">
              <span className="spinner" style={{ width: 16, height: 16, borderWidth: 2, borderTopColor: "#fff" }} />
              提交中...
            </span>
          ) : "开始提取"}
        </button>
      </div>

      {/* Tips */}
      <div className="mt-8 grid grid-cols-3 gap-4">
        {[
          { icon: "🎯", title: "转写文本", desc: "自动获取字幕或 AI 转写" },
          { icon: "📸", title: "关键帧", desc: "智能提取视频中的关键画面" },
          { icon: "🧠", title: "知识结构", desc: "LLM 提取论点、概念、时间线" },
        ].map(t => (
          <div key={t.title} className="bg-white/60 backdrop-blur rounded-xl p-4 border" style={{ borderColor: "var(--border)" }}>
            <span className="text-2xl">{t.icon}</span>
            <p className="text-sm font-medium mt-2" style={{ color: "var(--text-primary)" }}>{t.title}</p>
            <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>{t.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}


/* ═══════════════════════════════════════════════════════
   PAGE: 资产库
   ═══════════════════════════════════════════════════════ */
function LibraryPage({ assets, onSelect, onRefresh }: { assets: any[]; onSelect: (id: string) => void; onRefresh: () => void }) {
  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!confirm("确认删除？")) return;
    try { await deleteAsset(id); onRefresh(); } catch {}
  };

  return (
    <div className="max-w-5xl mx-auto px-8 py-10">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">资产库</h2>
          <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>{assets.length} 个视频资产</p>
        </div>
      </div>

      {assets.length === 0 ? (
        <div className="text-center py-24">
          <div className="text-5xl mb-4 opacity-40">📹</div>
          <p style={{ color: "var(--text-muted)" }}>还没有视频资产</p>
          <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>前往「新总结」提交视频链接</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {assets.map((a, i) => (
            <div
              key={a.id}
              onClick={() => onSelect(a.id)}
              className="card-hover bg-white rounded-xl border overflow-hidden cursor-pointer"
              style={{ borderColor: "var(--border)", animationDelay: `${i * 50}ms` }}
            >
              <div className="flex gap-4 p-4">
                <div className="w-36 h-24 flex-shrink-0 rounded-lg overflow-hidden bg-gray-100">
                  {a.thumbnail_url ? (
                    <img src={a.thumbnail_url} className="w-full h-full object-cover" referrerPolicy="no-referrer" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-gray-300 text-3xl">▶</div>
                  )}
                </div>
                <div className="flex-1 min-w-0 flex flex-col">
                  <p className="font-medium text-sm leading-snug line-clamp-2" style={{ color: "var(--text-primary)" }}>
                    {a.title || a.id}
                  </p>
                  <p className="text-xs mt-1.5" style={{ color: "var(--text-secondary)" }}>
                    {a.author} · {fmtDur(a.duration)}
                  </p>
                  <div className="flex items-center gap-3 mt-auto pt-2">
                    <span className="flex items-center gap-1.5 text-xs" style={{ color: "var(--text-secondary)" }}>
                      <span className={`w-2 h-2 rounded-full ${STATUS_COLOR[a.status] || "bg-[var(--blue)]"} ${PROCESSING.includes(a.status) ? "pulse-dot" : ""}`} />
                      {STATUS_LABEL[a.status] || a.status}
                    </span>
                    <button
                      onClick={(e) => handleDelete(e, a.id)}
                      className="text-xs ml-auto opacity-0 group-hover:opacity-100 transition-opacity"
                      style={{ color: "var(--text-muted)" }}
                      onMouseOver={e => (e.target as HTMLElement).style.color = "var(--red)"}
                      onMouseOut={e => (e.target as HTMLElement).style.color = "var(--text-muted)"}
                    >
                      删除
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


/* ═══════════════════════════════════════════════════════
   PAGE: 视频详情（Step 3 核心页面）
   ═══════════════════════════════════════════════════════ */
function DetailPage({ asset, onBack, onDelete, onRefresh }: {
  asset: any; onBack: () => void; onDelete: () => void; onRefresh: () => void;
}) {
  const [tab, setTab] = useState<"summary" | "xiaohongshu" | "mindmap" | "chat">("summary");
  const [genData, setGenData] = useState<Record<string, any>>({});
  const [genLoading, setGenLoading] = useState<Record<string, boolean>>({});
  const [genError, setGenError] = useState<Record<string, string>>({});
  const [cacheChecked, setCacheChecked] = useState<Record<string, boolean>>({});
  const [userPrompt, setUserPrompt] = useState("");

  // AI Chat - 多轮对话
  const [chatHistory, setChatHistory] = useState<{role: string; content: string; refs?: any[]}[]>([]);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);

  // 切换 Tab 时自动加载缓存
  useEffect(() => {
    if (tab === "chat" || cacheChecked[tab] || genData[tab] || genLoading[tab]) return;
    setCacheChecked(p => ({ ...p, [tab]: true }));
    setGenLoading(p => ({ ...p, [tab]: true }));
    getCachedGeneration(asset.id, tab).then(cached => {
      if (cached) {
        setGenData(p => ({ ...p, [tab]: cached }));
        setGenLoading(p => ({ ...p, [tab]: false }));
      } else {
        setGenLoading(p => ({ ...p, [tab]: false }));
        // 无缓存，不自动生成，让用户点击按钮
      }
    }).catch(() => {
      setGenLoading(p => ({ ...p, [tab]: false }));
    });
  }, [tab, asset.id]);

  const handleGenerate = async (mode: string, force = false, prompt?: string) => {
    if (!force && genData[mode]) return;
    setGenLoading(p => ({ ...p, [mode]: true }));
    setGenError(p => ({ ...p, [mode]: "" }));
    try {
      const d = await generateContent([asset.id], mode, prompt || undefined);
      setGenData(p => ({ ...p, [mode]: d }));
    } catch (e: any) {
      setGenError(p => ({ ...p, [mode]: e.message }));
    } finally {
      setGenLoading(p => ({ ...p, [mode]: false }));
    }
  };

  const handleAsk = async () => {
    if (!question.trim()) return;
    const q = question.trim();
    setChatHistory(prev => [...prev, { role: "user", content: q }]);
    setQuestion("");
    setAsking(true);
    try {
      const d = await queryAsset([asset.id], q);
      setChatHistory(prev => [...prev, { role: "assistant", content: d.answer, refs: d.references }]);
    } catch (e: any) {
      setChatHistory(prev => [...prev, { role: "assistant", content: `查询失败: ${e.message}` }]);
    } finally { setAsking(false); }
  };

  const handleDeleteAsset = async () => {
    if (!confirm("确认删除该资产？")) return;
    try { await deleteAsset(asset.id); onDelete(); } catch {}
  };

  // iframe src state for in-page time jumping
  const [iframeSrc, setIframeSrc] = useState(`//player.bilibili.com/player.html?bvid=${asset.id}&autoplay=0&danmaku=0&high_quality=1`);

  // 时间戳点击：页面内跳转（更新 iframe src）
  const handleTimeClick = (timeStr: string) => {
    const parts = timeStr.split(":");
    const sec = parseInt(parts[0]) * 60 + parseInt(parts[1] || "0");
    setIframeSrc(`//player.bilibili.com/player.html?bvid=${asset.id}&autoplay=1&danmaku=0&high_quality=1&t=${sec}`);
  };

  // 重新生成（带 prompt）
  const handleRegenerate = (mode: string) => {
    if (!confirm("重新生成将覆盖当前内容，确定？")) return;
    handleGenerate(mode, true, userPrompt);
  };

  const isProcessing = PROCESSING.includes(asset.status);

  return (
    <div className="flex h-full">
      {/* ── LEFT PANEL: Video + Info (sticky, fixed height) ── */}
      <div className="w-[52%] flex-shrink-0 sticky top-0 h-[100vh] overflow-visible border-r relative" style={{ borderColor: "var(--border)" }}>
        {/* Back bar - absolute top */}
        <div className="absolute top-0 left-0 right-0 z-10 flex items-center gap-3 px-5 py-2.5" style={{ background: "var(--bg)" }}>
          <button onClick={onBack} className="flex items-center gap-1.5 text-sm transition-colors" style={{ color: "var(--text-secondary)" }}
            onMouseOver={e => (e.currentTarget.style.color = "var(--accent)")}
            onMouseOut={e => (e.currentTarget.style.color = "var(--text-secondary)")}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
            返回
          </button>
          <div className="flex-1" />
          <button onClick={handleDeleteAsset} className="text-[11px] px-2.5 py-1 rounded-lg border transition-colors" style={{ color: "var(--text-muted)", borderColor: "var(--border)" }}
            onMouseOver={e => { e.currentTarget.style.color = "var(--red)"; e.currentTarget.style.borderColor = "var(--red)"; }}
            onMouseOut={e => { e.currentTarget.style.color = "var(--text-muted)"; e.currentTarget.style.borderColor = "var(--border)"; }}
          >删除</button>
        </div>

        {/* Video + Info - vertically centered */}
        <div className="h-full flex flex-col justify-center px-4">
          {/* Video Player */}
          <div className="bg-black flex-shrink-0 rounded-lg overflow-hidden">
            <iframe
              key={iframeSrc}
              src={iframeSrc}
              width="100%"
              height="340"
              frameBorder="0"
              allowFullScreen={true}
              allow="fullscreen; autoplay; encrypted-media"
              sandbox="allow-scripts allow-same-origin allow-popups allow-presentation allow-fullscreen"
              referrerPolicy="no-referrer"
            />
          </div>

          {/* Video Info */}
          <div className="px-5 py-4">
            <h1 className="text-base font-bold leading-snug" style={{ color: "var(--text-primary)" }}>{asset.title}</h1>
            <p className="text-sm mt-2" style={{ color: "var(--text-secondary)" }}>{asset.author} · {fmtDur(asset.duration)}</p>
            <div className="flex items-center gap-2 mt-2.5">
              <span className={`w-2 h-2 rounded-full ${STATUS_COLOR[asset.status] || "bg-[var(--blue)]"} ${isProcessing ? "pulse-dot" : ""}`} />
              <span className="text-xs" style={{ color: "var(--text-secondary)" }}>{STATUS_LABEL[asset.status] || asset.status}</span>
              {isProcessing && <span className="text-xs ml-1 pulse-dot" style={{ color: "var(--blue)" }}>处理中...</span>}
              {asset.status === "failed" && asset.error_message && (
                <span className="text-xs ml-1" style={{ color: "var(--red)" }}>{asset.error_message}</span>
              )}
            </div>
            {asset.description && (
              <p className="text-xs mt-3 leading-relaxed" style={{ color: "var(--text-muted)" }}>{asset.description.slice(0, 200)}</p>
            )}
            <a href={`https://www.bilibili.com/video/${asset.id}`} target="_blank" rel="noopener noreferrer"
              className="mt-3 inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-colors"
              style={{ color: "var(--blue)", background: "var(--blue-light)" }}
            >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
            在B站观看
          </a>
          </div>
        </div>
      </div>

      {/* ── RIGHT PANEL: Tabs + Content (scrollable) ── */}
      <div className="flex-1 h-[100vh] overflow-y-auto">
        {!isProcessing && asset.status !== "failed" ? (
          <div className="p-6">
            {/* Tab bar */}
            <div className="flex gap-0 border-b mb-6 sticky top-0 bg-[var(--bg)] z-10 -mx-6 px-6" style={{ borderColor: "var(--border)" }}>
              {([
                { key: "summary", label: "全文总结" },
                { key: "xiaohongshu", label: "小红书图文" },
                { key: "mindmap", label: "知识树" },
                { key: "chat", label: "💬 AI对话" },
              ] as const).map(t => (
                <button
                  key={t.key}
                  onClick={() => setTab(t.key)}
                  className={`tab-btn px-5 py-3 text-sm font-medium transition-colors ${tab === t.key ? "active" : ""}`}
                  style={{ color: tab === t.key ? "var(--accent)" : "var(--text-secondary)" }}
                >
                  {t.label}
                </button>
              ))}
            </div>

            {/* Tab Content */}
            <div className="animate-in">
              {tab !== "chat" ? (
                <div>
                  {/* Prompt 输入 + 重新生成 */}
                  <div className="flex items-center gap-2 mb-4">
                    <input
                      value={userPrompt}
                      onChange={e => setUserPrompt(e.target.value)}
                      placeholder="输入侧重点，例如：侧重可行动的建议 / 只关注技术细节 / 用通俗语言解释..."
                      className="flex-1 border rounded-lg px-3 py-2 text-xs outline-none input-glow transition-all"
                      style={{ borderColor: "var(--border)" }}
                      onKeyDown={e => { if (e.key === "Enter") { genData[tab] ? handleRegenerate(tab) : handleGenerate(tab, false, userPrompt); } }}
                    />
                    {!genData[tab] && !genLoading[tab] ? (
                      <button onClick={() => handleGenerate(tab, false, userPrompt)}
                        className="flex-shrink-0 flex items-center gap-1.5 text-xs px-4 py-2 rounded-lg text-white transition-colors"
                        style={{ background: "var(--accent)" }}
                        onMouseOver={e => (e.currentTarget.style.background = "var(--accent-hover)")}
                        onMouseOut={e => (e.currentTarget.style.background = "var(--accent)")}
                      >生成</button>
                    ) : genData[tab] && !genLoading[tab] ? (
                      <button onClick={() => handleRegenerate(tab)}
                        className="flex-shrink-0 flex items-center gap-1.5 text-xs px-3 py-2 rounded-lg border transition-colors"
                        style={{ color: "var(--text-muted)", borderColor: "var(--border)" }}
                        onMouseOver={e => { e.currentTarget.style.color = "var(--accent)"; e.currentTarget.style.borderColor = "var(--accent)"; }}
                        onMouseOut={e => { e.currentTarget.style.color = "var(--text-muted)"; e.currentTarget.style.borderColor = "var(--border)"; }}
                      >🔄 重新生成</button>
                    ) : null}
                  </div>
                  <TabContent
                    mode={tab}
                    data={genData[tab]}
                    loading={genLoading[tab]}
                    error={genError[tab]}
                    onGenerate={() => handleGenerate(tab, false, userPrompt)}
                    asset={asset}
                    onTimeClick={handleTimeClick}
                  />
                </div>
              ) : (
                /* AI Chat Tab */
                <div className="bg-white rounded-2xl border flex flex-col" style={{ borderColor: "var(--border)", minHeight: "500px" }}>
                  <div className="px-5 py-3 border-b flex items-center gap-2" style={{ borderColor: "var(--border)" }}>
                    <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>AI 对话 · 向视频提问</span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: "var(--blue-light)", color: "var(--blue)" }}>
                      基于 {asset.title?.slice(0, 20)}
                    </span>
                  </div>

                  <div className="flex-1 p-5 space-y-4 overflow-y-auto">
                    {chatHistory.length === 0 && (
                      <div className="text-center py-12">
                        <p className="text-sm" style={{ color: "var(--text-muted)" }}>输入问题开始对话，AI 将基于视频内容回答</p>
                        <div className="flex flex-wrap justify-center gap-2 mt-4">
                          {["视频的核心观点是什么？", "总结一下主要内容", "有哪些可操作的建议？"].map(q => (
                            <button key={q} onClick={() => setQuestion(q)} className="text-xs px-3 py-1.5 rounded-full border transition-colors"
                              style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
                              onMouseOver={e => { e.currentTarget.style.borderColor = "var(--accent)"; e.currentTarget.style.color = "var(--accent)"; }}
                              onMouseOut={e => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.color = "var(--text-secondary)"; }}
                            >{q}</button>
                          ))}
                        </div>
                      </div>
                    )}
                    {chatHistory.map((msg, i) => (
                      <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                        <div className="max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed" style={{
                          background: msg.role === "user" ? "var(--accent)" : "#f3f4f6",
                          color: msg.role === "user" ? "white" : "var(--text-primary)",
                        }}>
                          <div className="whitespace-pre-wrap">{msg.content}</div>
                          {msg.refs?.length ? (
                            <div className="mt-2 pt-2 border-t border-gray-200 space-y-1">
                              {msg.refs.slice(0, 3).map((r: any, j: number) => (
                                <p key={j} className="text-[11px] opacity-70 cursor-pointer" onClick={() => handleTimeClick(fmtTime(r.start_time))}>
                                  <span className="underline">{fmtTime(r.start_time)}</span> {r.text?.slice(0, 40)}
                                </p>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      </div>
                    ))}
                    {asking && (
                      <div className="flex justify-start">
                        <div className="rounded-2xl px-4 py-3" style={{ background: "#f3f4f6" }}>
                          <div className="flex items-center gap-2">
                            <span className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />
                            <span className="text-xs" style={{ color: "var(--text-muted)" }}>思考中...</span>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="px-5 py-3 border-t flex gap-2" style={{ borderColor: "var(--border)" }}>
                    <input value={question} onChange={e => setQuestion(e.target.value)}
                      onKeyDown={e => e.key === "Enter" && !asking && handleAsk()}
                      placeholder="输入你的问题..."
                      className="flex-1 border rounded-xl px-4 py-2.5 text-sm outline-none input-glow transition-all"
                      style={{ borderColor: "var(--border)" }}
                    />
                    <button onClick={handleAsk} disabled={asking || !question.trim()}
                      className="px-5 py-2.5 rounded-xl text-white text-sm font-medium transition-all"
                      style={{ background: asking || !question.trim() ? "var(--text-muted)" : "var(--accent)" }}
                    >发送</button>
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="p-6">
            <div className="text-center py-20">
              {isProcessing ? (
                <>
                  <div className="spinner mx-auto mb-4" />
                  <p className="text-sm" style={{ color: "var(--text-secondary)" }}>视频正在处理中，请稍候...</p>
                </>
              ) : (
                <p className="text-sm" style={{ color: "var(--red)" }}>{asset.error_message || "处理失败"}</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function fmtTime(sec: number) {
  const m = Math.floor(sec / 60), s = Math.floor(sec % 60);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

/* ── Tab Content (生成 + 渲染) ── */
function TabContent({ mode, data, loading, error, onGenerate, asset, onTimeClick }: {
  mode: string; data: any; loading: boolean; error: string; onGenerate: () => void; asset: any; onTimeClick?: (t: string) => void;
}) {
  if (loading) {
    return (
      <div className="text-center py-20">
        <div className="spinner mx-auto mb-4" style={{ width: 32, height: 32 }} />
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          正在生成{mode === "summary" ? "全文总结" : mode === "xiaohongshu" ? "小红书图文" : "知识树"}...
        </p>
        <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>首次生成可能需要 30-60 秒</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-16">
        <p className="text-sm" style={{ color: "var(--red)" }}>{error}</p>
        <button onClick={onGenerate} className="mt-3 text-sm underline" style={{ color: "var(--accent)" }}>重试</button>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="text-center py-16">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          点击下方按钮生成{mode === "summary" ? "全文总结" : mode === "xiaohongshu" ? "小红书图文" : "知识树"}
        </p>
        <button
          onClick={onGenerate}
          className="mt-4 px-6 py-2.5 rounded-xl text-white text-sm font-medium transition-all"
          style={{ background: "var(--accent)" }}
          onMouseOver={e => (e.target as HTMLElement).style.background = "var(--accent-hover)"}
          onMouseOut={e => (e.target as HTMLElement).style.background = "var(--accent)"}
        >
          生成{mode === "summary" ? "全文总结" : mode === "xiaohongshu" ? "小红书图文" : "知识树"}
        </button>
      </div>
    );
  }

  // 渲染生成结果
  if (mode === "summary") return <SummaryView data={data} onTimeClick={onTimeClick} />;
  if (mode === "xiaohongshu") return <XiaohongshuView data={data} />;
  if (mode === "mindmap") return <MindmapView data={data} />;
  return null;
}

/* ── Summary 渲染 ── */
function SummaryView({ data, onTimeClick }: { data: any; onTimeClick?: (t: string) => void }) {
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  const allExpanded = data.sections?.every((_: any, i: number) => expanded[i]);

  const toggleAll = () => {
    if (allExpanded) {
      setExpanded({});
    } else {
      const all: Record<number, boolean> = {};
      data.sections?.forEach((_: any, i: number) => { all[i] = true; });
      setExpanded(all);
    }
  };

  return (
    <div className="space-y-4">
      {/* 摘要 - 始终可见 */}
      <div className="bg-white rounded-2xl border-l-4 shadow-sm p-6" style={{ borderLeftColor: "var(--blue)", borderTop: "1px solid var(--border)", borderRight: "1px solid var(--border)", borderBottom: "1px solid var(--border)" }}>
        <h2 className="text-lg font-bold mb-2 tracking-tight" style={{ color: "var(--text-primary)" }}>{data.title}</h2>
        <p className="text-[15px] leading-[1.8]" style={{ color: "var(--text-secondary)" }}>{data.abstract}</p>
      </div>

      {/* 全部展开/折叠 */}
      {data.sections?.length > 0 && (
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>{data.sections.length} 个章节</p>
          <button onClick={toggleAll} className="text-xs px-3 py-1 rounded-lg border transition-colors"
            style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
          >{allExpanded ? "全部折叠" : "全部展开"}</button>
        </div>
      )}

      {/* 章节列表 - 可折叠 */}
      {data.sections?.map((s: any, i: number) => {
        const isOpen = expanded[i];
        return (
          <div key={i} className="bg-white rounded-xl border overflow-hidden transition-shadow" style={{ borderColor: "var(--border)", boxShadow: isOpen ? "0 4px 16px rgba(0,0,0,0.06)" : "none" }}>
            {/* 章节标题行 - 始终可见，可点击 */}
            <div
              className="flex items-center gap-3 px-5 py-3.5 cursor-pointer transition-colors"
              style={{ background: isOpen ? "var(--blue-light)" : "transparent" }}
              onClick={() => setExpanded(p => ({ ...p, [i]: !p[i] }))}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                className="flex-shrink-0 transition-transform" style={{ transform: isOpen ? "rotate(90deg)" : "rotate(0)", color: "var(--text-muted)" }}>
                <polyline points="9 18 15 12 9 6"/>
              </svg>
              <span className="time-tag flex-shrink-0" onClick={(e) => { e.stopPropagation(); onTimeClick?.(s.time); }}>{s.time}</span>
              <span className="text-[15px] font-semibold truncate" style={{ color: "var(--text-primary)" }}>{s.title}</span>
            </div>

            {/* 展开内容 */}
            {isOpen && (
              <div className="px-5 pb-5 pt-2 fade-in">
                <div className="flex flex-col gap-4">
                  {s.keyframe_url && (
                    <img
                      src={`${BASE_URL}${s.keyframe_url}`}
                      className="w-full max-w-md rounded-lg shadow-sm cursor-pointer"
                      onClick={() => onTimeClick?.(s.time)}
                    />
                  )}
                  <p className="text-[15px] leading-[1.8]" style={{ color: "var(--text-secondary)" }}>{s.content}</p>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ── 小红书渲染 ── */
function XiaohongshuView({ data }: { data: any }) {
  const copyAll = () => {
    const text = `${data.title}\n\n` +
      data.sections?.map((s: any) => `${s.subtitle}\n${s.content}`).join("\n\n") +
      `\n\n${data.tags?.join(" ")}`;
    navigator.clipboard.writeText(text);
  };

  return (
    <div className="max-w-xl mx-auto space-y-4">
      {/* 标题 */}
      <div className="bg-gradient-to-r from-pink-50 via-orange-50 to-rose-50 rounded-2xl border border-pink-100 p-6 text-center">
        <h2 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>{data.title}</h2>
        <button onClick={copyAll} className="mt-3 text-xs px-3 py-1 rounded-full border border-pink-200 text-pink-500 hover:bg-pink-50 transition-colors">
          📋 一键复制全文
        </button>
      </div>

      {/* Sections */}
      {data.sections?.map((s: any, i: number) => (
        <div key={i} className="bg-white rounded-2xl border overflow-hidden" style={{ borderColor: "var(--border)" }}>
          {s.keyframe_url && (
            <img src={`${BASE_URL}${s.keyframe_url}`} className="w-full aspect-video object-cover" />
          )}
          <div className="p-5">
            <h3 className="font-semibold mb-2" style={{ color: "var(--text-primary)" }}>{s.subtitle}</h3>
            <p className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>{s.content}</p>
          </div>
        </div>
      ))}

      {/* Tags */}
      {data.tags?.length > 0 && (
        <div className="flex flex-wrap gap-2 px-1">
          {data.tags.map((tag: string, i: number) => (
            <span key={i} className="text-sm px-3 py-1 rounded-full bg-pink-50 text-pink-500">{tag}</span>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── 知识树渲染 ── */
function MindmapView({ data }: { data: any }) {
  const tree = data.tree;
  if (!tree) return <p className="text-center py-12" style={{ color: "var(--text-muted)" }}>无数据</p>;

  return (
    <div className="bg-white rounded-2xl border p-6" style={{ borderColor: "var(--border)" }}>
      <TreeNode node={tree} depth={0} />
    </div>
  );
}

function TreeNode({ node, depth }: { node: any; depth: number }) {
  const [open, setOpen] = useState(depth < 2);
  const hasChildren = node.children?.length > 0;
  const colors = ["var(--accent)", "var(--blue)", "var(--green)", "var(--amber)"];
  const dotColor = colors[depth % colors.length];

  return (
    <div className={depth > 0 ? "ml-6 border-l-2 pl-4" : ""} style={{ borderColor: depth > 0 ? "var(--border)" : undefined }}>
      <div
        className="flex items-start gap-2 py-1.5 cursor-pointer group"
        onClick={() => hasChildren && setOpen(!open)}
      >
        {hasChildren ? (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
            className="mt-0.5 flex-shrink-0 transition-transform" style={{ transform: open ? "rotate(90deg)" : "rotate(0)", color: dotColor }}>
            <polyline points="9 18 15 12 9 6"/>
          </svg>
        ) : (
          <span className="w-2 h-2 rounded-full flex-shrink-0 mt-1.5" style={{ background: dotColor }} />
        )}
        <span className={`text-sm ${depth === 0 ? "font-bold text-base" : depth === 1 ? "font-semibold" : ""}`}
          style={{ color: "var(--text-primary)" }}>
          {node.name}
        </span>
      </div>
      {open && hasChildren && (
        <div className="fade-in">
          {node.children.map((child: any, i: number) => (
            <TreeNode key={i} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}


/* ═══════════════════════════════════════════════════════
   PAGE: 历史记录
   ═══════════════════════════════════════════════════════ */
function HistoryPage({ mode, assets }: { mode?: string; assets?: any[] }) {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedItem, setSelectedItem] = useState<any>(null);

  // 多视频选择生成
  const [selectedAssetIds, setSelectedAssetIds] = useState<string[]>([]);
  const [genPrompt, setGenPrompt] = useState("");
  const [generating, setGenerating] = useState(false);
  const [genResult, setGenResult] = useState<any>(null);

  const readyAssets = (assets || []).filter((a: any) => a.status === "ready");

  const toggleAsset = (id: string) => {
    setSelectedAssetIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  };

  const handleMultiGenerate = async () => {
    if (!selectedAssetIds.length || !mode) return;
    setGenerating(true); setGenResult(null);
    try {
      const d = await generateContent(selectedAssetIds, mode, genPrompt || undefined);
      setGenResult(d);
      // 刷新历史列表
      listHistory(mode).then(d => setItems(d.items || [])).catch(() => {});
    } catch (e: any) {
      alert(`生成失败: ${e.message}`);
    } finally { setGenerating(false); }
  };

  useEffect(() => {
    setLoading(true);
    setSelectedItem(null);
    setGenResult(null);
    listHistory(mode).then(d => {
      setItems(d.items || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [mode]);

  const modeLabel = mode === "summary" ? "图文总结笔记" : mode === "xiaohongshu" ? "小红书图文" : mode === "mindmap" ? "知识树" : "所有记录";

  // 查看单条记录详情
  if (selectedItem) {
    return (
      <div className="max-w-5xl mx-auto px-8 py-8 animate-in">
        <button onClick={() => setSelectedItem(null)} className="flex items-center gap-1.5 text-sm mb-6 transition-colors" style={{ color: "var(--text-secondary)" }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
          返回列表
        </button>
        <div className="mb-6">
          <h2 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>{selectedItem.title || modeLabel}</h2>
          <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>{selectedItem.asset_titles} · {selectedItem.created_at}</p>
        </div>
        {selectedItem.mode === "summary" && <SummaryView data={selectedItem.content} />}
        {selectedItem.mode === "xiaohongshu" && <XiaohongshuView data={selectedItem.content} />}
        {selectedItem.mode === "mindmap" && <MindmapView data={selectedItem.content} />}
      </div>
    );
  }

  // 查看刚刚生成的结果
  if (genResult) {
    return (
      <div className="max-w-5xl mx-auto px-8 py-8 animate-in">
        <button onClick={() => setGenResult(null)} className="flex items-center gap-1.5 text-sm mb-6 transition-colors" style={{ color: "var(--text-secondary)" }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
          返回列表
        </button>
        <div className="mb-6">
          <h2 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>{genResult.title || modeLabel}</h2>
          <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>刚刚生成 · {selectedAssetIds.length} 个视频</p>
        </div>
        {mode === "summary" && <SummaryView data={genResult} />}
        {mode === "xiaohongshu" && <XiaohongshuView data={genResult} />}
        {mode === "mindmap" && <MindmapView data={genResult} />}
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-8 py-10">
      <div className="mb-6">
        <h2 className="text-2xl font-bold tracking-tight">{modeLabel}</h2>
        <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>选择视频资产生成内容，或查看历史记录</p>
      </div>

      {/* 多视频选择 + 生成 */}
      {mode && readyAssets.length > 0 && (
        <div className="bg-white rounded-2xl border p-5 mb-6" style={{ borderColor: "var(--border)" }}>
          <p className="text-sm font-medium mb-3" style={{ color: "var(--text-primary)" }}>选择视频资产</p>
          <div className="space-y-2 mb-4">
            {readyAssets.map((a: any) => (
              <label key={a.id} className="flex items-center gap-3 p-2.5 rounded-lg cursor-pointer transition-colors"
                style={{ background: selectedAssetIds.includes(a.id) ? "var(--blue-light)" : "transparent" }}
              >
                <input type="checkbox" checked={selectedAssetIds.includes(a.id)} onChange={() => toggleAsset(a.id)}
                  className="w-4 h-4 rounded accent-[var(--accent)]" />
                <div className="w-12 h-8 rounded overflow-hidden bg-gray-100 flex-shrink-0">
                  {a.thumbnail_url && <img src={a.thumbnail_url} className="w-full h-full object-cover" referrerPolicy="no-referrer" />}
                </div>
                <span className="text-sm truncate" style={{ color: "var(--text-primary)" }}>{a.title}</span>
              </label>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <input value={genPrompt} onChange={e => setGenPrompt(e.target.value)}
              placeholder="可选：输入侧重点，例如侧重对比分析 / 提取共同观点..."
              className="flex-1 border rounded-lg px-3 py-2 text-xs outline-none input-glow"
              style={{ borderColor: "var(--border)" }}
            />
            <button onClick={handleMultiGenerate}
              disabled={generating || !selectedAssetIds.length}
              className="flex-shrink-0 px-4 py-2 rounded-lg text-white text-xs font-medium transition-colors"
              style={{ background: generating || !selectedAssetIds.length ? "var(--text-muted)" : "var(--accent)" }}
            >
              {generating ? (
                <span className="flex items-center gap-1.5">
                  <span className="spinner" style={{ width: 12, height: 12, borderWidth: 1.5, borderTopColor: "#fff" }} />
                  生成中...
                </span>
              ) : `生成${modeLabel}（${selectedAssetIds.length}个视频）`}
            </button>
          </div>
        </div>
      )}

      {/* 历史记录列表 */}
      <div className="mb-4">
        <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>历史记录</p>
      </div>

      {loading ? (
        <div className="text-center py-16"><div className="spinner mx-auto" /></div>
      ) : items.length === 0 ? (
        <div className="text-center py-16">
          <div className="text-4xl mb-3 opacity-40">📝</div>
          <p style={{ color: "var(--text-muted)" }}>暂无{modeLabel}记录</p>
          <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>选择视频资产并点击生成</p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item, i) => (
            <div key={item.id} onClick={() => setSelectedItem(item)}
              className="card-hover bg-white rounded-xl border p-4 cursor-pointer animate-in"
              style={{ borderColor: "var(--border)", animationDelay: `${i * 40}ms` }}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[10px] px-2 py-0.5 rounded-full flex-shrink-0" style={{
                      background: item.mode === "summary" ? "var(--blue-light)" : item.mode === "xiaohongshu" ? "#fef2f2" : "#f0fdf4",
                      color: item.mode === "summary" ? "var(--blue)" : item.mode === "xiaohongshu" ? "var(--accent)" : "var(--green)",
                    }}>
                      {item.mode === "summary" ? "总结" : item.mode === "xiaohongshu" ? "小红书" : "知识树"}
                    </span>
                    <p className="text-sm font-medium truncate" style={{ color: "var(--text-primary)" }}>
                      {item.title || item.asset_titles || `记录 #${item.id}`}
                    </p>
                  </div>
                  <p className="text-xs" style={{ color: "var(--text-secondary)" }}>{item.asset_titles}</p>
                  {item.preview && <p className="text-xs mt-1.5 line-clamp-2 leading-relaxed" style={{ color: "var(--text-muted)" }}>{item.preview}</p>}
                </div>
                <p className="text-[10px] flex-shrink-0" style={{ color: "var(--text-muted)" }}>{item.created_at?.slice(0, 16)}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

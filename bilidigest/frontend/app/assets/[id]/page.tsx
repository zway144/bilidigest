"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getAsset, deleteAsset, BASE_URL } from "@/lib/api";

const STATUS_LABEL: Record<string, string> = {
  ready: "已就绪", pending: "待处理", downloading: "下载中",
  transcribing: "转写中", extracting_frames: "截帧中",
  analyzing: "分析中", partial: "部分完成", failed: "失败",
};
const STATUS_STYLES: Record<string, string> = {
  ready: "bg-green-100 text-green-700", pending: "bg-blue-100 text-blue-700",
  downloading: "bg-blue-100 text-blue-700", transcribing: "bg-blue-100 text-blue-700",
  extracting_frames: "bg-blue-100 text-blue-700", analyzing: "bg-blue-100 text-blue-700",
  partial: "bg-yellow-100 text-yellow-700", failed: "bg-red-100 text-red-700",
};

const PROCESSING = ["pending", "downloading", "transcribing", "extracting_frames", "analyzing"];

function formatDuration(sec: number) {
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  if (h > 0) return `${h}:${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}`;
  return `${m}:${String(s).padStart(2,"0")}`;
}

const TABS = ["转写文本", "关键帧", "知识结构", "生成输出", "查询"] as const;

export default function AssetDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [asset, setAsset] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<typeof TABS[number]>("转写文本");
  const [deleting, setDeleting] = useState(false);

  const fetchAsset = async () => {
    try {
      const data = await getAsset(id);
      setAsset(data);
    } catch {
      setAsset(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAsset();
  }, [id]);

  // 处理中时每3秒轮询
  useEffect(() => {
    if (!asset) return;
    if (!PROCESSING.includes(asset.status)) return;
    const t = setInterval(fetchAsset, 3000);
    return () => clearInterval(t);
  }, [asset?.status]);

  const handleDelete = async () => {
    if (!confirm("确认删除该资产？")) return;
    setDeleting(true);
    try {
      await deleteAsset(id);
      router.push("/");
    } catch {
      setDeleting(false);
    }
  };

  if (loading) return <div className="min-h-screen bg-gray-50 flex items-center justify-center text-gray-400">加载中...</div>;
  if (!asset) return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center gap-4">
      <p className="text-gray-500">资产不存在或已删除</p>
      <button onClick={() => router.push("/")} className="text-blue-600 underline text-sm">返回首页</button>
    </div>
  );

  return (
    <main className="min-h-screen bg-gray-50">
      {/* 顶栏 */}
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-3">
        <button onClick={() => router.push("/")} className="text-gray-400 hover:text-gray-700 text-sm">← 返回</button>
        <span className="text-xl font-bold text-blue-600">BiliDigest</span>
      </header>

      <div className="max-w-5xl mx-auto px-4 py-6">
        {/* 视频元信息 */}
        <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6 flex gap-5">
          {asset.thumbnail_url && (
            <img src={asset.thumbnail_url} alt={asset.title} className="w-40 h-24 object-cover rounded-lg flex-shrink-0" referrerPolicy="no-referrer" />
          )}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-3">
              <h1 className="text-lg font-semibold text-gray-900 leading-snug">{asset.title}</h1>
              <button onClick={handleDelete} disabled={deleting} className="text-xs text-red-400 hover:text-red-600 flex-shrink-0">
                {deleting ? "删除中..." : "删除"}
              </button>
            </div>
            <p className="text-sm text-gray-500 mt-1">{asset.author} · {formatDuration(asset.duration)}</p>
            <div className="flex flex-wrap gap-2 mt-2">
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_STYLES[asset.status] || "bg-gray-100 text-gray-600"}`}>
                {STATUS_LABEL[asset.status] || asset.status}
              </span>
              {asset.tags?.map((tag: string) => (
                <span key={tag} className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">{tag}</span>
              ))}
            </div>
            {PROCESSING.includes(asset.status) && (
              <p className="text-xs text-blue-500 mt-2 animate-pulse">正在处理中，每3秒自动刷新...</p>
            )}
            {asset.status === "failed" && asset.error_message && (
              <p className="text-xs text-red-500 mt-2">错误：{asset.error_message}</p>
            )}
          </div>
        </div>

        {/* Tab 导航 */}
        <div className="flex border-b border-gray-200 mb-4 bg-white rounded-t-xl overflow-hidden">
          {TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-5 py-3 text-sm font-medium transition-colors ${
                activeTab === tab
                  ? "text-blue-600 border-b-2 border-blue-600 bg-blue-50"
                  : "text-gray-500 hover:text-gray-700 hover:bg-gray-50"
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Tab 内容 */}
        <div className="bg-white rounded-b-xl border border-gray-200 border-t-0 p-5 min-h-64">
          {activeTab === "转写文本" && (
            <TranscriptTab transcripts={asset.transcripts} status={asset.status} />
          )}
          {activeTab === "关键帧" && (
            <KeyframesTab keyframes={asset.keyframes} status={asset.status} />
          )}
          {activeTab === "知识结构" && (
            <KnowledgeTab knowledge={asset.structured_knowledge} status={asset.status} />
          )}
          {activeTab === "生成输出" && (
            <div className="text-center text-gray-400 py-16">生成输出功能将在阶段三实现</div>
          )}
          {activeTab === "查询" && (
            <div className="text-center text-gray-400 py-16">查询功能将在阶段三实现</div>
          )}
        </div>
      </div>
    </main>
  );
}

function TranscriptTab({ transcripts, status }: { transcripts: any[]; status: string }) {
  if (PROCESSING.includes(status)) return <EmptyProcessing text="转写文本生成中..." />;
  if (!transcripts?.length) return <EmptyState text="暂无转写文本" />;
  return (
    <div className="space-y-3 max-h-[600px] overflow-y-auto">
      {transcripts.map((t: any) => (
        <div key={t.id} className="flex gap-3">
          <span className="text-xs text-gray-400 w-28 flex-shrink-0 pt-0.5">
            [{formatTime(t.start_time)}-{formatTime(t.end_time)}]
          </span>
          <p className="text-sm text-gray-700 leading-relaxed">
            {t.text}
            {t.source === "whisper" && (
              <span className="ml-2 text-xs bg-purple-100 text-purple-600 px-1.5 py-0.5 rounded">AI转写</span>
            )}
          </p>
        </div>
      ))}
    </div>
  );
}

function KeyframesTab({ keyframes, status }: { keyframes: any[]; status: string }) {
  const [enlarged, setEnlarged] = useState<string | null>(null);
  if (PROCESSING.includes(status)) return <EmptyProcessing text="关键帧截取中..." />;
  if (!keyframes?.length) return <EmptyState text="暂无关键帧" />;
  return (
    <>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
        {keyframes.map((kf: any) => (
          <div key={kf.id} className="cursor-pointer group" onClick={() => setEnlarged(kf.url)}>
            <img src={`${BASE_URL}${kf.url}`} alt={`${formatTime(kf.timestamp)}`}
              className="w-full aspect-video object-cover rounded-lg group-hover:opacity-90 transition-opacity" />
            <p className="text-xs text-gray-400 mt-1 text-center">{formatTime(kf.timestamp)}</p>
          </div>
        ))}
      </div>
      {enlarged && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50" onClick={() => setEnlarged(null)}>
          <img src={`${BASE_URL}${enlarged}`} className="max-w-4xl max-h-screen rounded-xl" />
        </div>
      )}
    </>
  );
}

function KnowledgeTab({ knowledge, status }: { knowledge: any; status: string }) {
  if (PROCESSING.includes(status)) return <EmptyProcessing text="知识结构提取中..." />;
  if (!knowledge || Object.keys(knowledge).length === 0) return <EmptyState text="暂无知识结构" />;
  const sections = [
    { key: "arguments", label: "核心论点" },
    { key: "timeline", label: "内容时间线" },
    { key: "concepts", label: "关键概念" },
    { key: "conclusions", label: "结论与建议" },
  ];
  return (
    <div className="space-y-4">
      {sections.map(({ key, label }) => knowledge[key] && (
        <details key={key} open className="border border-gray-200 rounded-lg">
          <summary className="px-4 py-3 font-medium text-gray-800 cursor-pointer select-none hover:bg-gray-50">{label}</summary>
          <div className="px-4 pb-4">
            <pre className="text-xs text-gray-600 whitespace-pre-wrap bg-gray-50 rounded p-3 overflow-x-auto">
              {JSON.stringify(knowledge[key], null, 2)}
            </pre>
          </div>
        </details>
      ))}
    </div>
  );
}

function EmptyProcessing({ text }: { text: string }) {
  return <div className="text-center text-blue-400 py-16 animate-pulse">{text}</div>;
}
function EmptyState({ text }: { text: string }) {
  return <div className="text-center text-gray-400 py-16">{text}</div>;
}
function formatTime(sec: number) {
  const m = Math.floor(sec / 60), s = Math.floor(sec % 60);
  return `${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}`;
}

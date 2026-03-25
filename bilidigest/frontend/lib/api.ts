export const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** 带超时的 fetch 封装，默认 30 秒，支持外部 AbortSignal */
async function fetchWithTimeout(url: string, options?: RequestInit & { signal?: AbortSignal }, timeoutMs = 30000): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  // 外部 signal 联动：外部取消时同步取消本次请求
  const externalSignal = options?.signal;
  let onExternalAbort: (() => void) | undefined;
  if (externalSignal) {
    if (externalSignal.aborted) { clearTimeout(timer); throw new Error("请求已取消"); }
    onExternalAbort = () => controller.abort();
    externalSignal.addEventListener("abort", onExternalAbort);
  }

  try {
    const { signal: _, ...rest } = options || {};
    return await fetch(url, { ...rest, signal: controller.signal });
  } catch (e: any) {
    if (e.name === "AbortError") {
      if (externalSignal?.aborted) throw new Error("请求已取消");
      throw new Error("请求超时，请检查后端是否正在运行");
    }
    throw new Error(`网络错误：无法连接到后端服务 (${e.message})`);
  } finally {
    clearTimeout(timer);
    if (externalSignal && onExternalAbort) externalSignal.removeEventListener("abort", onExternalAbort);
  }
}

/* ── Assets ── */

export async function createAsset(url: string) {
  const res = await fetchWithTimeout(`${BASE_URL}/api/assets`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  }, 60000);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "提交失败");
  return data;
}

export async function listAssets() {
  const res = await fetchWithTimeout(`${BASE_URL}/api/assets`);
  if (!res.ok) throw new Error("获取列表失败");
  return res.json();
}

export async function getAsset(bvId: string) {
  const res = await fetchWithTimeout(`${BASE_URL}/api/assets/${bvId}`);
  if (!res.ok) throw new Error("获取资产失败");
  return res.json();
}

export async function deleteAsset(bvId: string) {
  const res = await fetchWithTimeout(`${BASE_URL}/api/assets/${bvId}`, { method: "DELETE" });
  if (!res.ok) throw new Error("删除失败");
  return res.json();
}

/* ── Generate ── */

export async function generateContent(assetIds: string[], mode: string, userPrompt?: string, signal?: AbortSignal) {
  const res = await fetchWithTimeout(`${BASE_URL}/api/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ asset_ids: assetIds, mode, user_prompt: userPrompt || null }),
    signal,
  }, 180000);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "生成失败");
  return data;
}

export async function getCachedGeneration(assetId: string, mode: string) {
  const res = await fetchWithTimeout(`${BASE_URL}/api/generate/cache?asset_id=${assetId}&mode=${mode}`);
  if (!res.ok) return null;
  const data = await res.json();
  return data.cached ? data : null;
}

/* ── Query ── */

export async function queryAsset(assetIds: string[], question: string, signal?: AbortSignal) {
  const res = await fetchWithTimeout(`${BASE_URL}/api/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ asset_ids: assetIds, question }),
    signal,
  }, 120000);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "查询失败");
  return data;
}

/* ── History ── */

export async function listHistory(mode?: string) {
  const qs = mode ? `?mode=${mode}` : "";
  const res = await fetchWithTimeout(`${BASE_URL}/api/history${qs}`);
  if (!res.ok) throw new Error("获取历史记录失败");
  return res.json();
}

export async function getHistory(id: number) {
  const res = await fetchWithTimeout(`${BASE_URL}/api/history/${id}`);
  if (!res.ok) throw new Error("获取历史记录详情失败");
  return res.json();
}

export async function deleteHistory(id: number) {
  const res = await fetchWithTimeout(`${BASE_URL}/api/history/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("删除失败");
  return res.json();
}

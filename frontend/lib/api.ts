export type Result = {
  type_id: string;
  axes: Record<string, string>;
  summary: string;
  strengths: string[];
  adjustments: string[];
  conversation_tip: string;
  limitations: string[];
  evidence_status: 'fixture' | 'ai_draft_unreviewed';
};
export type Analysis = {
  analysis_id: string;
  result: Result;
};
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(
    () => controller.abort(),
    path === 'analyses' ? 110000 : path === 'health' ? 30000 : 8000,
  );
  try {
    const r = await fetch('/api/v1/' + path, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...options.headers },
      cache: 'no-store',
      signal: controller.signal,
    });
    if (!r.ok) {
      const e = await r.json().catch(() => null);
      throw new Error(e?.error?.message || '연결하지 못했어요. 잠시 후 다시 시도해 주세요.');
    }
    return r.status === 204 ? (undefined as T) : await r.json();
  } catch (e) {
    if (e instanceof Error && e.name === 'AbortError')
      throw new Error('응답이 늦어지고 있어요. 잠시 후 다시 시도해 주세요.');
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

export type SpicyTitle = { id: string; text: string };
export type Spicy = { titles: Record<string, SpicyTitle>; notes: Record<string, string> };
export type Answer = {
  question: string;
  status: 'answered' | 'declined_offtopic' | 'declined_adult';
  text: string;
};
export type Result = {
  schema_version: '1.0' | '1.1';
  type_id: string;
  axes: Record<string, string>;
  summary: string;
  strengths: string[];
  adjustments: string[];
  conversation_tip: string;
  limitations: string[];
  evidence_status: 'fixture' | 'ai_draft_unreviewed';
  spicy?: Spicy;
};
export type Analysis = {
  analysis_id: string;
  result: Result;
  /** Reply to the optional question. Never part of a share link. */
  answer?: Answer;
  share_code?: string;
};
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(
    () => controller.abort(),
    path === 'analyses' ? 110000 : path === 'health' || path === 'shared' ? 30000 : 8000,
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
export type Shared = { result: Result; created_at: string };

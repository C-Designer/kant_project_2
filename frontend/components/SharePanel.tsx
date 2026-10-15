'use client';
import { useState } from 'react';
import { Analysis } from '@/lib/api';
import { shareUrl } from '@/lib/share';

type Notice = { text: string; failed: boolean };

export default function SharePanel({ analysis }: { analysis: Analysis }) {
  const [notice, setNotice] = useState<Notice | null>(null);
  if (!analysis.share_code) return null;
  // Rendered only after an analysis arrives in the browser, so window is defined here.
  const link = shareUrl(window.location.origin, analysis.share_code);
  const canSend = typeof navigator.share === 'function';

  function announce(text: string, failed = false) {
    // Clear first so screen readers announce the same message again on a repeat click.
    setNotice(null);
    requestAnimationFrame(() => setNotice({ text, failed }));
  }
  async function copy() {
    try {
      await navigator.clipboard.writeText(link);
      announce('링크를 복사했어요.');
    } catch {
      announce('자동 복사가 안 돼요. 위 링크를 직접 선택해 복사해 주세요.', true);
    }
  }
  async function send() {
    try {
      await navigator.share({ title: '러브코드 결과', url: link });
    } catch (e) {
      // Closing the share sheet is not an error; anything else falls back to copying.
      if ((e as Error).name !== 'AbortError')
        announce('다른 앱으로 보내지 못했어요. 링크 복사를 이용해 주세요.', true);
    }
  }

  return (
    <section className="share-panel" aria-labelledby="share-heading">
      <h2 id="share-heading">결과를 함께 보고 싶다면</h2>
      <p>
        링크 안에 이 결과 화면이 그대로 담겨요. 서버에 따로 저장하지 않아서, 링크를 받은 사람은
        누구나 볼 수 있고 보낸 뒤에는 되돌릴 수 없어요. 생년월일·시각·성별·MBTI 원문은 담기지
        않아요.
      </p>
      <div className="share-values">
        <label>
          공유 링크
          <input readOnly value={link} onFocus={(e) => e.currentTarget.select()} />
        </label>
        <button className="button secondary" onClick={copy}>
          링크 복사
        </button>
        {canSend && (
          <button className="button secondary" onClick={send}>
            다른 앱으로 보내기
          </button>
        )}
      </div>
      <p role="status" className={notice?.failed ? 'status error' : 'status'}>
        {notice?.text}
      </p>
    </section>
  );
}

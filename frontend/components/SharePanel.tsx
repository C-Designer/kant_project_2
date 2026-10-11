'use client';
import { useRef, useState } from 'react';
import { Analysis, Saved, api, token } from '@/lib/api';
export default function SharePanel({ analysis }: { analysis: Analysis }) {
  const [consent, setConsent] = useState(false),
    [busy, setBusy] = useState(false),
    [saved, setSaved] = useState<Saved | null>(null),
    [message, setMessage] = useState('');
  const keys = useRef<{
    read: string;
    remove: string;
  } | null>(null);
  const lock = useRef(false);
  async function share() {
    if (!analysis || !consent || lock.current) return;
    lock.current = true;
    setBusy(true);
    setMessage('');
    keys.current ??= { read: token(), remove: token() };
    try {
      const s = await api<Saved>('results', {
        method: 'POST',
        body: JSON.stringify({
          save_ticket: analysis.save_ticket,
          read_token: keys.current.read,
          delete_token: keys.current.remove,
        }),
      });
      setSaved(s);
      setMessage('공유 링크를 만들었어요. 삭제용 정보도 따로 보관해 주세요.');
    } catch (e) {
      try {
        const s = await api<Saved>('results', {
          headers: { Authorization: 'Bearer ' + keys.current.read },
        });
        setSaved(s);
        setMessage('이미 저장된 결과를 확인했어요.');
      } catch {
        setMessage((e as Error).message + ' 같은 키로 다시 시도할 수 있어요.');
      }
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  async function copy(text: string, label: string) {
    try {
      await navigator.clipboard.writeText(text);
      setMessage(label + '를 복사했어요.');
    } catch {
      setMessage('자동 복사가 안 돼요. 내용을 직접 선택해 복사해 주세요.');
    }
  }
  return (
    <section className="share-panel">
      <h2>함께 읽고, 이야기해 보세요</h2>
      <p>
        공유하면 결과만 7일 동안 저장해요. 링크를 가진 사람은 결과를 볼 수 있어요. 입력 정보는
        저장하지 않아요.
      </p>
      {!saved ? (
        <>
          <label className="check">
            <input
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
            />
            결과를 7일 동안 저장하고 공유할게요.
          </label>
          <button className="button primary" disabled={!consent || busy} onClick={share}>
            {busy ? '링크 만드는 중…' : '공유 링크 만들기'}
          </button>
          <small>결과를 연 뒤 10분 안에 만들 수 있어요.</small>
        </>
      ) : (
        <div className="share-values">
          <label>
            공유 링크
            <input
              readOnly
              value={
                typeof window !== 'undefined'
                  ? window.location.origin + '/r#' + keys.current?.read
                  : ''
              }
            />
          </label>
          <button
            className="button secondary"
            onClick={() => copy(window.location.origin + '/r#' + keys.current?.read, '공유 링크')}
          >
            링크 복사
          </button>
          <label>
            삭제용 정보 · 공유하지 마세요
            <input readOnly value={saved.result_id + '.' + keys.current?.remove} />
          </label>
          <button
            className="button secondary"
            onClick={() => copy(saved.result_id + '.' + keys.current?.remove, '삭제용 정보')}
          >
            삭제용 정보 복사
          </button>
          <p className="small-note">
            이 화면을 닫으면 삭제용 정보를 다시 받을 수 없어요. 따로 보관한 뒤 ‘공유 관리’에서
            사용하세요.
          </p>
        </div>
      )}
      <p role="status" className="status">
        {message}
      </p>
    </section>
  );
}

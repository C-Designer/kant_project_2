'use client';
import { useRef, useState } from 'react';
import { api } from '@/lib/api';
export default function Manage() {
  const [key, setKey] = useState(''),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState('');
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  function ask(e: React.FormEvent) {
    e.preventDefault();
    setMessage('');
    if (
      !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.[A-Za-z0-9_-]{43}$/i.test(
        key.trim(),
      )
    ) {
      setMessage('저장할 때 받은 삭제용 정보를 그대로 붙여넣어 주세요.');
      return;
    }
    dialog.current?.showModal();
  }
  async function remove() {
    if (busy) return;
    setBusy(true);
    try {
      const [id, t] = key.trim().split('.');
      await api('results/' + id, { method: 'DELETE', headers: { Authorization: 'Bearer ' + t } });
      setMessage('삭제 요청을 처리했어요. 해당 결과와 공유 링크는 더 이상 사용할 수 없어요.');
      setKey('');
    } catch {
      setMessage('삭제하지 못했어요. 삭제용 정보와 연결 상태를 확인하고 다시 시도해 주세요.');
    } finally {
      setBusy(false);
      dialog.current?.close();
    }
  }
  return (
    <main id="main" className="manage-main">
      <p className="eyebrow">내가 공유한 이야기</p>
      <h1>공유 결과 관리</h1>
      <p>
        공유할 때 따로 보관한 삭제용 정보를 입력해 주세요.
        <br />
        공유 링크만으로는 삭제할 수 없어요.
      </p>
      <form onSubmit={ask}>
        <label htmlFor="delete-key">삭제용 정보</label>
        <textarea
          id="delete-key"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          required
          autoComplete="off"
          spellCheck={false}
          placeholder="저장할 때 복사한 정보를 붙여넣어 주세요."
        />
        <button className="button primary" ref={trigger} type="submit">
          공유 결과 삭제
        </button>
      </form>
      <p role="status" className="status">
        {message}
      </p>
      <aside className="notice">
        <strong>삭제용 정보를 잃어버렸나요?</strong>
        <p>
          계정이 없어 다시 발급할 수는 없어요. 공유 결과는 저장한 날부터 7일이 지나면 자동으로
          만료돼요.
        </p>
      </aside>
      <dialog
        ref={dialog}
        onClose={() => trigger.current?.focus()}
        onCancel={(e) => {
          if (busy) e.preventDefault();
        }}
        aria-labelledby="delete-title"
      >
        <h2 id="delete-title">공유 결과를 삭제할까요?</h2>
        <p>
          삭제하면 공유 링크로도 다시 볼 수 없어요.
          <br />이 작업은 되돌릴 수 없어요.
        </p>
        <div className="dialog-actions">
          <button
            className="button secondary"
            autoFocus
            disabled={busy}
            onClick={() => dialog.current?.close()}
          >
            돌아가기
          </button>
          <button className="button primary" disabled={busy} onClick={remove}>
            {busy ? '삭제하는 중…' : '삭제하기'}
          </button>
        </div>
      </dialog>
    </main>
  );
}

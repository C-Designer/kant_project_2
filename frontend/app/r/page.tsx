'use client';
import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import ResultView from '@/components/ResultView';
import BrandMark from '@/components/BrandMark';
import { Shared, api } from '@/lib/api';
import { codeFromHash } from '@/lib/share';

export default function SharedResultPage() {
  const [shared, setShared] = useState<Shared | null>(null),
    [error, setError] = useState(''),
    [retry, setRetry] = useState(0);
  const code = useRef<string | null>(null);
  const focusNext = useRef(false);
  const resultTop = useRef<HTMLDivElement>(null);
  const errorHeading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    const onHashChange = () => {
      const target = window.location.hash.slice(1);
      if (target && document.getElementById(target)) {
        // An in-page anchor such as the skip link (#main): keep the result, and put the code
        // back in the address bar so reloading or copying the URL still works.
        if (code.current) history.replaceState(null, '', '#' + code.current);
        return;
      }
      // Another link was pasted into this tab. Re-register the entry so Next's router owns it
      // and Back from another page restores this result.
      history.replaceState(null, '', window.location.href);
      setRetry((n) => n + 1);
    };
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);
  useEffect(() => {
    let active = true;
    setShared(null);
    setError('');
    // After a retry or a pasted link, focus whatever this load produces (not the old content).
    const settle = (apply: () => void) => {
      focusNext.current = retry > 0;
      apply();
    };
    code.current = codeFromHash(window.location.hash);
    if (!code.current) {
      settle(() => setError('링크 주소가 올바르지 않아요. 받은 링크 전체를 다시 열어 주세요.'));
      return;
    }
    api<Shared>('shared', { headers: { 'X-Share-Code': code.current } })
      .then((value) => {
        if (active) settle(() => setShared(value));
      })
      .catch((e) => {
        if (active) settle(() => setError((e as Error).message));
      });
    return () => {
      active = false;
    };
  }, [retry]);
  useEffect(() => {
    if (!focusNext.current || (!shared && !error)) return;
    focusNext.current = false;
    if (shared) resultTop.current?.focus();
    else errorHeading.current?.focus();
  }, [shared, error]);
  return (
    <main id="main" className="form-main">
      {shared ? (
        <div ref={resultTop} tabIndex={-1}>
          <ResultView result={shared.result} sharedAt={shared.created_at} />
          <p className="center">
            <Link className="button primary" href="/test">
              우리 관계도 알아보기 →
            </Link>
          </p>
        </div>
      ) : error ? (
        <section className="empty">
          <BrandMark />
          <h1 ref={errorHeading} tabIndex={-1}>
            결과를 열 수 없어요
          </h1>
          <p role="alert">{error}</p>
          <button className="button secondary" onClick={() => setRetry((n) => n + 1)}>
            다시 확인
          </button>
          <Link className="text-button" href="/test">
            새로운 궁합 알아보기 →
          </Link>
        </section>
      ) : (
        <p role="status" className="center">
          공유받은 결과를 불러오고 있어요…
        </p>
      )}
    </main>
  );
}

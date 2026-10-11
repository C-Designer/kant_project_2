'use client';
import { useState, useRef, useEffect } from 'react';
import ResultView from '@/components/ResultView';
import PersonFields from '@/components/PersonFields';
import PersonReview from '@/components/PersonReview';
import { Analysis, api } from '@/lib/api';
export default function Test() {
  const [analysis, setAnalysis] = useState<Analysis | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  const resultTop = useRef<HTMLDivElement>(null);
  const lock = useRef(false);
  const [ready, setReady] = useState(false);
  const [verification, setVerification] = useState(false);
  const [operation, setOperation] = useState<'demo' | 'analysis'>('demo');
  const [step, setStep] = useState(0);
  const [review, setReview] = useState<Record<string, string>>({});
  const stepHeading = useRef<HTMLHeadingElement>(null);
  const autoDemo = useRef(false);
  function moveStep(next: number) {
    setStep(next);
    setError('');
    setTimeout(() => {
      stepHeading.current?.focus();
      stepHeading.current?.scrollIntoView({ behavior: 'instant', block: 'start' });
    }, 0);
  }
  useEffect(() => {
    if (new URLSearchParams(window.location.search).get('demo') === '1' && !autoDemo.current) {
      autoDemo.current = true;
      void demo();
    }
  }, []);
  useEffect(() => {
    api<{
      analysis_ready: boolean;
      verification_mode: boolean;
    }>('health')
      .then((h) => {
        setReady(h.analysis_ready);
        setVerification(h.verification_mode);
      })
      .catch(() => setReady(false));
  }, []);
  function showResult(value: Analysis) {
    setAnalysis(value);
    setTimeout(() => {
      resultTop.current?.focus();
      resultTop.current?.scrollIntoView({ behavior: 'instant' });
    }, 0);
  }
  async function demo() {
    if (lock.current) return;
    setOperation('demo');
    lock.current = true;
    setBusy(true);
    setError('');
    try {
      showResult(await api<Analysis>('demo-analysis', { method: 'POST', body: '{}' }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (lock.current) return;
    const values = new FormData(e.currentTarget);
    if (step < 2) {
      setReview(Object.fromEntries([...values].map(([k, v]) => [k, String(v)])));
      moveStep(step + 1);
      return;
    }
    if (!ready) {
      setError('실제 분석은 준비 중이에요. 예시 결과를 먼저 살펴보세요.');
      return;
    }
    setOperation('analysis');
    lock.current = true;
    setBusy(true);
    setError('');
    const f = values;
    const person = (id: string) => ({
      gender: f.get(id + 'gender'),
      birth_date: f.get(id + 'date'),
      birth_time: f.get(id + 'unknown') ? null : f.get(id + 'time'),
      mbti: f.get(id + 'mbti'),
    });
    try {
      showResult(
        await api<Analysis>('analyses', {
          method: 'POST',
          body: JSON.stringify({
            person_a: person('a'),
            person_b: person('b'),
            external_processing_consent: f.get('external-consent') === 'on',
          }),
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      lock.current = false;
    }
  }
  return (
    <main id="main" className="form-main">
      {verification && (
        <aside className="notice">
          <strong>모의 API 검증 모드</strong>
          <p>실제 OpenAI 응답이 아닙니다. 연결 흐름만 검증합니다.</p>
        </aside>
      )}
      {analysis && (
        <>
          <div tabIndex={-1} ref={resultTop}>
            <ResultView result={analysis.result} analysis={analysis} />
          </div>
          <button
            className="text-button"
            onClick={() => {
              setAnalysis(null);
              setError('');
            }}
          >
            ← 입력으로 돌아가기
          </button>
        </>
      )}
      <div hidden={!!analysis} className="atlas-form">
        <div className="form-intro">
          <p className="eyebrow">우리 사이 알아보기</p>
          <h1>
            두 사람의 이야기를
            <br />
            시작해 볼까요?
          </h1>
          <p>한 사람씩 알려주세요. 입력한 정보는 서비스 DB에 저장하지 않아요.</p>
        </div>
        <aside className="notice">
          <strong>{ready ? '어떤 결과인지 먼저 볼까요?' : '실제 분석은 아직 준비 중이에요'}</strong>
          <p>
            {ready
              ? '입력 없이 예시 결과를 살펴볼 수 있어요.'
              : '지금은 예시 결과와 공유 기능을 이용할 수 있어요.'}
          </p>
          <button type="button" className="text-button" disabled={busy} onClick={demo}>
            {busy && operation === 'demo' ? '예시 여는 중…' : '입력 없이 예시 결과 보기 →'}
          </button>
        </aside>
        <ol className="form-steps" aria-label="입력 진행 단계">
          {['첫 번째 사람', '두 번째 사람', '확인하기'].map((label, i) => (
            <li key={label} aria-current={step === i ? 'step' : undefined}>
              <span>{i + 1}</span>
              {label}
            </li>
          ))}
        </ol>
        <h2 className="step-heading" tabIndex={-1} ref={stepHeading}>
          {['먼저, 첫 번째 사람', '이제, 두 번째 사람', '마지막으로 확인해 주세요'][step]}
        </h2>
        <form onSubmit={submit} aria-busy={busy}>
          <PersonFields id="a" title="첫 번째 사람 정보" active={step === 0} />
          <PersonFields id="b" title="두 번째 사람 정보" active={step === 1} />
          {step < 2 && (
            <p className="small-note">
              양력·한국 표준시 기준이에요. 태어난 시각을 모르면 ‘몰라요’를 선택해 주세요.
            </p>
          )}
          {step === 2 && (
            <>
              <PersonReview review={review} onEdit={moveStep} />
              <label className="check consent">
                <input type="checkbox" required />두 사람의 입력 동의를 확인했고, 참고·오락용
                해석임을 이해했어요.
              </label>
              {ready && (
                <label className="check consent">
                  <input type="checkbox" name="external-consent" required />두 사람의 사주 계산
                  결과와 MBTI를 OpenAI로 보내 관계 해석을 생성하는 데 동의해요. 생년월일·시각 원문은
                  보내지 않아요.
                </label>
              )}
            </>
          )}
          <div className="step-actions">
            {step > 0 && (
              <button
                type="button"
                className="button secondary"
                disabled={busy}
                onClick={() => moveStep(step - 1)}
              >
                이전
              </button>
            )}
            <button
              className="button primary"
              disabled={busy || (step === 2 && !ready)}
              type="submit"
            >
              {busy
                ? '두 사람의 관계를 살펴보는 중…'
                : step === 0
                  ? '두 번째 사람 입력하기 →'
                  : step === 1
                    ? '입력 내용 확인하기 →'
                    : '우리 궁합 알아보기'}
            </button>
          </div>
          {step === 2 && (
            <p className="small-note">
              {ready
                ? '분석에 최대 2분 정도 걸릴 수 있어요.'
                : '실제 분석이 준비되면 이용할 수 있어요. 지금은 위의 예시 결과를 살펴보세요.'}
            </p>
          )}
        </form>
      </div>
      <p className="error" role="alert">
        {error}
      </p>
      {error && !analysis && (
        <button className="button secondary wide" disabled={busy} onClick={demo}>
          예시 결과 보기 →
        </button>
      )}
    </main>
  );
}

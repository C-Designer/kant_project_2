'use client';
import { useEffect, useState } from 'react';

export default function ResultLoading({ demo }: { demo: boolean }) {
  const [longWait, setLongWait] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setLongWait(true), 15000);
    return () => clearTimeout(timer);
  }, []);
  return (
    <div className="result-loading">
      <div className="loading-heading" role="status" aria-live="polite" aria-atomic="true">
        <span className="loading-circle" aria-hidden="true" />
        <h1>{demo ? '예시 결과를 불러오고 있어요' : '두 사람의 관계를 살펴보고 있어요'}</h1>
        <p>
          {longWait
            ? '조금 더 시간이 걸리고 있어요. 이 화면에서 잠시 기다려 주세요.'
            : demo
              ? '결과 화면을 곧 보여드릴게요.'
              : '관계유형과 해설을 준비하고 있어요. 잠시만 기다려 주세요.'}
        </p>
      </div>
      <div className="result-card" aria-label="관계 결과" aria-busy="true">
        <div aria-hidden="true" className="result-skeleton">
          <div className="result-type">
            <div className="skeleton-shape skeleton-art" />
            <div className="skeleton-copy">
              <div className="skeleton-shape skeleton-short" />
              <div className="skeleton-shape skeleton-title" />
              <div className="skeleton-shape" />
            </div>
          </div>
          <div className="result-cover">
            <div className="skeleton-copy">
              <div className="skeleton-shape skeleton-short" />
              <div className="skeleton-shape skeleton-title" />
              <div className="skeleton-shape" />
            </div>
            <div className="skeleton-axes">
              {[0, 1, 2, 3].map((i) => (
                <div className="skeleton-shape" key={i} />
              ))}
            </div>
          </div>
          {[0, 1].map((i) => (
            <div className="result-section skeleton-copy" key={i}>
              <div className="skeleton-shape skeleton-short" />
              <div className="skeleton-shape" />
              <div className="skeleton-shape" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

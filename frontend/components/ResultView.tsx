'use client';
import Link from 'next/link';
import SpicyCards from './SpicyCards';
import SpicyGate from './SpicyGate';
import TypeIllustration from './TypeIllustration';
import types from '@/data/relationship-types.json';
import { Answer, Result } from '@/lib/api';
import { axisEntries } from '@/lib/relationship';
import { formatDate } from '@/lib/share';
export default function ResultView({
  result,
  sharedAt,
  answer,
  adultConfirmed = false,
}: {
  result: Result;
  sharedAt?: string;
  answer?: Answer;
  /** The requester ticked the adult check on the input form; the gate starts ticked. */
  adultConfirmed?: boolean;
}) {
  const relationshipType = types.find((type) => type.id === result.type_id);
  const fixture = result.evidence_status === 'fixture';
  return (
    <div className="result-wrap">
      {/* A real analysis needs no banner; label only fixed examples and links someone sent. */}
      {(fixture || sharedAt) && (
        <div className="notice">
          <strong>
            {[sharedAt && '공유받은 결과', fixture && '예시 결과 · 실제 분석 아님']
              .filter(Boolean)
              .join(' · ')}
          </strong>
          {fixture && (
            <p>결과 화면을 살펴보기 위한 고정 예시예요. 입력한 정보로 계산한 결과가 아니에요.</p>
          )}
        </div>
      )}
      <article className="result-card">
        {relationshipType && (
          <Link
            href={`/types/${relationshipType.slug}`}
            className="result-type-link"
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`${relationshipType.name} 유형 자세히 보기 (새 탭)`}
          >
            <div className="result-type-art">
              <TypeIllustration type={relationshipType} />
            </div>
            <div className="result-type-copy">
              <p>두 사람의 관계유형</p>
              <h1>{relationshipType.name}</h1>
              <p>{relationshipType.title}</p>
              <span>
                유형 자세히 보기 · 새 탭 <span aria-hidden="true">↗</span>
              </span>
            </div>
          </Link>
        )}
        <div className="result-cover">
          <div className="result-intro">
            <p className="eyebrow">두 사람의 관계 스타일</p>
            <h2>{result.summary}</h2>
          </div>
          <dl className="result-axes">
            {axisEntries(result.axes).map((axis) => (
              <div key={axis.key}>
                <dt>{axis.label}</dt>
                <dd>{axis.value}</dd>
              </div>
            ))}
          </dl>
        </div>
        <section className="result-section">
          <h2>함께라서 좋은 점</h2>
          {result.strengths.map((t, i) => (
            <p key={t}>
              <b aria-hidden="true">0{i + 1}</b>
              {t}
            </p>
          ))}
        </section>
        <section className="result-section">
          <h2>조금씩 맞춰 갈 점</h2>
          {result.adjustments.map((t, i) => (
            <p key={t}>
              <b aria-hidden="true">0{i + 1}</b>
              {t}
            </p>
          ))}
        </section>
        <section className="conversation">
          <span>오늘의 대화 한마디</span>
          <p>{result.conversation_tip}</p>
        </section>
        {answer && (
          <section className="answer">
            <span>두 사람이 물어본 것</span>
            <p className="answer-question">Q. {answer.question}</p>
            <p className={answer.status === 'answered' ? '' : 'answer-declined'}>{answer.text}</p>
          </section>
        )}
        {result.spicy && (
          <SpicyGate title="매운맛 궁합" preconfirmed={adultConfirmed && !sharedAt}>
            <SpicyCards spicy={result.spicy} />
          </SpicyGate>
        )}
        {result.limitations.length > 0 && (
          <p className="small-note">
            태어난 시각을 모르는 사람이 있어요. 시주를 제외한 해석이며, 경계일에는 일부 기둥이
            달라질 수 있어요.
          </p>
        )}
        <p className="small-note">
          사주와 MBTI를 바탕으로 한 참고·오락용 해석이에요. 실제 관계와 미래를 단정하지 않아요.
        </p>
      </article>
      <p className="small-note center">
        {sharedAt
          ? `${formatDate(sharedAt)}에 만든 결과를 링크로 받았어요. 서버에는 저장되어 있지 않아요.`
          : '결과는 이 화면에만 표시돼요. 새로고침하거나 닫으면 사라져요.'}
      </p>
    </div>
  );
}

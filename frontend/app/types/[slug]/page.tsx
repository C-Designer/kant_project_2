import type { Metadata } from 'next';
import SpicyGate from '@/components/SpicyGate';
import TypeIllustration from '@/components/TypeIllustration';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import types from '@/data/relationship-types.json';
import { AXES, AXIS_MEANINGS, oneAxisApart } from '@/lib/relationship';
import { reachableTitles } from '@/lib/spicy';

type Props = { params: Promise<{ slug: string }> };
export const dynamicParams = false;
export function generateStaticParams() {
  return types.map((type) => ({ slug: type.slug }));
}
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const type = types.find((t) => t.slug === slug);
  return {
    title: type ? `${type.name} — 러브코드 관계유형` : '관계유형 — 러브코드',
    description: type?.summary,
  };
}
export default async function TypeDetail({ params }: Props) {
  const { slug } = await params;
  const index = types.findIndex((t) => t.slug === slug);
  if (index < 0) notFound();
  const type = types[index];
  const previous = types[(index + 15) % 16],
    next = types[(index + 1) % 16];
  const nearby = oneAxisApart(type.axes, types);
  return (
    <main id="main" className="type-detail-main">
      <Link href="/types" className="text-button type-back">
        ← 16가지 유형 모두 보기
      </Link>
      <section className="type-detail-hero" aria-labelledby="type-name">
        <div className="type-detail-image">
          <TypeIllustration type={type} />
        </div>
        <div className="type-detail-intro">
          <p className="eyebrow">두 사람이 만나는 방식</p>
          <h1 id="type-name">{type.name}</h1>
          <p className="type-detail-subtitle">{type.title}</p>
          <p>{type.summary}</p>
          <dl className="type-detail-axes">
            {AXES.map(({ label }, i) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{type.labels[i]}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>
      <div className="type-detail-reading">
        <section>
          <p className="eyebrow">이런 하루를 보내요</p>
          <h2>둘의 어느 하루</h2>
          <p>{type.day}</p>
        </section>
        <section>
          <p className="eyebrow">함께라서 좋은 점</p>
          <h2>우리의 좋은 호흡</h2>
          <ul className="type-detail-list">
            {type.strengths.map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
        </section>
        <section>
          <p className="eyebrow">서로 맞춰갈 점</p>
          <h2>서로에게 한 걸음</h2>
          <ul className="type-detail-list">
            {type.cares.map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
        </section>
        <section>
          <p className="eyebrow">마음이 엇갈릴 때</p>
          <h2>다툼을 푸는 순서</h2>
          <ol className="type-detail-steps">
            {type.conflict.map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ol>
        </section>
        <section>
          <p className="eyebrow">둘에게 어울리는 시간</p>
          <h2>이런 데이트는 어때요</h2>
          <ul className="type-detail-chips">
            {type.dates.map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
        </section>
        <blockquote>
          <span>오늘, 이렇게 말을 건네보세요.</span>
          {type.tips.map((text) => (
            <p key={text}>“{text}”</p>
          ))}
        </blockquote>
        <section>
          <p className="eyebrow">네 가지 기준으로 읽기</p>
          <h2>이 조합을 이루는 것들</h2>
          <dl className="type-detail-meanings">
            {AXES.map(({ label }, i) => (
              <div key={label}>
                <dt>
                  {label} <b>{type.labels[i]}</b>
                </dt>
                <dd>{AXIS_MEANINGS[type.axes[i]]}</dd>
              </div>
            ))}
          </dl>
        </section>
        <SpicyGate title="이 유형에서 나올 수 있는 매운맛 칭호">
          <p className="spicy-lead">
            실제 칭호는 두 사람 사주의 도화살·홍염살과 배우자 자리의 합·충에 따라 이 중 하나로
            정해져요.
          </p>
          <ul className="spicy-cards">
            {reachableTitles(type.id).map((topic) => (
              <li key={topic.key}>
                <small>
                  <span aria-hidden="true">{topic.emoji}</span> {topic.name}
                </small>
                {topic.titles.map((title) => (
                  <strong key={title}>{title}</strong>
                ))}
              </li>
            ))}
          </ul>
        </SpicyGate>
        <section>
          <p className="eyebrow">한 가지만 다르다면</p>
          <h2>가까운 유형</h2>
          <ul className="type-detail-nearby">
            {nearby.map(({ axis, type: other }) => (
              <li key={other.slug}>
                <Link href={`/types/${other.slug}`}>
                  <small>{axis}만 다른</small>
                  <span>{other.name}</span>
                  <small>{other.labels.join(' · ')}</small>
                </Link>
              </li>
            ))}
          </ul>
        </section>
        <p className="type-editorial-note">
          네 가지 기준을 이해하기 위한 유형 안내예요. 개인 분석 결과나 검증된 심리 진단이 아니며,
          실제 관계는 두 사람이 함께 만들어 가요.
        </p>
        <Link href="/test" className="button primary">
          우리 사이 알아보기 <span aria-hidden="true">↗</span>
        </Link>
      </div>
      <nav className="type-neighbours" aria-label="다른 관계유형">
        <Link href={`/types/${previous.slug}`}>
          <small>← 이전 유형</small>
          <span>{previous.name}</span>
        </Link>
        <Link href="/types" className="type-index-link">
          전체 보기
        </Link>
        <Link href={`/types/${next.slug}`}>
          <small>다음 유형 →</small>
          <span>{next.name}</span>
        </Link>
      </nav>
    </main>
  );
}

import type { Metadata } from 'next';
import TypeIllustration from '@/components/TypeIllustration';
import Link from 'next/link';
import types from '@/data/relationship-types.json';

export const metadata: Metadata = {
  title: '16가지 관계유형 — 러브코드',
  description: '열여섯 가지 관계의 모습. 그림을 골라 두 사람의 케미와 대화 방식을 살펴보세요.',
};

export default function TypesPage() {
  return <main id="main" className="matrix-main">
    <header className="matrix-heading"><p className="eyebrow">THE RELATIONSHIP COLLECTION</p><h1>16가지, <span>우리 사이.</span></h1><p>어떤 사이가 궁금한가요?<br className="mobile-break"/> 그림을 눌러 자세히 알아보세요.</p></header>
    <div className="relationship-matrix" aria-label="16가지 관계유형">{types.map(type=><Link className="matrix-tile" href={`/types/${type.slug}`} key={type.id} aria-label={`${type.name} — ${type.labels.join(', ')} 알아보기`}>
      <div className="matrix-image"><TypeIllustration type={type}/><span className="matrix-arrow" aria-hidden="true">↗</span></div>
      <h2>{type.name}</h2>
    </Link>)}</div>
    <p className="matrix-note">닮은꼴 또는 보완형 · 열정 또는 안정 · 함께 또는 각자 · 바로 또는 천천히<br/>네 가지 기준의 조합이에요. 더 좋거나 나쁜 유형은 없어요.</p>
    <div className="matrix-bottom"><p>우리 둘의 모습도 궁금하다면.</p><Link href="/test" className="text-button">우리 사이 알아보기 <span aria-hidden="true">↗</span></Link></div>
  </main>;
}

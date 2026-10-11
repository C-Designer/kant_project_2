import Link from 'next/link';
import PairArt from '@/components/PairArt';

const axes = [
  ['01', '연애 케미', '닮아서 편안할까, 달라서 끌릴까?', '닮은꼴', '보완형'],
  ['02', '연애 온도', '뜨거운 설렘일까, 잔잔한 다정함일까?', '열정형', '안정형'],
  ['03', '관계 거리', '함께하는 시간과 각자의 시간 사이', '밀착형', '독립형'],
  ['04', '갈등 해결', '바로 이야기할까, 잠깐 쉬어 갈까?', '바로 풀기', '시간 두기'],
];

export default function Home() {
  return (
    <main id="main" className="home-main">
      <div className="cover-kicker"><span className="edition">LOVE CODE / RELATIONSHIP EDITION</span><span>두 사람을 읽는 네 가지 시선</span></div>
      <section className="hero" aria-labelledby="cover-title">
        <div className="hero-copy">
          <h1 id="cover-title"><span>닮은 점.</span><span className="light">다른 점.</span><span>그 사이의 우리.</span></h1>
          <p className="lead">사주와 MBTI로 읽는<br />두 사람의 관계 스타일.</p>
          <Link href="/test" className="button primary">우리 사이 알아보기 <span aria-hidden="true">↗</span></Link>
          <p className="micro">회원가입 없이 · 양력 생일과 MBTI로</p>
        </div>
        <div className="hero-picture"><PairArt /><span className="picture-caption" lang="en">The space between us.</span></div>
      </section>
      <div className="preview-note"><strong>먼저 살펴보기</strong><p>예시 결과로 관계유형과 공유 기능을 살펴보세요.<br className="mobile-break" /> 분석 가능 여부는 입력 화면에서 안내해요.</p><Link href="/test">예시 살펴보기 <span aria-hidden="true">↗</span></Link></div>
      <section className="axis-section" aria-labelledby="axis-title">
        <div className="section-heading"><p className="eyebrow">01 / 관계의 네 가지 면</p><div><h2 id="axis-title">우리가 만나는 방식.</h2><p>네 가지 시선, 열여섯 가지 관계유형.<br />두 사람이 이야기할 힌트를 찾아보세요.</p></div></div>
        <div className="axis-list">{axes.map(([n, title, desc, a, b]) => (
          <article className="axis-row" key={n}><span className="axis-number" aria-hidden="true">{n}</span><h3>{title}</h3><p>{desc}</p><div className="pair-labels"><span>{a}</span><i aria-hidden="true">/</i><span>{b}</span></div></article>
        ))}</div>
        <Link href="/types" className="text-button">16가지 관계유형 살펴보기 <span aria-hidden="true">↗</span></Link>
      </section>
      <section className="closing-note"><p className="eyebrow">대화의 시작</p><div><h2>서로를 아는 일은,<br /><span>계속되는 이야기니까.</span></h2><p>결과는 참고용이에요.<br />실제 관계의 모습은 두 사람이 함께 만들어 가요.</p></div><Link href="/test" className="text-button">우리 사이 알아보기 <span aria-hidden="true">↗</span></Link></section>
    </main>
  );
}

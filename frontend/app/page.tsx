import Link from 'next/link';
import TypeIllustration from '@/components/TypeIllustration';
import types from '@/data/relationship-types.json';

export default function Home() {
  const picks = ['T06', 'T03', 'T13'].map((id) => types.find((t) => t.id === id)!);
  return (
    <main id="main" className="home-main atlas-home">
      <section className="atlas-hero">
        <div>
          <p className="eyebrow">두 사람을 위한 관계 도감</p>
          <h1>
            우리 둘은
            <br />
            어떤 커플일까?
          </h1>
          <p className="lead">
            함께라서 편한 순간, 서로 달라서 좋은 순간.
            <br />
            사주와 MBTI로 우리 사이를 살펴보세요.
          </p>
          <Link href="/test" className="button primary">
            우리 궁합 알아보기 <span aria-hidden="true">→</span>
          </Link>
          <p className="micro">회원가입 없이 · 양력 생일과 MBTI로</p>
          <Link href="/test?demo=1" className="text-button">
            입력 전에 예시 결과 보기 →
          </Link>
        </div>
        <div className="atlas-shelf" aria-label="관계유형 미리보기">
          {picks.map((t) => (
            <Link href={`/types/${t.slug}`} key={t.id} aria-label={`${t.name} 자세히 보기`}>
              <TypeIllustration type={t} />
              <span>{t.name}</span>
            </Link>
          ))}
        </div>
      </section>
      <section className="atlas-intro">
        <div>
          <p className="eyebrow">정답보다, 대화의 시작</p>
          <h2>
            같은 마음에도
            <br />
            다른 방식이 있으니까.
          </h2>
        </div>
        <div>
          <p>
            자주 붙어 있어야 좋은 사람도, 혼자 쉬어야 더 다정해지는 사람도 있어요. 네 가지 기준으로
            두 사람의 모습을 읽어봅니다.
          </p>
          <Link href="/types" className="text-button">
            16가지 관계유형 펼쳐보기 →
          </Link>
        </div>
      </section>
      <section className="atlas-axes" aria-label="궁합을 읽는 네 가지 기준">
        {[
          ['연애 케미', '닮아서 편할까, 달라서 끌릴까?', '취향과 성향이 만나는 방식'],
          ['연애 온도', '뜨거운 설렘, 잔잔한 다정함', '마음을 표현하는 온도'],
          ['관계 거리', '함께하는 시간, 각자의 시간', '서로 편안한 거리'],
          ['갈등 해결', '지금 이야기할까, 조금 쉴까?', '다툰 뒤 다시 가까워지는 방식'],
        ].map(([title, question, desc]) => (
          <article key={title}>
            <p className="eyebrow">{title}</p>
            <h3>{question}</h3>
            <p>{desc}</p>
          </article>
        ))}
      </section>
      <aside className="atlas-footnote">
        <p>
          좋고 나쁜 유형은 없어요. 결과는 사주·MBTI 기반의 참고·오락용 해석이며, 실제 관계나 미래를
          단정하지 않아요.
        </p>
      </aside>
    </main>
  );
}

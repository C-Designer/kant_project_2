import type { Metadata } from 'next';
import Link from 'next/link';
import BrandMark from '@/components/BrandMark';
import './globals.css';

export const metadata: Metadata = {
  title: '러브코드 — 사이의 발견',
  description: '함께 읽고, 서로를 조금 더 알아가는 시간. 사주와 MBTI로 읽는 두 사람의 관계 스타일.',
  robots: { index: false, follow: false },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <a className="skip" href="#main">
          본문으로 건너뛰기
        </a>
        <header className="header">
          <Link className="logo" href="/" aria-label="러브코드 홈">
            <BrandMark />
            러브코드
          </Link>
          <nav aria-label="주 메뉴">
            <Link href="/types">16가지 유형</Link>
            <Link href="/test">궁합 알아보기</Link>
          </nav>
        </header>
        {children}
        <footer>
          <div>
            <Link className="logo footer-logo" href="/">
              러브코드
            </Link>
            <p>함께 읽고, 서로를 조금 더 알아가는 시간.</p>
          </div>
          <div className="footer-meta">
            <span className="edition">두 사람을 위한 관계 도감</span>
            <small>사주·MBTI 기반 참고·오락용 서비스</small>
            <small>AI 해석은 참고용 · 결과별 검수 상태 표시</small>
          </div>
        </footer>
      </body>
    </html>
  );
}

import type { Metadata } from 'next';
import Link from 'next/link';
import { Wordmark } from '@/components/BrandMark';
import 'pretendard/dist/web/variable/pretendardvariable-dynamic-subset.css';
import './globals.css';

const TITLE = '러브코드 — 우리 둘은 어떤 커플일까?';
const DESCRIPTION =
  '사주와 MBTI로 읽는 두 사람의 관계 스타일. 16가지 커플 유형 중 우리는 어디일까요?';

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? 'https://kant-lovecode.vercel.app'),
  title: TITLE,
  description: DESCRIPTION,
  robots: { index: false, follow: false },
  openGraph: {
    type: 'website',
    locale: 'ko_KR',
    siteName: '러브코드',
    title: TITLE,
    description: DESCRIPTION,
    // Built by scripts/build_og_image.py from the original illustrations.
    images: [
      { url: '/og.png', width: 1200, height: 630, alt: '우리 둘은 어떤 커플일까? 러브코드' },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: TITLE,
    description: DESCRIPTION,
    images: ['/og.png'],
  },
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
            <Wordmark />
          </Link>
          <nav aria-label="주 메뉴">
            <Link href="/types">16가지 유형</Link>
            <Link href="/test" className="nav-cta">
              궁합 알아보기
            </Link>
          </nav>
        </header>
        {children}
        <footer>
          <div>
            <Link className="logo footer-logo" href="/" aria-label="러브코드 홈">
              <Wordmark />
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

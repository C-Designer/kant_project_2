// Logo A (docs/design/brand-ppt/logo-sheet.png): the deck's two-tone title as a wordmark.
const HEART =
  'M12 21s-7.5-4.6-10-9.2C.3 8.4 2.2 4 6.3 4c2.4 0 4 1.4 5.7 3.4C13.7 5.4 15.3 4 17.7 4 21.8 4 23.7 8.4 22 11.8 19.5 16.4 12 21 12 21z';

export default function BrandMark({ className = 'brand-mark' }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <path d={HEART} />
    </svg>
  );
}

// 러브 in cocoa, 코드 in pink, with a small heart over the last syllable.
export function Wordmark() {
  return (
    <span className="wordmark">
      러브<span className="wordmark-point">코드</span>
      <BrandMark className="wordmark-heart" />
    </span>
  );
}

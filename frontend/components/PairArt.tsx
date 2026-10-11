export default function PairArt() {
  return (
    <svg className="pair-art" viewBox="0 0 520 520" role="img" aria-label="서로 겹치며 새로운 공간을 만드는 두 개의 선">
      <path d="M221 150C325 115 403 181 413 270C424 363 336 421 260 393C303 322 297 227 221 150Z" className="art-accent" />
      <g fill="none" stroke="currentColor" strokeWidth="2.5">
        <ellipse cx="224" cy="252" rx="128" ry="181" transform="rotate(-32 224 252)" />
        <ellipse cx="321" cy="269" rx="128" ry="181" transform="rotate(32 321 269)" />
      </g>
      <path d="M56 418H466" className="art-rule" />
      <g fill="currentColor"><circle cx="105" cy="186" r="5" /><circle cx="439" cy="190" r="5" /></g>
      <g fill="currentColor" fontFamily="Georgia,serif" fontStyle="italic" fontSize="24" aria-hidden="true">
        <text x="80" y="167">a</text><text x="449" y="176">b</text>
      </g>
    </svg>
  );
}

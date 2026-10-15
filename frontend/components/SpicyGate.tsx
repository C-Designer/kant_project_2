'use client';
import { useId, useState } from 'react';

/** Blurred until the reader confirms they are an adult. Nothing is stored: reload = blurred. */
export default function SpicyGate({
  title,
  preconfirmed = false,
  children,
}: {
  title: string;
  preconfirmed?: boolean;
  children: React.ReactNode;
}) {
  const [adult, setAdult] = useState(preconfirmed);
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <section className="spicy" aria-labelledby={id}>
      <h2 id={id}>
        <span aria-hidden="true">🌶</span> {title}
      </h2>
      {open ? (
        children
      ) : (
        <div className="spicy-gate">
          <div className="spicy-blur" aria-hidden="true">
            <span />
            <span />
            <span />
            <span />
          </div>
          <div className="spicy-gate-actions">
            <p>속궁합·바람기처럼 매운 주제를 다뤄요. 웃자고 만든 오락용이에요.</p>
            <label className="check">
              <input type="checkbox" checked={adult} onChange={(e) => setAdult(e.target.checked)} />
              만 19세 이상이며 오락용임을 이해해요
            </label>
            <button
              type="button"
              className="button primary"
              disabled={!adult}
              onClick={() => setOpen(true)}
            >
              매운맛 열기
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

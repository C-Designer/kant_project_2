'use client';
import { useRef, useState } from 'react';

const GENDERS = [
  ['male', '남성'],
  ['female', '여성'],
  ['unspecified', '선택 안 함'],
] as const;

// One pair per MBTI letter; the submitted value joins the four choices (e.g. INTJ).
export const MBTI_AXES = [
  ['E', '외향', 'I', '내향'],
  ['S', '감각', 'N', '직관'],
  ['T', '사고', 'F', '감정'],
  ['J', '판단', 'P', '인식'],
] as const;

export function mbtiFrom(form: FormData, id: string): string {
  return MBTI_AXES.map((_, i) => String(form.get(`${id}mbti-${i}`) ?? '')).join('');
}

export default function PersonFields({ id, title }: { id: string; title: string }) {
  const [unknown, setUnknown] = useState(false);
  const [mbti, setMbti] = useState(['', '', '', '']);
  const time = useRef<HTMLInputElement>(null);
  return (
    <fieldset className="person">
      <legend>
        <span aria-hidden="true">{id === 'a' ? '01' : '02'}</span>
        {title}
      </legend>

      <fieldset className="choice">
        <legend>성별</legend>
        <div className="segmented">
          {GENDERS.map(([value, label], i) => (
            <label key={value}>
              <input type="radio" name={id + 'gender'} value={value} required={i === 0} />
              <span>{label}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <label htmlFor={id + 'date'}>
        생년월일 <small>양력</small>
      </label>
      <input
        id={id + 'date'}
        name={id + 'date'}
        type="date"
        min="1940-01-01"
        aria-describedby={id + 'date-hint'}
        onInvalid={(e) => {
          const input = e.currentTarget;
          if (input.validity.rangeUnderflow || input.validity.rangeOverflow) {
            input.setCustomValidity('1940년 1월 1일부터 오늘까지의 날짜를 입력해 주세요.');
          }
        }}
        onChange={(e) => e.currentTarget.setCustomValidity('')}
        max={new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Seoul' })}
        required
      />
      <p id={id + 'date-hint'} className="field-hint">
        1940년 1월 1일부터 오늘까지 태어난 분을 지원해요.
      </p>

      <label htmlFor={id + 'time'}>
        태어난 시각 <small>한국 표준시</small>
      </label>
      <input
        ref={time}
        id={id + 'time'}
        name={id + 'time'}
        type="time"
        disabled={unknown}
        required={!unknown}
      />
      <label className="check">
        <input
          type="checkbox"
          name={id + 'unknown'}
          checked={unknown}
          onChange={(e) => {
            // Clear the hidden time so unchecking asks for it again instead of reusing it.
            if (e.target.checked && time.current) time.current.value = '';
            setUnknown(e.target.checked);
          }}
        />
        태어난 시각을 몰라요
      </label>

      <fieldset className="choice">
        <legend>
          MBTI{' '}
          <small aria-live="polite">
            {mbti.every(Boolean) ? mbti.join('') : '네 가지를 골라 주세요'}
          </small>
        </legend>
        {MBTI_AXES.map(([a, aLabel, b, bLabel], i) => (
          <div
            className="segmented mbti"
            key={a + b}
            role="radiogroup"
            aria-label={`${aLabel} 또는 ${bLabel}`}
          >
            {[
              [a, aLabel],
              [b, bLabel],
            ].map(([letter, label], j) => (
              <label key={letter}>
                <input
                  type="radio"
                  name={`${id}mbti-${i}`}
                  value={letter}
                  required={j === 0}
                  onChange={() => setMbti((m) => m.map((v, k) => (k === i ? letter : v)))}
                />
                <span>
                  <b>{letter}</b> {label}
                </span>
              </label>
            ))}
          </div>
        ))}
      </fieldset>
    </fieldset>
  );
}

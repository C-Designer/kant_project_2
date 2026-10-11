'use client';
import { useState } from 'react';
const mbtis = [
  'INTJ',
  'INTP',
  'ENTJ',
  'ENTP',
  'INFJ',
  'INFP',
  'ENFJ',
  'ENFP',
  'ISTJ',
  'ISFJ',
  'ESTJ',
  'ESFJ',
  'ISTP',
  'ISFP',
  'ESTP',
  'ESFP',
];
export default function PersonFields({
  id,
  title,
  active,
}: {
  id: string;
  title: string;
  active: boolean;
}) {
  const [unknown, setUnknown] = useState(false);
  return (
    <fieldset className="person" hidden={!active}>
      <legend>
        <span>{id === 'a' ? '01' : '02'}</span> {title}
      </legend>
      <label htmlFor={id + 'gender'}>성별</label>
      <select id={id + 'gender'} name={id + 'gender'} required={active} defaultValue="">
        <option disabled value="">
          선택해 주세요
        </option>
        <option value="male">남성</option>
        <option value="female">여성</option>
        <option value="unspecified">선택 안 함</option>
      </select>
      <label htmlFor={id + 'date'}>
        생년월일 <small>양력</small>
      </label>
      <input
        id={id + 'date'}
        name={id + 'date'}
        type="date"
        min="1900-01-01"
        max={new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Seoul' })}
        required={active}
      />
      <label htmlFor={id + 'time'}>
        태어난 시각 <small>한국 표준시</small>
      </label>
      <input
        id={id + 'time'}
        name={id + 'time'}
        type="time"
        disabled={unknown}
        required={active && !unknown}
      />
      <label className="check">
        <input
          type="checkbox"
          name={id + 'unknown'}
          checked={unknown}
          onChange={(e) => setUnknown(e.target.checked)}
        />
        태어난 시각을 몰라요
      </label>
      <label htmlFor={id + 'mbti'}>MBTI</label>
      <select id={id + 'mbti'} name={id + 'mbti'} required={active} defaultValue="">
        <option disabled value="">
          선택해 주세요
        </option>
        {mbtis.map((m) => (
          <option key={m}>{m}</option>
        ))}
      </select>
    </fieldset>
  );
}

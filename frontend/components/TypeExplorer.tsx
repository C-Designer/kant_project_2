'use client';
import { useState } from 'react';
import types from '@/data/relationship-types.json';

const filters = [
  {name:'연애 케미', values:['similar','complementary'], labels:['닮은꼴','보완형']},
  {name:'연애 온도', values:['passionate','steady'], labels:['열정형','안정형']},
  {name:'관계 거리', values:['together','independent'], labels:['밀착형','독립형']},
  {name:'갈등 해결', values:['immediate','pause'], labels:['바로 풀기','시간 두기']},
];

export default function TypeExplorer() {
  const [selected,setSelected] = useState(['','','','']);
  const visible = types.filter(type=>selected.every((value,i)=>!value||type.axes[i]===value));
  return <section className="type-explorer" aria-labelledby="explore-title">
    <div className="type-filter-heading"><h2 id="explore-title">어떤 사이가 궁금한가요?</h2><button type="button" className="text-button" onClick={()=>setSelected(['','','',''])} disabled={selected.every(v=>!v)}>전체 보기</button></div>
    <p className="type-filter-help">관심 있는 특징을 골라보세요. 선택하지 않은 기준은 모두 보여드려요.</p>
    <div className="type-filters">{filters.map((f,i)=><label key={f.name} htmlFor={`type-filter-${i}`}>{f.name}<select id={`type-filter-${i}`} value={selected[i]} onChange={e=>setSelected(selected.map((v,j)=>i===j?e.target.value:v))}><option value="">모두</option>{f.values.map((v,j)=><option key={v} value={v}>{f.labels[j]}</option>)}</select></label>)}</div>
    <p className="type-count" role="status">전체 16가지 중 <strong>{visible.length}가지</strong> 관계 <span>설명을 펼쳐 서로 맞춰갈 점도 읽어보세요.</span></p>
    <div className="type-grid">{visible.map(type=><article className="type-entry" key={type.id}>
      <p className="type-labels">{type.labels.map(label=><span key={label}>{label}</span>)}</p>
      <h3>{type.title}</h3><p className="type-summary">{type.summary}</p>
      <details><summary><span>이 관계 자세히 보기</span><span className="disclosure-mark" aria-hidden="true">+</span></summary><div className="type-details"><h4>함께라서 좋은 점</h4><p>{type.strength}</p><h4>서로 맞춰갈 점</h4><p>{type.care}</p><blockquote><span>이렇게 말을 건네보세요</span><p>“{type.tip}”</p></blockquote></div></details>
    </article>)}</div>
  </section>;
}

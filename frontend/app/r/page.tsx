'use client';
import {useEffect,useState} from 'react';
import Link from 'next/link';
import ResultView from '@/components/ResultView';
import BrandMark from '@/components/BrandMark';
import {Saved,api} from '@/components/client';
export default function Shared(){const [saved,setSaved]=useState<Saved|null>(null),[error,setError]=useState(''),[retry,setRetry]=useState(0);useEffect(()=>{let active=true;setError('');const t=window.location.hash.slice(1);if(!/^[A-Za-z0-9_-]{43}$/.test(t)){setError('결과를 볼 수 없어요. 링크가 잘못됐거나 삭제·만료되었을 수 있어요.');return;}api<Saved>('results',{headers:{Authorization:'Bearer '+t}}).then(r=>{if(active)setSaved(r);}).catch(()=>{if(active)setError('결과를 불러오지 못했어요. 링크가 삭제·만료되었거나 연결이 잠시 끊겼을 수 있어요.');});return()=>{active=false;};},[retry]);return <main id="main" className="form-main">{saved?.result?<ResultView result={saved.result} expires={saved.expires_at}/>:error?<section className="empty"><BrandMark/><h1>결과를 열 수 없어요</h1><p role="alert">{error}</p><button className="button secondary" onClick={()=>setRetry(retry+1)}>다시 확인</button><Link className="text-button" href="/test">새로운 궁합 알아보기 →</Link></section>:<p role="status" className="center">공유한 이야기를 불러오고 있어요…</p>}</main>}

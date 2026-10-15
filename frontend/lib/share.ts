// A share link carries the signed result itself after '#'. Browsers never send the fragment
// to a server, so it stays out of access logs; the shared page passes it in a header instead.
// Mirrors CODE in backend/lovecode/share.py.
const CODE = /^[A-Za-z0-9_-]{1,6000}\.[A-Za-z0-9_-]{22}$/;

export function shareUrl(origin: string, code: string): string {
  return origin + '/r#' + code;
}

export function codeFromHash(hash: string): string | null {
  const code = hash.replace(/^#/, '');
  return CODE.test(code) ? code : null;
}

export function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat('ko-KR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    timeZone: 'Asia/Seoul',
  }).format(date);
}

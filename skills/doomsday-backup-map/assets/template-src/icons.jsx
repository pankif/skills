// Пиктограммы типов компонентов: 16×16, штрих, цвет из currentColor.
const P = {
  section: <><path d="M8 1.75l6.25 3.25L8 8.25 1.75 5z" /><path d="M1.75 8L8 11.25 14.25 8M1.75 11L8 14.25 14.25 11" /></>,
  gateway: <><path d="M8 1.75l5.5 2v4c0 3.2-2.3 5.6-5.5 6.5-3.2-.9-5.5-3.3-5.5-6.5v-4z" /><path d="M5.5 8h5M8.5 6l2 2-2 2" /></>,
  client: <><rect x="1.75" y="2.75" width="12.5" height="8.5" rx="1.5" /><path d="M5.5 13.75h5M8 11.25v2.5" /></>,
  table: <><rect x="1.75" y="2.75" width="12.5" height="10.5" rx="1.5" /><path d="M1.75 6.25h12.5M1.75 9.75h12.5M6 6.25v7" /></>,
  cron: <><circle cx="8" cy="8" r="6.25" /><path d="M8 4.5V8l2.5 1.75" /></>,
  secret: <><circle cx="5.5" cy="8" r="3" /><path d="M8.5 8h6M12 8v2.5M14.25 8v1.75" /></>,
  collection: <><rect x="3.75" y="1.75" width="9" height="10.5" rx="1.5" /><path d="M2 4.5v8.25a1.5 1.5 0 0 0 1.5 1.5H10M6.25 5h4M6.25 8h4" /></>,
  file: <><path d="M3.25 1.75h6l3.5 3.5v8a1 1 0 0 1-1 1h-8.5a1 1 0 0 1-1-1v-10.5a1 1 0 0 1 1-1z" /><path d="M9.25 1.75v3.5h3.5" /></>,
  external: <><circle cx="8" cy="8" r="6.25" /><path d="M1.75 8h12.5M8 1.75c1.8 1.7 2.6 3.8 2.6 6.25S9.8 12.55 8 14.25C6.2 12.55 5.4 10.45 5.4 8S6.2 3.45 8 1.75z" /></>,
  chat: <><path d="M2 7.25c0-2.9 2.7-5 6-5s6 2.1 6 5-2.7 5-6 5c-.7 0-1.4-.1-2-.3L2.75 13.5l.9-2.6C2.6 10 2 8.7 2 7.25z" /></>,
  book: <><path d="M8 3.6C6.7 2.6 4.8 2.2 2 2.25v10c2.8-.05 4.7.35 6 1.35 1.3-1 3.2-1.4 6-1.35v-10c-2.8-.05-4.7.35-6 1.35zM8 3.6v10" /></>,
  star: <><path d="M8 1.9l1.85 3.85 4.2.55-3.07 2.9.78 4.15L8 11.3l-3.76 2.05.78-4.15-3.07-2.9 4.2-.55z" /></>,
  photo: <><rect x="1.75" y="2.75" width="12.5" height="10.5" rx="1.75" /><circle cx="5.5" cy="6.25" r="1.25" /><path d="M14.25 10.5l-3.5-3.25-6.5 6" /></>,
  flag: <><path d="M3 14.25V2.25M3 2.75c3-1.5 5.5 1.5 9.75 0v6.5C8.5 10.75 6 7.75 3 9.25" /></>,
  bell: <><path d="M4 11V7a4 4 0 0 1 8 0v4l1.25 1.5H2.75z" /><path d="M6.5 14a1.6 1.6 0 0 0 3 0" /></>,
  shield: <><path d="M8 1.75l5.5 2v4c0 3.2-2.3 5.6-5.5 6.5-3.2-.9-5.5-3.3-5.5-6.5v-4z" /><path d="M5.5 8l1.75 1.75L10.75 6.25" /></>,
  phone: <><path d="M4.5 1.75h-1.6a1.15 1.15 0 0 0-1.15 1.3c.6 5.5 4.95 9.85 10.45 10.45a1.15 1.15 0 0 0 1.3-1.15V10.7l-2.9-1-1.4 1.4a8.6 8.6 0 0 1-3.65-3.65L7 6.05z" /></>,
  envelope: <><rect x="1.75" y="3.25" width="12.5" height="9.5" rx="1.5" /><path d="M2 4l6 4.5L14 4" /></>,
  channel: <><rect x="1.75" y="3.25" width="12.5" height="9.5" rx="1.5" /><path d="M2 4l6 4.5L14 4" /></>,
  edge: <><path d="M8 1.75l5.5 2v4c0 3.2-2.3 5.6-5.5 6.5-3.2-.9-5.5-3.3-5.5-6.5v-4z" /><path d="M5.5 8h5M8.5 6l2 2-2 2" /></>,
  auth: <><circle cx="5.5" cy="8" r="3" /><path d="M8.5 8h6M12 8v2.5M14.25 8v1.75" /></>,
  service: <><path d="M8 1.75l5.5 3.1v6.3L8 14.25l-5.5-3.1V4.85z" /><path d="M2.75 5L8 8l5.25-3M8 8v6" /></>,
  worker: <><path d="M13 6.5A5.25 5.25 0 0 0 3.4 4.6M3 9.5a5.25 5.25 0 0 0 9.6 1.9" /><path d="M3.25 1.75v3h3M12.75 14.25v-3h-3" /></>,
  stream: <><path d="M1.75 4.5c2 0 2-1.5 4-1.5s2 1.5 4 1.5 2-1.5 4.5-1.5M1.75 8.5c2 0 2-1.5 4-1.5s2 1.5 4 1.5 2-1.5 4.5-1.5M1.75 12.5c2 0 2-1.5 4-1.5s2 1.5 4 1.5 2-1.5 4.5-1.5" /></>,
  queue: <><rect x="1.75" y="5" width="3" height="6" rx=".75" /><rect x="6.5" y="5" width="3" height="6" rx=".75" /><rect x="11.25" y="5" width="3" height="6" rx=".75" /></>,
  cache: <><path d="M9 1.75L3.5 9h4l-1 5.25L12.5 7h-4z" /></>,
  db: <><ellipse cx="8" cy="3.75" rx="5.25" ry="2" /><path d="M2.75 3.75v8.5c0 1.1 2.35 2 5.25 2s5.25-.9 5.25-2v-8.5M2.75 8c0 1.1 2.35 2 5.25 2s5.25-.9 5.25-2" /></>,
  search: <><circle cx="7" cy="7" r="4.5" /><path d="M10.4 10.4l3.85 3.85" /></>,
  object: <><path d="M2.5 4.25h11l-1.4 9.1a1 1 0 0 1-1 .9H4.9a1 1 0 0 1-1-.9z" /><ellipse cx="8" cy="4.25" rx="5.5" ry="1.75" /></>,
  analytics: <><path d="M1.75 14.25h12.5" /><rect x="3" y="8" width="2.5" height="6.25" /><rect x="6.75" y="4.5" width="2.5" height="9.75" /><rect x="10.5" y="1.75" width="2.5" height="12.5" /></>,
  secrets: <><rect x="2.75" y="7" width="10.5" height="7.25" rx="1.5" /><path d="M5 7V5a3 3 0 0 1 6 0v2M8 10v1.75" /></>,
  config: <><circle cx="4" cy="3.5" r="1.75" /><circle cx="4" cy="12.5" r="1.75" /><circle cx="12" cy="6" r="1.75" /><path d="M4 5.25v5.5M12 7.75c0 2.5-3 2.5-6.6 3.6" /></>,
  mail: <><path d="M1.75 9.5l2-6.25h8.5l2 6.25v3.75a1 1 0 0 1-1 1H2.75a1 1 0 0 1-1-1z" /><path d="M1.75 9.5h3.5l1 1.75h3.5l1-1.75h3.5" /></>,
  pbx: <><path d="M4.5 1.75h-1.6a1.15 1.15 0 0 0-1.15 1.3c.6 5.5 4.95 9.85 10.45 10.45a1.15 1.15 0 0 0 1.3-1.15V10.7l-2.9-1-1.4 1.4a8.6 8.6 0 0 1-3.65-3.65L7 6.05z" /></>,
  target: <><rect x="1.75" y="2.25" width="12.5" height="4" rx="1" /><path d="M2.75 6.25v6.5a1 1 0 0 0 1 1h8.5a1 1 0 0 0 1-1v-6.5M6.25 9h3.5" /></>,
  vault: <><rect x="1.75" y="3.25" width="12.5" height="9.5" rx="1.5" /><circle cx="5.25" cy="8" r="1.75" /><circle cx="10.75" cy="8" r="1.75" /><path d="M5.25 9.75h5.5" /></>,
};

export function KindIcon({ kind, size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ flex: 'none' }}>
      {P[kind] || P.service}
    </svg>
  );
}

export const Ico = {
  search: (s = 14) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden="true"><circle cx="7" cy="7" r="4.5" /><path d="M10.4 10.4l3.6 3.6" /></svg>,
  plus: (s = 14) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden="true"><path d="M8 3v10M3 8h10" /></svg>,
  minus: (s = 14) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden="true"><path d="M3 8h10" /></svg>,
  fit: (s = 14) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M2 6V2h4M14 6V2h-4M2 10v4h4M14 10v4h-4" /></svg>,
  close: (s = 14) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8" /></svg>,
  arrowUp: (s = 12) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M8 13V3M4 7l4-4 4 4" /></svg>,
  arrowDown: (s = 12) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M8 3v10M4 9l4 4 4-4" /></svg>,
  shield: (s = 14) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" aria-hidden="true"><path d="M8 1.75l5.5 2v4c0 3.2-2.3 5.6-5.5 6.5-3.2-.9-5.5-3.3-5.5-6.5v-4z" /></svg>,
  copy: (s = 13) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" aria-hidden="true"><rect x="5" y="5" width="9" height="9" rx="1.5" /><path d="M11 5V3.5A1.5 1.5 0 0 0 9.5 2h-6A1.5 1.5 0 0 0 2 3.5v6A1.5 1.5 0 0 0 3.5 11H5" /></svg>,
  check: (s = 14) => <svg width={s} height={s} viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="7" fill="currentColor" /><path d="M4.9 8.2l2.05 2.05L11.2 6" fill="none" stroke="var(--on-status, #04120b)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>,
  cross: (s = 14) => <svg width={s} height={s} viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="7" fill="currentColor" /><path d="M5.6 5.6l4.8 4.8M10.4 5.6l-4.8 4.8" fill="none" stroke="var(--on-status, #1d0406)" strokeWidth="1.8" strokeLinecap="round" /></svg>,
  question: (s = 14) => <svg width={s} height={s} viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="7" fill="currentColor" /><path d="M6.1 6.2a1.95 1.95 0 0 1 3.8.5c0 1.3-1.9 1.6-1.9 2.8" fill="none" stroke="var(--on-status, #0d0b2a)" strokeWidth="1.6" strokeLinecap="round" /><circle cx="8" cy="11.6" r=".95" fill="var(--on-status, #0d0b2a)" /></svg>,
  dash: (s = 14) => <svg width={s} height={s} viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6.4" fill="none" stroke="currentColor" strokeWidth="1.4" /><path d="M5.25 8h5.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>,
  half: (s = 14) => <svg width={s} height={s} viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6.4" fill="none" stroke="currentColor" strokeWidth="1.6" /><path d="M8 1.6a6.4 6.4 0 0 1 0 12.8z" fill="currentColor" /></svg>,
  sidebar: (s = 16) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><rect x="1.75" y="2.75" width="12.5" height="10.5" rx="2" /><path d="M6 2.75v10.5M3.5 5.5h1M3.5 7.5h1" strokeLinecap="round" /></svg>,
  chevron: (s = 12) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M6 3.5L10.5 8 6 12.5" /></svg>,
  back: (s = 14) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M10 3L5 8l5 5" /></svg>,
  alert: (s = 14) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M8 2L1.75 13.25h12.5z" /><path d="M8 6.5v3M8 11.6v.1" /></svg>,
};

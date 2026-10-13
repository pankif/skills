import { useEffect, useState } from 'react';

export function useReducedMotion() {
  const [r, setR] = useState(() => {
    try { return window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch { return false; }
  });
  useEffect(() => {
    let mq;
    try { mq = window.matchMedia('(prefers-reduced-motion: reduce)'); } catch { return undefined; }
    const h = () => setR(mq.matches);
    mq.addEventListener?.('change', h);
    return () => mq.removeEventListener?.('change', h);
  }, []);
  return r;
}

export function useMedia(query) {
  const get = () => { try { return window.matchMedia(query).matches; } catch { return false; } };
  const [m, setM] = useState(get);
  useEffect(() => {
    let mq;
    try { mq = window.matchMedia(query); } catch { return undefined; }
    const h = () => setM(mq.matches);
    mq.addEventListener?.('change', h);
    return () => mq.removeEventListener?.('change', h);
  }, [query]);
  return m;
}

// Глобальные клавиши: «/» — поиск, Esc — сброс. Не перехватываем ввод в полях.
export function useHotkeys(map) {
  useEffect(() => {
    const h = (e) => {
      const t = e.target;
      const typing = t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable);
      const key = (e.metaKey || e.ctrlKey ? 'mod+' : '') + e.key.toLowerCase();
      const fn = map[key];
      if (!fn) return;
      if (typing && key !== 'escape' && !key.startsWith('mod+')) return;
      e.preventDefault();
      fn(e);
    };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  });
}

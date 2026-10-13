import React, { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import {
  ReactFlow, ReactFlowProvider, Background, Handle, Position, useReactFlow, useNodesState,
  BaseEdge, EdgeLabelRenderer, getSmoothStepPath,
} from '@xyflow/react';
import { layout, plural } from './layout.js';
import { KindIcon, Ico } from './icons.jsx';
import { useReducedMotion, useMedia, useHotkeys } from './shared.jsx';

// Карта стека с отметками бэкапа. Данные — JSON в <script id="map-data"> (формат: references/data-format.md скилла).
// Статусы, изменённые на карте, и ширина панелей хранятся в localStorage этого браузера.

// ── Справочники
const LAYERS = [
  { id: 'root', name: 'Раздел' },
  { id: 'entry', name: 'Точки входа' },
  { id: 'app', name: 'Сервисы' },
  { id: 'bus', name: 'Очереди и кеш' },
  { id: 'workers', name: 'Фоновые задачи' },
  { id: 'data', name: 'Хранилища' },
  { id: 'external', name: 'Внешние системы' },
];
const LAYER_IDS = new Set(LAYERS.map((l) => l.id));
const LAYER_NAME = Object.fromEntries(LAYERS.map((l) => [l.id, l.name]));
const TYPE = {
  schema: ['Схема', 'db'], table: ['Таблица', 'table'], collection: ['Коллекция', 'collection'], bucket: ['Бакет', 'object'],
  topic: ['Топик', 'stream'], queue: ['Очередь', 'queue'], cache: ['Кеш', 'cache'], cron: ['Крон', 'cron'],
  config: ['Конфиг', 'file'], secret: ['Секрет', 'secret'], index: ['Индекс', 'search'], mailbox: ['Почтовый ящик', 'mail'],
  file: ['Файлы', 'file'], volume: ['Диск', 'db'], repo: ['Репозиторий', 'config'], other: ['Объект', 'file'],
};
const KIND = {
  client: ['Клиент', 'entry'], channel: ['Канал', 'entry'], gateway: ['Шлюз', 'svc'], service: ['Сервис', 'svc'],
  auth: ['Авторизация', 'svc'], pbx: ['Телефония', 'svc'], queue: ['Очередь', 'bus'], stream: ['Поток событий', 'bus'], cache: ['Кеш', 'bus'],
  worker: ['Фоновая задача', 'work'], db: ['База данных', 'data'], search: ['Поисковый индекс', 'data'], analytics: ['Аналитическая БД', 'data'],
  object: ['Файловое хранилище', 'files'], mail: ['Почта', 'ext'], external: ['Внешняя система', 'ext'],
};
const ICONS = new Set(['chat', 'book', 'phone', 'star', 'photo', 'flag', 'envelope', 'bell', 'shield', 'section', 'db', 'service', 'client', 'secret', 'cron', 'external']);
const STATUS = new Set(['yes', 'no', 'skip', 'unknown']);
const EDITABLE = ['no', 'unknown', 'skip'];
const ST_LABEL = { yes: 'В бэкапе', no: 'Нет в бэкапе', unknown: 'Не выяснено', skip: 'Бэкап не нужен' };
const ST_SHORT = { yes: 'В бэкапе', no: 'Нет', unknown: 'Не выяснено', skip: 'Не нужно' };

// Геометрия схемы
const NODE_W = 208, ROOT_W = 248, GAP_X = 14;
const TRAY_PAD = 20, TRAY_TOP = 34, TRAY_BOTTOM = 14, TRAY_GAP = 12, ROOT_GAP = 30, EST_H = 84;
const SIDE = { def: 264, min: 220, max: 440 };
const INS = { def: 344, min: 300, max: 600 };
const GAP = 10;

// ── Нормализация: снисходительно к неполным данным, всё лишнее отбрасываем
const st = (v) => (STATUS.has(v) ? v : 'unknown');
function normItems(items) {
  return (Array.isArray(items) ? items : []).filter((x) => x && x.name).map((x) => {
    const s = st(x.status);
    const o = { type: TYPE[x.type] ? x.type : 'other', name: String(x.name), size: x.size, status: s, where: x.where, note: x.note };
    if (Array.isArray(x.children) && x.children.length) {
      o.children = x.children.filter((c) => c && c.name).map((c) => ({
        type: TYPE[c.type] ? c.type : 'table', name: String(c.name), size: c.size,
        status: c.status ? st(c.status) : s, own: !!c.status, where: c.where, note: c.note,
      }));
    }
    return o;
  });
}

function readData() {
  const el = document.getElementById('map-data');
  let raw;
  try { raw = JSON.parse(el ? el.textContent : ''); } catch { return null; }
  if (!raw || !Array.isArray(raw.services)) return null;
  const services = raw.services.filter((s) => s && Array.isArray(s.sections)).map((s, si) => ({
    id: String(s.id || `s${si}`), name: String(s.name || 'Сервис'), icon: ICONS.has(s.icon) ? s.icon : 'section',
    sections: s.sections.filter(Boolean).map((sec, xi) => {
      const comps = (sec.components || []).filter((c) => c && c.id).map((c) => ({
        id: String(c.id), layer: LAYER_IDS.has(c.layer) && c.layer !== 'root' ? c.layer : 'app', kind: KIND[c.kind] ? c.kind : 'service',
        name: String(c.name || c.id), tech: c.tech || '', desc: c.desc || '', sources: Array.isArray(c.sources) ? c.sources : c.sources ? [c.sources] : [],
        items: normItems(c.items),
      }));
      const ids = new Set(comps.map((c) => c.id));
      const links = (sec.links || []).map((l) => (Array.isArray(l) ? { from: l[0], to: l[1], label: l[2] } : { from: l.from, to: l.to, label: l.label }))
        .filter((l) => ids.has(l.from) && ids.has(l.to) && l.from !== l.to);
      // Корень раздела строится сам и ведёт к точкам входа (или к верхним компонентам без входящих связей)
      const hasIn = new Set(links.map((l) => l.to));
      let tops = comps.filter((c) => c.layer === 'entry' && !hasIn.has(c.id));
      if (!tops.length) {
        const firstLayer = LAYERS.find((L) => comps.some((c) => c.layer === L.id && !hasIn.has(c.id)));
        tops = firstLayer ? comps.filter((c) => c.layer === firstLayer.id && !hasIn.has(c.id)) : [];
      }
      const root = { id: '__root', layer: 'root', kind: 'section', name: String(sec.name || 'Раздел'), tech: String(s.name || ''), desc: sec.desc || '', sources: [], items: [] };
      return {
        id: String(sec.id || `x${xi}`), name: String(sec.name || 'Раздел'), icon: ICONS.has(sec.icon) ? sec.icon : 'section', desc: sec.desc || '',
        nodes: [root, ...comps],
        edges: [...tops.map((t) => ({ source: '__root', target: t.id })), ...links.map((l) => ({ source: l.from, target: l.to, label: l.label }))],
      };
    }),
  })).filter((s) => s.sections.length);
  if (!services.length) return null;
  return { title: String(raw.title || 'Бэкапы судного дня'), subtitle: String(raw.subtitle || 'Каталог критичных данных'), services };
}

const DATA = readData();
const SECTIONS = DATA ? DATA.services.flatMap((g) => g.sections.map((s) => ({ ...s, group: g, key: `${g.id}/${s.id}` }))) : [];

// ── Локальное хранилище: правки статусов и ширина панелей
const STORE_KEY = DATA ? `doomsday-map:v1:${DATA.title}` : 'doomsday-map:v1';
function readStore() {
  try { const v = JSON.parse(window.localStorage.getItem(STORE_KEY) || 'null'); return v && typeof v === 'object' ? v : {}; } catch { return {}; }
}
function writeStore(patch) {
  try { window.localStorage.setItem(STORE_KEY, JSON.stringify({ ...readStore(), ...patch })); } catch { /* хранилище недоступно: правки живут до перезагрузки */ }
}

// ── Статусы с учётом правок
const SEP = '\u001f';
const pathOf = (sec, comp, item, child) => [sec.group.id, sec.id, comp.id, item.name, child ? child.name : ''].join(SEP);
// Правка действует, только пока в данных тот же статус, от которого её сделали: если данные обновили, побеждают данные
function effective(o, base) {
  if (!o || base === 'yes' || !EDITABLE.includes(o.status)) return base;
  if (o.was && o.was !== base) return base;
  return o.status;
}
function stateOf(s) {
  if (!s.total) return 'none';
  if (s.no) return s.yes ? 'partial' : 'missing';
  if (s.unknown) return 'unknown';
  return s.yes ? 'ok' : 'skip';
}

function evaluate(sec, ov) {
  const rows = {}, stats = {}, applied = new Set();
  const total = { yes: 0, no: 0, skip: 0, unknown: 0 };
  const missing = [], unknown = [];
  for (const n of sec.nodes) {
    const s = { yes: 0, no: 0, skip: 0, unknown: 0, total: 0 };
    rows[n.id] = n.items.map((it) => {
      const path = pathOf(sec, n, it);
      const status = effective(ov[path], it.status);
      if (status !== it.status) applied.add(path);
      const rec = { service: sec.group.id, section: sec.id, component: n.id, item: it.name };
      const row = { it, path, base: it.status, status, rec };
      if (it.children) {
        row.kids = it.children.map((c) => {
          const cpath = pathOf(sec, n, it, c);
          const cbase = c.own ? c.status : status;
          const cst = effective(ov[cpath], cbase);
          if (cst !== cbase) applied.add(cpath);
          return { it: c, path: cpath, base: cbase, status: cst, parent: it, inherited: !c.own, rec: { ...rec, child: c.name } };
        });
      }
      return row;
    });
    for (const row of rows[n.id]) {
      for (const leaf of row.kids || [row]) {
        s[leaf.status]++;
        s.total++;
        if (leaf.status === 'no' || leaf.status === 'unknown') {
          (leaf.status === 'no' ? missing : unknown).push({
            type: leaf.it.type, name: leaf.parent ? `${leaf.parent.name}.${leaf.it.name}` : leaf.it.name,
            note: leaf.it.note || (leaf.inherited ? leaf.parent.note : undefined), node: n, key: leaf.path,
          });
        }
      }
    }
    s.state = stateOf(s);
    stats[n.id] = s;
    for (const k of Object.keys(total)) total[k] += s[k];
  }
  return { rows, stats, total, missing, unknown, applied };
}

// Убираем правки, которые уже совпадают с данными или устарели после пересборки карты
function prune(ov) {
  const live = new Set();
  for (const sec of SECTIONS) for (const p of evaluate(sec, ov).applied) live.add(p);
  return Object.fromEntries(Object.entries(ov).filter(([p]) => live.has(p)));
}

// ── Раскладка раздела: x — по слоям с барицентром соседей, y — по измеренной высоте нод
const cache = new Map();
function prepare(sec) {
  if (cache.has(sec.key)) return cache.get(sec.key);
  const byId = Object.fromEntries(sec.nodes.map((n) => [n.id, n]));
  const out = Object.fromEntries(sec.nodes.map((n) => [n.id, []]));
  const inc = Object.fromEntries(sec.nodes.map((n) => [n.id, []]));
  for (const e of sec.edges) { out[e.source].push(e.target); inc[e.target].push(e.source); }
  const reach = (start, adj) => { const seen = new Set(); const stack = [start]; while (stack.length) for (const n of adj[stack.pop()]) if (!seen.has(n)) { seen.add(n); stack.push(n); } return seen; };
  const layers = LAYERS.filter((l) => sec.nodes.some((n) => n.layer === l.id));
  const L = layout({ layers, nodes: sec.nodes, edges: sec.edges }, { nodeW: NODE_W, rowGap: 100, gapX: GAP_X, widths: { __root: ROOT_W } });
  const layerOf = Object.fromEntries(sec.nodes.map((n) => [n.id, layers.findIndex((l) => l.id === n.layer)]));
  const prefix = `${sec.key}:`;
  const edges = sec.edges.map((e) => {
    const la = layerOf[e.source], lb = layerOf[e.target];
    let h = { sourceHandle: 's', targetHandle: 't' };
    if (la === lb) h = L.pos[e.source].x < L.pos[e.target].x ? { sourceHandle: 'sr', targetHandle: 'tl' } : { sourceHandle: 'sl', targetHandle: 'tr' };
    else if (la > lb) h = { sourceHandle: 'su', targetHandle: 'td' }; // связь снизу вверх
    return { id: `${prefix}${e.source}→${e.target}`, source: `${prefix}${e.source}`, target: `${prefix}${e.target}`, label: e.label, raw: e, ...h };
  });
  const res = { sec, byId, out, inc, layers, L, layerOf, prefix, edges, up: (id) => reach(id, inc), down: (id) => reach(id, out) };
  cache.set(sec.key, res);
  return res;
}

function place(P, heights = {}, prevNodes = []) {
  const prev = new Map(prevNodes.map((n) => [n.id, n]));
  const rowH = P.layers.map((_, i) => Math.max(...P.L.rows[i].map((id) => heights[id] || EST_H)));
  const y = [], tray = [];
  let cursor = 0;
  P.layers.forEach((l, i) => {
    if (i === 0) { y[0] = 0; cursor = rowH[0] + ROOT_GAP; return; }
    const h = TRAY_TOP + rowH[i] + TRAY_BOTTOM;
    tray[i] = { top: cursor, h };
    y[i] = cursor + TRAY_TOP;
    cursor += h + TRAY_GAP;
  });
  const x0 = P.L.minX - TRAY_PAD, w = P.L.maxX - P.L.minX + TRAY_PAD * 2;
  const nodes = [];
  P.layers.forEach((l, i) => {
    if (i === 0) return;
    const id = `${P.prefix}tray-${l.id}`;
    nodes.push({
      ...(prev.get(id) || {}), id, type: 'tray', position: { x: x0, y: tray[i].top },
      data: { name: l.name, count: P.L.rows[i].length, w, h: tray[i].h, i },
      draggable: false, selectable: false, focusable: false, connectable: false, zIndex: -1,
    });
  });
  for (const n of P.sec.nodes) {
    const id = `${P.prefix}${n.id}`;
    nodes.push({
      ...(prev.get(id) || {}), id, type: 'part', position: { x: P.L.pos[n.id].x, y: y[P.layerOf[n.id]] },
      data: { n, i: P.layerOf[n.id], sec: P.sec.key }, draggable: false, connectable: false, style: { width: n.id === '__root' ? ROOT_W : NODE_W },
    });
  }
  return { nodes, bounds: { x: x0, y: 0, w, h: Math.max(cursor - TRAY_GAP, rowH[0]) } };
}

const View = createContext({});

// ── Ноды
function Glyph({ status, size = 13 }) {
  if (status === 'yes') return Ico.check(size);
  if (status === 'no') return Ico.cross(size);
  if (status === 'unknown') return Ico.question(size);
  return Ico.dash(size);
}

function Badge({ s, total }) {
  if (total) {
    const need = total.yes + total.no + total.unknown;
    const cls = total.no ? 'b-partial' : total.unknown ? 'b-unknown' : 'b-ok';
    return <span className={`badge ${cls}`}>{total.no ? Ico.half(13) : total.unknown ? Ico.question(13) : Ico.check(13)}В бэкапе {total.yes} из {need}</span>;
  }
  switch (s.state) {
    case 'none': return <span className="badge b-none">Без данных</span>;
    case 'skip': return <span className="badge b-skip">{Ico.dash(13)}Бэкап не нужен</span>;
    case 'ok': return <span className="badge b-ok">{Ico.check(13)}В бэкапе{s.yes > 1 && <b>{s.yes}</b>}</span>;
    case 'missing': return <span className="badge b-missing">{Ico.cross(13)}Нет бэкапа{s.no > 1 && <b>{s.no}</b>}</span>;
    case 'unknown': return <span className="badge b-unknown">{Ico.question(13)}Не выяснено{s.unknown > 1 && <b>{s.unknown}</b>}</span>;
    default: return <span className="badge b-partial">{Ico.half(13)}{s.yes} из {s.yes + s.no + s.unknown} в бэкапе</span>;
  }
}

function PartNode({ data }) {
  const { sel, branch, onlyGaps, evals, key } = useContext(View);
  const n = data.n;
  const [, grp] = KIND[n.kind] || ['', 'root'];
  const root = n.layer === 'root';
  // Пока раздел переключается, на холсте могут быть ноды прежнего раздела: статусы берём по их разделу
  const E = evals[data.sec];
  const s = E.stats[n.id];
  const current = data.sec === key;
  let state = '';
  if (!current) state = '';
  else if (sel) state = n.id === sel ? 'is-sel' : branch.has(n.id) ? 'is-rel' : 'is-dim';
  else if (onlyGaps && !root) state = s.no || s.unknown ? 'is-hit' : 'is-dim';
  return (
    <div className={`part g-${root ? 'root' : grp} ${root ? 'root' : ''} ${state}`} style={{ '--i': data.i }}>
      <Handle type="target" id="t" position={Position.Top} isConnectable={false} />
      <Handle type="target" id="tl" position={Position.Left} isConnectable={false} />
      <Handle type="target" id="tr" position={Position.Right} isConnectable={false} />
      <Handle type="target" id="td" position={Position.Bottom} isConnectable={false} />
      <Handle type="source" id="sl" position={Position.Left} isConnectable={false} />
      <Handle type="source" id="sr" position={Position.Right} isConnectable={false} />
      <Handle type="source" id="su" position={Position.Top} isConnectable={false} />
      <div className="p-row">
        <span className="p-ico"><KindIcon kind={n.kind} size={root ? 17 : 15} /></span>
        <span className="p-text">
          <span className="p-name">{n.name}</span>
          {n.tech && <span className="p-tech">{n.tech}</span>}
        </span>
      </div>
      <Badge s={s} total={root ? E.total : null} />
      <Handle type="source" id="s" position={Position.Bottom} isConnectable={false} />
    </div>
  );
}

function TrayNode({ data }) {
  return (
    <div className="tray" style={{ width: data.w, height: data.h, '--i': data.i }}>
      <span className="tray-name">{data.name}</span>
      <span className="tray-count">{data.count}</span>
    </div>
  );
}

function LinkEdge({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data }) {
  const [path, lx, ly] = getSmoothStepPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, borderRadius: 14, offset: 14 });
  return (
    <>
      <BaseEdge id={id} path={path} className="link" interactionWidth={0} />
      {data.hi && data.label && (
        <EdgeLabelRenderer>
          <div className="elabel" style={{ transform: `translate(-50%, -50%) translate(${lx}px, ${ly}px)` }}>{data.label}</div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

const nodeTypes = { part: PartNode, tray: TrayNode };
const edgeTypes = { link: LinkEdge };

// ── Сайдбар
function Accessory({ t }) {
  if (t.no > 0) return <span className="sb-miss" title={`${t.no} ${plural(t.no, ['объект', 'объекта', 'объектов'])} не в бэкапе`}>{t.no}</span>;
  if (t.unknown > 0) return <span className="sb-unk" title={`${t.unknown} не выяснено`}>?{t.unknown}</span>;
  if (t.yes > 0) return <span className="sb-ok" title="Всё критичное в бэкапе">{Ico.check(14)}</span>;
  return null;
}

function Changes({ overrides, onReset }) {
  const count = Object.keys(overrides).length;
  const [copied, setCopied] = useState(false);
  const [manual, setManual] = useState(null);
  const [armed, setArmed] = useState(false);
  const area = useRef(null);
  useEffect(() => { if (!armed) return undefined; const t = setTimeout(() => setArmed(false), 3000); return () => clearTimeout(t); }, [armed]);
  useEffect(() => { if (manual && area.current) area.current.select(); }, [manual]);
  useEffect(() => { if (!count) setManual(null); }, [count]);
  if (!count) return <p className="sb-legend">Красная цифра — объектов нет в бэкапе, фиолетовая — не выяснено.</p>;
  const text = () => JSON.stringify({
    map: DATA.title,
    changes: Object.values(overrides).map(({ service, section, component, item, child, status, was }) => ({ service, section, component, item, ...(child ? { child } : {}), status, was })),
  }, null, 2);
  const copy = () => {
    const t = text();
    const fallback = () => setManual(t);
    try {
      const p = navigator.clipboard && navigator.clipboard.writeText(t);
      if (!p) { fallback(); return; }
      p.then(() => { setCopied(true); setTimeout(() => setCopied(false), 1600); }, fallback);
    } catch { fallback(); }
  };
  return (
    <div className="changes">
      <p className="ch-head"><b>{count}</b> {plural(count, ['статус изменён', 'статуса изменено', 'статусов изменено'])} вручную</p>
      <p className="ch-hint">Сохранено в этом браузере. Чтобы перенести в данные карты, скопируйте и передайте агенту.</p>
      <div className="ch-actions">
        <button type="button" className="btn primary" onClick={copy}>{copied ? <>{Ico.tick(12)}Скопировано</> : 'Скопировать для агента'}</button>
        <button type="button" className={`btn ${armed ? 'danger' : ''}`} onClick={() => { if (armed) { setArmed(false); onReset(); } else setArmed(true); }}>
          {armed ? 'Точно сбросить?' : 'Сбросить'}
        </button>
      </div>
      {manual && (
        <div className="ch-manual">
          <label htmlFor="ch-text">Буфер обмена недоступен — выделите и скопируйте вручную</label>
          <textarea id="ch-text" ref={area} readOnly rows={5} value={manual} onFocus={(e) => e.target.select()} />
          <button type="button" className="btn" onClick={() => setManual(null)}>Готово</button>
        </div>
      )}
    </div>
  );
}

function Sidebar({ current, onSelect, open, onClose, evals, overrides, onReset }) {
  const [q, setQ] = useState('');
  const [shut, setShut] = useState(() => new Set());
  const s = q.trim().toLowerCase();
  const match = (sec) => !s || `${sec.name} ${sec.group.name}`.toLowerCase().includes(s)
    || sec.nodes.some((n) => `${n.name} ${n.tech}`.toLowerCase().includes(s)
      || n.items.some((x) => x.name.toLowerCase().includes(s) || (x.children || []).some((c) => `${x.name}.${c.name}`.toLowerCase().includes(s))));
  return (
    <nav className={`sidebar ${open ? 'open' : ''}`} aria-label="Сервисы и разделы">
      <div className="sb-head">
        <span className="sb-app">{Ico.shield(18)}</span>
        <span className="sb-title"><b>{DATA.title}</b><small>{DATA.subtitle}</small></span>
        <button type="button" className="sb-close" onClick={onClose} aria-label="Скрыть список сервисов">{Ico.close()}</button>
      </div>
      <label className="sb-search">
        {Ico.search(13)}
        <input id="sb-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Поиск: раздел, таблица, крон" autoComplete="off" aria-label="Поиск по каталогу" />
      </label>
      <div className="sb-scroll">
        {DATA.services.map((g) => {
          const secs = SECTIONS.filter((x) => x.group.id === g.id && match(x));
          if (!secs.length) return null;
          const closed = shut.has(g.id) && !s;
          const missing = secs.reduce((a, x) => a + evals[x.key].total.no, 0);
          return (
            <section key={g.id} className="sb-group">
              <button type="button" className={`sb-ghead ${closed ? 'closed' : ''}`} aria-expanded={!closed}
                onClick={() => setShut((v) => { const nv = new Set(v); if (nv.has(g.id)) nv.delete(g.id); else nv.add(g.id); return nv; })}>
                <span className="sb-chev">{Ico.chevron(10)}</span>
                <span className="sb-gname">{g.name}</span>
                {closed && missing > 0 && <span className="sb-gcount">{missing}</span>}
              </button>
              {!closed && (
                <ul>
                  {secs.map((x) => (
                    <li key={x.key}>
                      <button type="button" className={`sb-row ${current === x.key ? 'on' : ''}`} aria-current={current === x.key ? 'page' : undefined} onClick={() => onSelect(x.key)}>
                        <span className="sb-ico"><KindIcon kind={x.icon} size={15} /></span>
                        <span className="sb-name">{x.name}</span>
                        <Accessory t={evals[x.key].total} />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          );
        })}
      </div>
      <div className="sb-foot"><Changes overrides={overrides} onReset={onReset} /></div>
    </nav>
  );
}

// ── Меню статуса: всплывает у кнопки, как меню macOS
function StatusMenu({ menu, onPick, onClose }) {
  const ref = useRef(null);
  const [pos, setPos] = useState(null);
  const { row } = menu;
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const r = menu.rect, w = el.offsetWidth, h = el.offsetHeight, m = 8;
    let top = r.bottom + 6, origin = 'top';
    if (top + h > window.innerHeight - m) { top = Math.max(m, r.top - h - 6); origin = 'bottom'; }
    const left = Math.max(m, Math.min(r.right - w, window.innerWidth - w - m));
    setPos({ top, left, origin });
  }, [menu]);
  useEffect(() => {
    if (!pos) return;
    const el = ref.current;
    (el.querySelector('[aria-checked="true"]') || el.querySelector('[role="menuitemradio"]'))?.focus();
  }, [pos]);
  useEffect(() => {
    const away = (e) => { if (!ref.current?.contains(e.target)) onClose(false); };
    const scroll = (e) => { if (!ref.current?.contains(e.target)) onClose(false); };
    const resize = () => onClose(false);
    window.addEventListener('pointerdown', away, true);
    window.addEventListener('scroll', scroll, true);
    window.addEventListener('resize', resize);
    return () => {
      window.removeEventListener('pointerdown', away, true);
      window.removeEventListener('scroll', scroll, true);
      window.removeEventListener('resize', resize);
    };
  }, [onClose]);
  const onKey = (e) => {
    const items = [...ref.current.querySelectorAll('[role="menuitemradio"]')];
    const i = items.indexOf(document.activeElement);
    if (e.key === 'ArrowDown') { e.preventDefault(); items[(i + 1) % items.length].focus(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); items[(i - 1 + items.length) % items.length].focus(); }
    else if (e.key === 'Home') { e.preventDefault(); items[0].focus(); }
    else if (e.key === 'End') { e.preventDefault(); items[items.length - 1].focus(); }
    else if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); onClose(true); }
    else if (e.key === 'Tab') { e.preventDefault(); onClose(true); }
  };
  const name = row.parent ? `${row.parent.name}.${row.it.name}` : row.it.name;
  return (
    <div ref={ref} className={`menu o-${pos ? pos.origin : 'top'}`} role="menu" aria-label={`Статус: ${name}`} onKeyDown={onKey}
      style={pos ? { top: pos.top, left: pos.left } : { top: 0, left: 0, visibility: 'hidden' }}>
      <div className="menu-title"><code>{name}</code></div>
      {EDITABLE.map((s) => (
        <button key={s} type="button" role="menuitemradio" aria-checked={row.status === s} className={`mi s-${s}`} onClick={() => onPick(s)}>
          <span className="mi-check">{row.status === s && Ico.tick(12)}</span>
          <span className="mi-glyph"><Glyph status={s} size={14} /></span>
          <span className="mi-label">{ST_LABEL[s]}</span>
          {row.base === s && <small>в данных</small>}
        </button>
      ))}
    </div>
  );
}

// ── Инспектор
function StatusControl({ row, onOpen }) {
  if (row.base === 'yes') return <span className="si si-yes" title="В бэкапе: подтверждено в данных">{Ico.check(15)}</span>;
  const changed = row.status !== row.base;
  return (
    <button type="button" className={`st-btn s-${row.status} ${changed ? 'changed' : ''}`} aria-haspopup="menu"
      aria-label={`Статус: ${ST_LABEL[row.status]}${changed ? ', изменён вручную' : ''}. Изменить`} onClick={(e) => onOpen(e.currentTarget, row)}>
      <Glyph status={row.status} size={13} />
      <span>{ST_SHORT[row.status]}</span>
      {Ico.chevronDown(9)}
    </button>
  );
}

function ItemRow({ row, nested, onOpen }) {
  const it = row.it;
  const [label, icon] = TYPE[it.type] || TYPE.other;
  const changed = row.status !== row.base;
  const own = !nested || !row.inherited;
  const sub = row.status === 'yes' ? (own ? it.where : null) : (own ? it.note : null);
  return (
    <li className={`item ${nested ? 'nested' : ''} is-${row.status}`}>
      <span className="it-ico" title={label}><KindIcon kind={icon} size={14} /></span>
      <span className="it-main">
        <span className="it-name"><code>{it.name}</code>{it.size && <small>{it.size}</small>}</span>
        {sub && <span className="it-sub">{sub}</span>}
        {changed && <span className="it-changed">Изменено вручную · в данных «{ST_SHORT[row.base]}»</span>}
      </span>
      <StatusControl row={row} onOpen={onOpen} />
    </li>
  );
}

function GapList({ title, list, onPick, tone }) {
  if (!list.length) return null;
  return (
    <section>
      <h3>{title}</h3>
      <ul className={`miss ${tone}`}>
        {list.map((x) => {
          const [label, icon] = TYPE[x.type] || TYPE.other;
          return (
            <li key={x.key}>
              <button type="button" onClick={() => onPick(x.node.id)}>
                <span className="it-ico" title={label}><KindIcon kind={icon} size={14} /></span>
                <span className="it-main">
                  <span className="it-name"><code>{x.name}</code></span>
                  <span className="it-sub">{x.node.name}{x.note ? ` · ${x.note}` : ''}</span>
                </span>
                <span className="m-chev">{Ico.chevron(11)}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function Overview({ P, E, onPick }) {
  const { sec } = P;
  const { total } = E;
  return (
    <div className="ins-body" key={sec.key}>
      <p className="eyebrow">{sec.group.name}</p>
      <h2>{sec.name}</h2>
      {sec.desc && <p className="lead">{sec.desc}</p>}
      <div className="tally" role="group" aria-label="Итог по разделу">
        <div className="t-yes"><b>{total.yes}</b><span>в бэкапе</span></div>
        <div className={total.no ? 't-no' : ''}><b>{total.no}</b><span>нет</span></div>
        <div className={total.unknown ? 't-unknown' : ''}><b>{total.unknown}</b><span>не выяснено</span></div>
        <div className="t-skip"><b>{total.skip}</b><span>не нужно</span></div>
      </div>
      <GapList title="Нет в бэкапе" list={E.missing} onPick={onPick} tone="no" />
      <GapList title="Не выяснено" list={E.unknown} onPick={onPick} tone="unknown" />
      {!E.missing.length && !E.unknown.length && <p className="all-ok">{Ico.check(16)} Всё критичное в бэкапе</p>}
      <p className="hint">Выберите компонент на схеме, чтобы увидеть, что в нём хранится, и поправить статусы.</p>
    </div>
  );
}

function Detail({ P, E, id, onPick, onBack, onOpen }) {
  const n = P.byId[id];
  const [kindLabel] = KIND[n.kind] || ['Раздел'];
  const rows = E.rows[id];
  return (
    <div className="ins-body" key={`${P.sec.key}-${id}`}>
      <button type="button" className="back" onClick={onBack}>{Ico.back(13)}<span>{P.sec.name}</span></button>
      <p className="eyebrow">{kindLabel} · {LAYER_NAME[n.layer]}</p>
      <h2>{n.name}</h2>
      {n.tech && <p className="tech">{n.tech}</p>}
      {n.desc && <p className="lead">{n.desc}</p>}
      {rows.length ? (
        <section>
          <div className="sec-head"><h3>Что хранится</h3><Badge s={E.stats[id]} /></div>
          <ul className="items">
            {rows.map((row) => (
              <React.Fragment key={row.it.name}>
                <ItemRow row={row} onOpen={onOpen} />
                {row.kids && row.kids.map((k) => <ItemRow key={k.it.name} row={k} nested onOpen={onOpen} />)}
              </React.Fragment>
            ))}
          </ul>
          {rows.some((r) => r.base !== 'yes' || (r.kids || []).some((k) => k.base !== 'yes')) && (
            <p className="hint">Статус «нет», «не выяснено» и «не нужно» можно поменять: нажмите на него. «В бэкапе» меняется только в данных — для него нужно подтверждение, где лежит копия.</p>
          )}
        </section>
      ) : n.layer !== 'root' && <p className="hint">Своих данных нет: бэкапить нечего.</p>}
      {n.sources.length > 0 && <p className="sources"><span>Откуда сведения</span>{n.sources.join(' · ')}</p>}
      {(P.out[id].length > 0 || P.inc[id].length > 0) && (
        <section>
          <h3>Связи</h3>
          {P.out[id].length > 0 && <div className="rel"><span>Обращается к</span><div>{P.out[id].map((d) => <button key={d} type="button" onClick={() => onPick(d)}>{P.byId[d].name}</button>)}</div></div>}
          {P.inc[id].filter((d) => d !== '__root').length > 0 && <div className="rel"><span>Кто обращается</span><div>{P.inc[id].filter((d) => d !== '__root').map((d) => <button key={d} type="button" onClick={() => onPick(d)}>{P.byId[d].name}</button>)}</div></div>}
        </section>
      )}
    </div>
  );
}

// ── Ручка изменения ширины панели
function Resizer({ side, value, spec, onStart, onResize, onEnd }) {
  const start = useRef(null);
  const [active, setActive] = useState(false);
  const sign = side === 'left' ? 1 : -1;
  const end = () => { if (!start.current) return; start.current = null; setActive(false); onEnd(); };
  return (
    <div
      role="separator" aria-orientation="vertical" tabIndex={0}
      aria-label={side === 'left' ? 'Ширина списка разделов' : 'Ширина панели подробностей'}
      aria-valuemin={spec.min} aria-valuemax={spec.max} aria-valuenow={Math.round(value)}
      title="Потяните, чтобы изменить ширину. Двойной щелчок — ширина по умолчанию"
      className={`resizer r-${side} ${active ? 'on' : ''}`}
      onPointerDown={(e) => {
        if (e.button !== 0) return;
        e.preventDefault();
        e.currentTarget.setPointerCapture(e.pointerId);
        start.current = { x: e.clientX, v: value };
        setActive(true);
        onStart();
      }}
      onPointerMove={(e) => { if (start.current) onResize(start.current.v + sign * (e.clientX - start.current.x)); }}
      onPointerUp={end}
      onPointerCancel={end}
      onLostPointerCapture={end}
      onDoubleClick={() => { onResize(spec.def); onEnd(); }}
      onKeyDown={(e) => {
        const step = e.shiftKey ? 48 : 16;
        let v = null;
        if (e.key === 'ArrowRight') v = value + sign * step;
        else if (e.key === 'ArrowLeft') v = value - sign * step;
        else if (e.key === 'Home') v = spec.min;
        else if (e.key === 'End') v = spec.max;
        if (v === null) return;
        e.preventDefault();
        onResize(v);
        onEnd();
      }}
    />
  );
}

// ── Приложение
function MapApp() {
  const rf = useReactFlow();
  const reduce = useReducedMotion();
  const narrow = useMedia('(max-width: 900px)');
  const [key, setKey] = useState(SECTIONS[0].key);
  const [sel, setSel] = useState(null);
  const [onlyGaps, setOnlyGaps] = useState(false);
  const [sideOpen, setSideOpen] = useState(false);
  const [sheet, setSheet] = useState(false);
  const [menu, setMenu] = useState(null);
  const [overrides, setOverrides] = useState(() => prune(readStore().overrides || {}));
  const stored = useMemo(() => readStore(), []);
  const clampW = (v, spec) => Math.round(Math.max(spec.min, Math.min(spec.max, Number(v) || spec.def)));
  const [sideW, setSideW] = useState(() => clampW(stored.sideW, SIDE));
  const [insW, setInsW] = useState(() => clampW(stored.insW, INS));
  const [resizing, setResizing] = useState(false);
  const widths = useRef({ side: sideW, ins: insW });
  const canvasRef = useRef(null);
  const P = useMemo(() => prepare(SECTIONS.find((s) => s.key === key)), [key]);
  const evals = useMemo(() => Object.fromEntries(SECTIONS.map((s) => [s.key, evaluate(s, overrides)])), [overrides]);
  const E = evals[key];

  useEffect(() => { writeStore({ overrides }); }, [overrides]);

  // Две фазы: сначала ноды рисуются невидимыми и измеряются, затем слои раскладываются по их реальной высоте
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const placed = useRef({ key: null, sig: '', bounds: null });
  const fitted = useRef(false); // схема вписана и пользователь её не двигал
  const [placedKey, setPlacedKey] = useState(null);
  useEffect(() => {
    const res = place(P);
    placed.current = { key: null, sig: '', bounds: res.bounds };
    setPlacedKey(null);
    setNodes(res.nodes);
  }, [P, setNodes]);
  useEffect(() => {
    const parts = nodes.filter((n) => n.type === 'part');
    if (!parts.length || !parts[0].id.startsWith(P.prefix)) return;
    const heights = {};
    let sig = '';
    for (const n of parts) {
      const h = n.measured && n.measured.height;
      if (!h) return;
      heights[n.id.slice(P.prefix.length)] = h;
      sig += `${h},`;
    }
    if (placed.current.key === P.sec.key && placed.current.sig === sig) return;
    const res = place(P, heights, nodes);
    placed.current = { key: P.sec.key, sig, bounds: res.bounds };
    setNodes(res.nodes);
    setPlacedKey(P.sec.key);
  }, [nodes, P, setNodes]);

  const fit = useCallback((animate) => {
    const el = canvasRef.current;
    const b = placed.current.bounds;
    if (!el || !b) return;
    const W = el.clientWidth, H = el.clientHeight;
    const ins = narrow ? { l: 12, r: 12, t: 76, b: 84 } : { l: widths.current.side + GAP * 2 + 14, r: widths.current.ins + GAP * 2 + 14, t: 80, b: 76 };
    const aw = Math.max(120, W - ins.l - ins.r), ah = Math.max(120, H - ins.t - ins.b);
    let zoom = Math.min(aw / b.w, ah / b.h, 1.05);
    if (narrow) zoom = Math.max(zoom, 0.55);
    const x = ins.l + (aw - b.w * zoom) / 2 - b.x * zoom;
    const y = narrow ? ins.t - b.y * zoom : ins.t + Math.max(0, (ah - b.h * zoom) / 2) - b.y * zoom;
    rf.setViewport({ x, y, zoom }, { duration: animate && !reduce ? 520 : 0 });
    fitted.current = true;
  }, [rf, reduce, narrow]);

  useEffect(() => {
    if (placedKey !== key) return undefined;
    const t = requestAnimationFrame(() => fit(false));
    return () => cancelAnimationFrame(t);
  }, [placedKey]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const el = canvasRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return undefined;
    let w = el.clientWidth;
    const ro = new ResizeObserver(() => { if (Math.abs(el.clientWidth - w) > 40) { w = el.clientWidth; fit(false); } });
    ro.observe(el);
    return () => ro.disconnect();
  }, [fit]);

  // Ширина панелей: схема сдвигается на половину изменения, чтобы её видимый центр оставался на месте
  const resize = useCallback((side, v) => {
    const spec = side === 'left' ? SIDE : INS;
    const other = side === 'left' ? widths.current.ins : widths.current.side;
    const vw = canvasRef.current ? canvasRef.current.clientWidth : window.innerWidth;
    const max = Math.max(spec.min, Math.min(spec.max, vw - other - GAP * 3 - 320));
    const nv = Math.round(Math.max(spec.min, Math.min(max, v)));
    const prev = side === 'left' ? widths.current.side : widths.current.ins;
    if (nv === prev) return;
    const vp = rf.getViewport();
    rf.setViewport({ ...vp, x: vp.x + (side === 'left' ? 1 : -1) * (nv - prev) / 2 });
    // setViewport выше — программный сдвиг, он не сбрасывает признак «вписано»
    if (side === 'left') { widths.current.side = nv; setSideW(nv); } else { widths.current.ins = nv; setInsW(nv); }
  }, [rf]);
  // Если схема была вписана, после изменения ширины панели вписываем её заново
  const endResize = useCallback(() => {
    setResizing(false);
    writeStore({ sideW: widths.current.side, insW: widths.current.ins });
    if (fitted.current) fit(true);
  }, [fit]);

  const selectSection = (k) => { setKey(k); setSel(null); setSideOpen(false); setSheet(false); setMenu(null); };
  const raw = (id) => id.slice(P.prefix.length);
  const pick = useCallback((id) => {
    setSel(id);
    setSheet(true);
    setMenu(null);
    const node = rf.getNode(`${P.prefix}${id}`);
    if (node) {
      const w = (node.measured && node.measured.width) || NODE_W, h = (node.measured && node.measured.height) || EST_H;
      rf.setCenter(node.position.x + w / 2, node.position.y + h / 2, { zoom: Math.max(rf.getZoom(), 0.8), duration: reduce ? 0 : 450 });
      fitted.current = false;
    }
  }, [rf, reduce, P]);

  const openMenu = useCallback((el, row) => setMenu({ rect: el.getBoundingClientRect(), row, anchor: el }), []);
  const closeMenu = useCallback((refocus) => setMenu((m) => { if (m && refocus && m.anchor && m.anchor.isConnected) m.anchor.focus(); return null; }), []);
  const setStatus = useCallback((row, status) => {
    setOverrides((ov) => {
      const next = { ...ov };
      if (status === row.base) delete next[row.path];
      else next[row.path] = { ...row.rec, status, was: row.base };
      return prune(next);
    });
  }, []);

  useHotkeys({ escape: () => { if (menu) { closeMenu(true); return; } setSel(null); setSideOpen(false); } });

  const branch = useMemo(() => (sel ? new Set([sel, ...P.up(sel), ...P.down(sel)]) : null), [sel, P]);
  const edges = useMemo(() => P.edges.map((e) => {
    const hi = !!branch && branch.has(e.raw.source) && branch.has(e.raw.target);
    const dim = branch ? !hi : onlyGaps;
    return {
      id: e.id, source: e.source, target: e.target, sourceHandle: e.sourceHandle, targetHandle: e.targetHandle, type: 'link',
      focusable: false, selectable: false, className: `${hi ? 'is-hi' : ''} ${dim ? 'is-dim' : ''}`, data: { label: e.label, hi },
    };
  }), [P, branch, onlyGaps]);

  const view = useMemo(() => ({ sel, branch, onlyGaps, evals, key }), [sel, branch, onlyGaps, evals, key]);
  const measuring = placedKey !== key;

  return (
    <View.Provider value={view}>
      <div className={`app ${narrow ? 'narrow' : ''} ${resizing ? 'resizing' : ''}`} style={{ '--side-w': `${sideW}px`, '--ins-w': `${insW}px` }}>
        <main className={`canvas ${measuring ? 'measuring' : ''}`} ref={canvasRef} onKeyDown={(e) => {
          const nid = e.target && e.target.closest && e.target.closest('.react-flow__node-part')?.dataset?.id;
          if (nid && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); pick(raw(nid)); }
        }}>
          <ReactFlow
            nodes={nodes} edges={edges} onNodesChange={onNodesChange} nodeTypes={nodeTypes} edgeTypes={edgeTypes}
            onNodeClick={(_, node) => { if (node.type === 'part') { const id = raw(node.id); if (id === sel) setSel(null); else { setSel(id); setSheet(true); } } }}
            onPaneClick={() => setSel(null)} minZoom={0.15} maxZoom={1.8}
            onMoveStart={(e) => { if (e) fitted.current = false; }}
            nodesDraggable={false} nodesConnectable={false} elementsSelectable={false}
            proOptions={{ hideAttribution: true }} aria-label={`Стек раздела ${P.sec.name}`}
          >
            <Background gap={24} size={1.1} color="var(--grid)" bgColor="transparent" />
          </ReactFlow>
        </main>

        <Sidebar current={key} onSelect={selectSection} open={sideOpen} onClose={() => setSideOpen(false)}
          evals={evals} overrides={overrides} onReset={() => setOverrides({})} />
        {narrow && sideOpen && <div className="scrim" onClick={() => setSideOpen(false)} aria-hidden="true" />}

        <header className="toolbar">
          {narrow && <button type="button" className="tb-btn" onClick={() => setSideOpen(true)} aria-label="Сервисы и разделы">{Ico.sidebar()}</button>}
          <div className="tb-title">
            <span className="tb-text">
              <span className="tb-group">{P.sec.group.name}</span>
              <span className="tb-sep" aria-hidden="true">{Ico.chevron(9)}</span>
              <b>{P.sec.name}</b>
            </span>
          </div>
          <div className="seg" role="group" aria-label="Что показать">
            <button type="button" className={!onlyGaps ? 'on' : ''} aria-pressed={!onlyGaps} onClick={() => setOnlyGaps(false)}>Все</button>
            <button type="button" className={onlyGaps ? 'on' : ''} aria-pressed={onlyGaps} onClick={() => { setOnlyGaps(true); setSel(null); }}>Проблемы</button>
          </div>
        </header>

        <div className="zoom" role="group" aria-label="Масштаб">
          <button type="button" onClick={() => { fitted.current = false; rf.zoomOut({ duration: reduce ? 0 : 220 }); }} aria-label="Отдалить">{Ico.minus()}</button>
          <button type="button" onClick={() => fit(true)} aria-label="Вписать схему">{Ico.fit()}</button>
          <button type="button" onClick={() => { fitted.current = false; rf.zoomIn({ duration: reduce ? 0 : 220 }); }} aria-label="Приблизить">{Ico.plus()}</button>
        </div>

        <aside className={`inspector ${sheet ? 'open' : ''}`} aria-label="Подробности">
          {narrow && (
            <button type="button" className="grabber" onClick={() => setSheet((v) => !v)} aria-expanded={sheet}>
              <span className="grab-bar" />
              <span className="grab-text">{sel ? P.byId[sel].name : `${P.sec.name}: ${E.total.no ? `${E.total.no} нет в бэкапе` : E.total.unknown ? `${E.total.unknown} не выяснено` : 'всё в бэкапе'}`}</span>
            </button>
          )}
          <div className="ins-scroll">
            {sel ? <Detail P={P} E={E} id={sel} onPick={pick} onBack={() => setSel(null)} onOpen={openMenu} /> : <Overview P={P} E={E} onPick={pick} />}
          </div>
        </aside>

        {!narrow && (
          <>
            <Resizer side="left" value={sideW} spec={SIDE} onStart={() => setResizing(true)} onResize={(v) => resize('left', v)} onEnd={endResize} />
            <Resizer side="right" value={insW} spec={INS} onStart={() => setResizing(true)} onResize={(v) => resize('right', v)} onEnd={endResize} />
          </>
        )}

        {menu && <StatusMenu menu={menu} onClose={closeMenu} onPick={(s) => { setStatus(menu.row, s); closeMenu(true); }} />}
      </div>
    </View.Provider>
  );
}

const rootEl = document.getElementById('root');
try {
  if (!window.React || !window.ReactDOM || !window.ReactFlow) throw new Error('cdn');
  if (!DATA) {
    rootEl.innerHTML = '<div class="boot-error"><b>Нет данных для карты.</b><span>Соберите страницу скриптом build_map.py из JSON по формату data-format.md.</span></div>';
  } else {
    window.ReactDOM.createRoot(rootEl).render(<ReactFlowProvider><MapApp /></ReactFlowProvider>);
  }
} catch (err) {
  rootEl.innerHTML = '<div class="boot-error"><b>Не удалось запустить карту.</b><span>React или React Flow не загрузились с CDN (cdnjs, jsDelivr). Проверьте доступ к этим адресам и обновите страницу.</span></div>';
  console.error(err);
}

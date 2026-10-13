import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { ReactFlow, ReactFlowProvider, Background, Handle, Position, useReactFlow, BaseEdge, EdgeLabelRenderer, getSmoothStepPath } from '@xyflow/react';
import { layout, plural } from './layout.js';
import { KindIcon, Ico } from './icons.jsx';
import { useReducedMotion, useMedia, useHotkeys } from './shared.jsx';

// Карта стека с отметками бэкапа. Данные — JSON в <script id="map-data"> (формат: references/data-format.md скилла).

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

// ── Нормализация: снисходительно к неполным данным, всё лишнее отбрасываем
const STATUS = new Set(['yes', 'no', 'skip', 'unknown']);
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
function leaves(items) { return items.flatMap((it) => (it.children ? it.children.map((c) => ({ ...c, parent: it.name, note: c.note || (c.own ? undefined : it.note) })) : [it])); }
function statsOf(items) {
  const s = { yes: 0, no: 0, skip: 0, unknown: 0 };
  const l = leaves(items);
  for (const x of l) s[x.status]++;
  s.total = l.length;
  s.state = !l.length ? 'none' : s.no ? (s.yes ? 'partial' : 'missing') : s.unknown ? 'unknown' : s.yes ? 'ok' : 'skip';
  return s;
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
  return { title: raw.title || 'Бэкапы судного дня', subtitle: raw.subtitle || 'Каталог критичных данных', services };
}

const DATA = readData();
const NODE_W = 196, NODE_H = 76, ROW = 134, TRAY_PAD = 20, TRAY_TOP = 32, TRAY_BOTTOM = 14;
const SECTIONS = DATA ? DATA.services.flatMap((g) => g.sections.map((s) => ({ ...s, group: g, key: `${g.id}/${s.id}` }))) : [];

const cache = new Map();
function prepare(sec) {
  if (cache.has(sec.key)) return cache.get(sec.key);
  const byId = Object.fromEntries(sec.nodes.map((n) => [n.id, { ...n, stats: statsOf(n.items) }]));
  const out = Object.fromEntries(sec.nodes.map((n) => [n.id, []]));
  const inc = Object.fromEntries(sec.nodes.map((n) => [n.id, []]));
  for (const e of sec.edges) { out[e.source].push(e.target); inc[e.target].push(e.source); }
  const reach = (start, adj) => { const seen = new Set(); const stack = [start]; while (stack.length) for (const n of adj[stack.pop()]) if (!seen.has(n)) { seen.add(n); stack.push(n); } return seen; };
  const layers = LAYERS.filter((l) => sec.nodes.some((n) => n.layer === l.id));
  const L = layout({ layers, nodes: sec.nodes, edges: sec.edges }, { nodeW: NODE_W, rowGap: ROW, gapX: 14 });
  const total = { yes: 0, no: 0, skip: 0, unknown: 0 };
  for (const n of Object.values(byId)) for (const k of Object.keys(total)) total[k] += n.stats[k];
  const listOf = (status) => Object.values(byId).flatMap((n) => leaves(n.items).filter((x) => x.status === status).map((x) => ({ ...x, node: n })));
  const p = `${sec.key}:`;
  const deco = layers.slice(1).map((l) => {
    const i = layers.indexOf(l);
    return {
      id: `${p}tray-${l.id}`, type: 'tray', position: { x: L.minX - TRAY_PAD, y: L.layerY[i] - TRAY_TOP },
      data: { name: l.name, count: L.rows[i].length, w: L.maxX - L.minX + TRAY_PAD * 2, h: TRAY_TOP + NODE_H + TRAY_BOTTOM, i },
      draggable: false, selectable: false, focusable: false, connectable: false, zIndex: -1,
    };
  });
  const parts = sec.nodes.map((n) => ({
    id: `${p}${n.id}`, type: 'part', position: L.pos[n.id], data: { n: byId[n.id], i: layers.findIndex((l) => l.id === n.layer) },
    draggable: false, connectable: false, style: { width: NODE_W },
  }));
  const edges = sec.edges.map((e) => {
    const a = byId[e.source], b = byId[e.target];
    const la = layers.findIndex((l) => l.id === a.layer), lb = layers.findIndex((l) => l.id === b.layer);
    let h = { sourceHandle: 's', targetHandle: 't' };
    if (la === lb) h = L.pos[e.source].x < L.pos[e.target].x ? { sourceHandle: 'sr', targetHandle: 'tl' } : { sourceHandle: 'sl', targetHandle: 'tr' };
    else if (la > lb) h = { sourceHandle: 'su', targetHandle: 'td' }; // связь снизу вверх
    return { id: `${p}${e.source}→${e.target}`, source: `${p}${e.source}`, target: `${p}${e.target}`, label: e.label, raw: e, ...h };
  });
  const res = {
    sec, byId, out, inc, total, prefix: p, nodes: [...deco, ...parts], edges,
    missing: listOf('no'), unknown: listOf('unknown'),
    bounds: { x: L.minX - TRAY_PAD, y: 0, w: L.maxX - L.minX + TRAY_PAD * 2, h: L.layerY[layers.length - 1] + NODE_H + TRAY_BOTTOM },
    up: (id) => reach(id, inc), down: (id) => reach(id, out),
  };
  cache.set(sec.key, res);
  return res;
}
const SEC_TOTALS = Object.fromEntries(SECTIONS.map((s) => [s.key, prepare(s).total]));

const View = createContext({});

// ── Ноды
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
  const { sel, branch, onlyGaps, P } = useContext(View);
  const n = data.n;
  const [, grp] = KIND[n.kind] || ['', 'root'];
  const root = n.layer === 'root';
  let state = '';
  if (sel) state = n.id === sel ? 'is-sel' : branch.has(n.id) ? 'is-rel' : 'is-dim';
  else if (onlyGaps && !root) state = n.stats.no || n.stats.unknown ? 'is-hit' : 'is-dim';
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
          <span className="p-name" title={n.name}>{n.name}</span>
          <span className="p-tech">{n.tech}</span>
        </span>
      </div>
      <Badge s={n.stats} total={root ? P.total : null} />
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

function Sidebar({ current, onSelect, open, onClose }) {
  const [q, setQ] = useState('');
  const [shut, setShut] = useState(() => new Set());
  const s = q.trim().toLowerCase();
  const match = (sec) => !s || `${sec.name} ${sec.group.name}`.toLowerCase().includes(s)
    || sec.nodes.some((n) => `${n.name} ${n.tech}`.toLowerCase().includes(s) || leaves(n.items).some((x) => `${x.parent || ''}.${x.name}`.toLowerCase().includes(s)));
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
          const missing = secs.reduce((a, x) => a + SEC_TOTALS[x.key].no, 0);
          return (
            <section key={g.id} className="sb-group">
              <button type="button" className={`sb-ghead ${closed ? 'closed' : ''}`} aria-expanded={!closed}
                onClick={() => setShut((v) => { const nv = new Set(v); if (nv.has(g.id)) nv.delete(g.id); else nv.add(g.id); return nv; })}>
                <span className="sb-chev">{Ico.chevron(10)}</span>
                <span>{g.name}</span>
                {closed && missing > 0 && <span className="sb-gcount">{missing}</span>}
              </button>
              {!closed && (
                <ul>
                  {secs.map((x) => (
                    <li key={x.key}>
                      <button type="button" className={`sb-row ${current === x.key ? 'on' : ''}`} aria-current={current === x.key ? 'page' : undefined} onClick={() => onSelect(x.key)}>
                        <span className="sb-ico"><KindIcon kind={x.icon} size={15} /></span>
                        <span className="sb-name">{x.name}</span>
                        <Accessory t={SEC_TOTALS[x.key]} />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          );
        })}
      </div>
      <p className="sb-foot"><span className="sb-miss">N</span> нет в бэкапе <span className="sb-unk">?</span> не выяснено</p>
    </nav>
  );
}

// ── Инспектор
function StatusIcon({ status }) {
  if (status === 'yes') return <span className="si si-yes" title="В бэкапе">{Ico.check(15)}</span>;
  if (status === 'no') return <span className="si si-no" title="Нет в бэкапе">{Ico.cross(15)}</span>;
  if (status === 'unknown') return <span className="si si-unknown" title="Не выяснено">{Ico.question(15)}</span>;
  return <span className="si si-skip" title="Бэкап не нужен">{Ico.dash(15)}</span>;
}

function ItemRow({ it, nested }) {
  const [label, icon] = TYPE[it.type] || TYPE.other;
  const sub = it.status === 'yes' ? it.where : it.note;
  return (
    <li className={`item ${nested ? 'nested' : ''} is-${it.status}`}>
      <span className="it-ico" title={label}><KindIcon kind={icon} size={14} /></span>
      <span className="it-main">
        <span className="it-name"><code>{it.name}</code>{it.size && <small>{it.size}</small>}</span>
        {sub && <span className="it-sub">{sub}</span>}
      </span>
      <StatusIcon status={it.status} />
    </li>
  );
}

function ItemList({ items }) {
  return (
    <ul className="items">
      {items.map((it) => (
        <React.Fragment key={it.name}>
          <ItemRow it={it} />
          {it.children && it.children.map((c) => <ItemRow key={c.name} nested it={c.own ? c : { ...c, where: undefined, note: undefined }} />)}
        </React.Fragment>
      ))}
    </ul>
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
            <li key={`${x.node.id}-${x.parent || ''}-${x.name}`}>
              <button type="button" onClick={() => onPick(x.node.id)}>
                <span className="it-ico" title={label}><KindIcon kind={icon} size={14} /></span>
                <span className="it-main">
                  <span className="it-name"><code>{x.parent ? `${x.parent}.${x.name}` : x.name}</code></span>
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

function Overview({ P, onPick }) {
  const { sec, total } = P;
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
      <GapList title="Нет в бэкапе" list={P.missing} onPick={onPick} tone="no" />
      <GapList title="Не выяснено" list={P.unknown} onPick={onPick} tone="unknown" />
      {!P.missing.length && !P.unknown.length && <p className="all-ok">{Ico.check(16)} Всё критичное в бэкапе</p>}
      <p className="hint">Выберите компонент на схеме, чтобы увидеть, что в нём хранится.</p>
    </div>
  );
}

function Detail({ P, id, onPick, onBack }) {
  const n = P.byId[id];
  const [kindLabel] = KIND[n.kind] || ['Раздел'];
  return (
    <div className="ins-body" key={`${P.sec.key}-${id}`}>
      <button type="button" className="back" onClick={onBack}>{Ico.back(13)}{P.sec.name}</button>
      <p className="eyebrow">{kindLabel} · {LAYER_NAME[n.layer]}</p>
      <h2>{n.name}</h2>
      {n.tech && <p className="tech">{n.tech}</p>}
      {n.desc && <p className="lead">{n.desc}</p>}
      {n.items.length ? (
        <section>
          <div className="sec-head"><h3>Что хранится</h3><Badge s={n.stats} /></div>
          <ItemList items={n.items} />
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
  const canvasRef = useRef(null);
  const P = prepare(SECTIONS.find((s) => s.key === key));

  const fit = useCallback((animate) => {
    const el = canvasRef.current;
    if (!el) return;
    const W = el.clientWidth, H = el.clientHeight;
    const ins = narrow ? { l: 12, r: 12, t: 76, b: 84 } : { l: 288, r: 368, t: 76, b: 76 };
    const aw = Math.max(120, W - ins.l - ins.r), ah = Math.max(120, H - ins.t - ins.b);
    const b = P.bounds;
    let zoom = Math.min(aw / b.w, ah / b.h, 1.05);
    if (narrow) zoom = Math.max(zoom, 0.55);
    const x = ins.l + (aw - b.w * zoom) / 2 - b.x * zoom;
    const y = narrow ? ins.t - b.y * zoom : ins.t + Math.max(0, (ah - b.h * zoom) / 2) - b.y * zoom;
    rf.setViewport({ x, y, zoom }, { duration: animate && !reduce ? 520 : 0 });
  }, [rf, reduce, narrow, P]);

  useEffect(() => { const t = setTimeout(() => fit(false), 30); return () => clearTimeout(t); }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const el = canvasRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return undefined;
    let w = 0;
    const ro = new ResizeObserver(() => { if (Math.abs(el.clientWidth - w) > 40) { w = el.clientWidth; fit(false); } });
    ro.observe(el);
    return () => ro.disconnect();
  }, [fit]);

  const selectSection = (k) => { setKey(k); setSel(null); setSideOpen(false); setSheet(false); };
  const raw = (id) => id.slice(P.prefix.length);
  const pick = useCallback((id) => {
    setSel(id);
    setSheet(true);
    const node = rf.getNode(`${P.prefix}${id}`);
    if (node) rf.setCenter(node.position.x + NODE_W / 2, node.position.y + NODE_H / 2, { zoom: Math.max(rf.getZoom(), 0.8), duration: reduce ? 0 : 450 });
  }, [rf, reduce, P]);

  useHotkeys({ escape: () => { setSel(null); setSideOpen(false); } });

  const branch = useMemo(() => (sel ? new Set([sel, ...P.up(sel), ...P.down(sel)]) : null), [sel, P]);
  const edges = useMemo(() => P.edges.map((e) => {
    const hi = !!branch && branch.has(e.raw.source) && branch.has(e.raw.target);
    const dim = branch ? !hi : onlyGaps;
    return {
      id: e.id, source: e.source, target: e.target, sourceHandle: e.sourceHandle, targetHandle: e.targetHandle, type: 'link',
      focusable: false, selectable: false, className: `${hi ? 'is-hi' : ''} ${dim ? 'is-dim' : ''}`, data: { label: e.label, hi },
    };
  }), [P, branch, onlyGaps]);

  const view = useMemo(() => ({ sel, branch, onlyGaps, P }), [sel, branch, onlyGaps, P]);

  return (
    <View.Provider value={view}>
      <div className={`app ${narrow ? 'narrow' : ''}`}>
        <main className="canvas" ref={canvasRef} onKeyDown={(e) => {
          const nid = e.target?.closest?.('.react-flow__node-part')?.dataset?.id;
          if (nid && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); pick(raw(nid)); }
        }}>
          <ReactFlow
            nodes={P.nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes}
            onNodeClick={(_, node) => { if (node.type === 'part') { const id = raw(node.id); if (id === sel) setSel(null); else { setSel(id); setSheet(true); } } }}
            onPaneClick={() => setSel(null)} minZoom={0.15} maxZoom={1.8}
            nodesDraggable={false} nodesConnectable={false} elementsSelectable={false}
            proOptions={{ hideAttribution: true }} aria-label={`Стек раздела ${P.sec.name}`}
          >
            <Background gap={24} size={1.1} color="var(--grid)" bgColor="transparent" />
          </ReactFlow>
        </main>

        <Sidebar current={key} onSelect={selectSection} open={sideOpen} onClose={() => setSideOpen(false)} />
        {narrow && sideOpen && <div className="scrim" onClick={() => setSideOpen(false)} aria-hidden="true" />}

        <header className="toolbar">
          {narrow && <button type="button" className="tb-btn" onClick={() => setSideOpen(true)} aria-label="Сервисы и разделы">{Ico.sidebar()}</button>}
          <div className="tb-title">
            <span className="tb-group">{P.sec.group.name}</span>
            <span className="tb-sep">{Ico.chevron(9)}</span>
            <b>{P.sec.name}</b>
          </div>
          <div className="seg" role="group" aria-label="Что показать">
            <button type="button" className={!onlyGaps ? 'on' : ''} aria-pressed={!onlyGaps} onClick={() => setOnlyGaps(false)}>Все</button>
            <button type="button" className={onlyGaps ? 'on' : ''} aria-pressed={onlyGaps} onClick={() => { setOnlyGaps(true); setSel(null); }}>Пробелы</button>
          </div>
        </header>

        <div className="zoom" role="group" aria-label="Масштаб">
          <button type="button" onClick={() => rf.zoomOut({ duration: reduce ? 0 : 220 })} aria-label="Отдалить">{Ico.minus()}</button>
          <button type="button" onClick={() => fit(true)} aria-label="Вписать схему">{Ico.fit()}</button>
          <button type="button" onClick={() => rf.zoomIn({ duration: reduce ? 0 : 220 })} aria-label="Приблизить">{Ico.plus()}</button>
        </div>

        <aside className={`inspector ${sheet ? 'open' : ''}`} aria-label="Подробности">
          {narrow && (
            <button type="button" className="grabber" onClick={() => setSheet((v) => !v)} aria-expanded={sheet}>
              <span />
              {sel ? P.byId[sel].name : `${P.sec.name}: ${P.total.no ? `${P.total.no} нет в бэкапе` : P.total.unknown ? `${P.total.unknown} не выяснено` : 'всё в бэкапе'}`}
            </button>
          )}
          <div className="ins-scroll">
            {sel ? <Detail P={P} id={sel} onPick={pick} onBack={() => setSel(null)} /> : <Overview P={P} onPick={pick} />}
          </div>
        </aside>
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

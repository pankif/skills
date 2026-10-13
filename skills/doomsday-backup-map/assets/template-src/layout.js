// Раскладка по слоям: порядок внутри слоя — по барицентру соседей, чтобы связи меньше пересекались.

export function layout(data, opt = {}) {
  // rowH — своя высота дорожки для слоя; stagger — слой «кирпичиком» в два ряда, чтобы схема была уже
  const { nodeW = 208, gapX = 26, rowGap = 150, sweeps = 8, widths = {}, rowH = {}, stagger = {}, staggerDy = 100, staggerGap = 64 } = opt;
  const w = (id) => widths[id] || nodeW;
  const rows = data.layers.map((l) => data.nodes.filter((n) => n.layer === l.id).map((n) => n.id));
  const nbr = Object.fromEntries(data.nodes.map((n) => [n.id, []]));
  for (const e of data.edges) { nbr[e.source].push(e.target); nbr[e.target].push(e.source); }
  const layerY = [];
  data.layers.reduce((y, l, i) => { layerY[i] = y; return y + (rowH[l.id] || rowGap) + (stagger[l.id] ? staggerDy : 0); }, 0);
  const pos = {};
  const placeRow = (li) => {
    const ids = rows[li];
    if (stagger[data.layers[li].id] && ids.length > 2) {
      const step = (Math.max(...ids.map(w)) + staggerGap) / 2;
      const total = (ids.length - 1) * step + w(ids[ids.length - 1]);
      ids.forEach((id, i) => { pos[id] = { x: -total / 2 + i * step, y: layerY[li] + (i % 2) * staggerDy }; });
      return;
    }
    const total = ids.reduce((s, id) => s + w(id), 0) + gapX * (ids.length - 1);
    let x = -total / 2;
    for (const id of ids) { pos[id] = { x, y: layerY[li] }; x += w(id) + gapX; }
  };
  rows.forEach((_, li) => placeRow(li));
  const center = (id) => pos[id].x + w(id) / 2;
  for (let it = 0; it < sweeps; it++) {
    const order = rows.map((_, i) => (it % 2 ? rows.length - 1 - i : i));
    for (const li of order) {
      const scored = rows[li].map((id, i) => {
        const ns = nbr[id];
        const bc = ns.length ? ns.reduce((s, n) => s + center(n), 0) / ns.length : center(id);
        return [id, bc, i];
      });
      scored.sort((a, b) => a[1] - b[1] || a[2] - b[2]);
      rows[li] = scored.map((s) => s[0]);
      placeRow(li);
    }
  }
  let minX = Infinity, maxX = -Infinity;
  for (const id in pos) { minX = Math.min(minX, pos[id].x); maxX = Math.max(maxX, pos[id].x + w(id)); }
  const last = data.layers.length - 1;
  const height = layerY[last] + (rowH[data.layers[last].id] || rowGap) + (stagger[data.layers[last].id] ? staggerDy : 0);
  return { pos, rows, minX, maxX, rowGap, layerY, height };
}

export function plural(n, forms) {
  const a = Math.abs(n) % 100, b = a % 10;
  if (a > 10 && a < 20) return forms[2];
  if (b > 1 && b < 5) return forms[1];
  if (b === 1) return forms[0];
  return forms[2];
}

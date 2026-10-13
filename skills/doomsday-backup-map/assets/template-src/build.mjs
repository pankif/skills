// Пересборка assets/map-template.html из исходников. Нужна, только если меняете вид карты.
//
//   cd skills/doomsday-backup-map/assets/template-src
//   npm i --no-save esbuild@0.24
//   node build.mjs
//
// React 18 и React Flow 12 страница грузит с CDN, в шаблон встраиваются только код карты,
// её стили и базовые стили React Flow (rf-base.css — base.css из @xyflow/react 12.3.6).
import * as esbuild from 'esbuild';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const CDN = {
  react: 'https://cdnjs.cloudflare.com/ajax/libs/react/18.3.1/umd/react.production.min.js',
  reactDom: 'https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.3.1/umd/react-dom.production.min.js',
  xyflow: 'https://cdn.jsdelivr.net/npm/@xyflow/react@12.3.6/dist/umd/index.js',
};
// React и React Flow берутся из глобальных переменных, которые создают UMD-сборки с CDN
const globals = {
  name: 'globals',
  setup(b) {
    const map = { react: 'window.React', 'react-dom': 'window.ReactDOM', '@xyflow/react': 'window.ReactFlow', 'react/jsx-runtime': 'window.jsxRuntime' };
    b.onResolve({ filter: /^(react|react-dom|@xyflow\/react|react\/jsx-runtime)$/ }, (a) => ({ path: a.path, namespace: 'g' }));
    b.onLoad({ filter: /.*/, namespace: 'g' }, (a) => ({ contents: `module.exports = ${map[a.path]};`, loader: 'js' }));
  },
};
// React 18 UMD не отдаёт react/jsx-runtime, а UMD-сборка React Flow его ждёт
const JSX_SHIM = 'window.jsxRuntime=(function(R){function j(t,p,k){return R.createElement(t,k===undefined?p:Object.assign({},p,{key:k}))}return{jsx:j,jsxs:j,Fragment:R.Fragment}})(window.React);';

const res = await esbuild.build({
  entryPoints: [path.join(here, 'main.jsx')],
  bundle: true, write: false, format: 'iife', minify: true, target: ['chrome100', 'safari15', 'firefox100'],
  jsx: 'automatic', plugins: [globals], charset: 'utf8', logLevel: 'warning',
});
const js = res.outputFiles[0].text.replace(/<\/script/gi, '<\\/script');
const css = ['rf-base.css', 'style.css'].map((f) => fs.readFileSync(path.join(here, f), 'utf8')).join('\n');
const html = `<title>__MAP_TITLE__</title>
<style>
${css}
</style>
<div id="root"></div>
<script type="application/json" id="map-data">__MAP_DATA__</script>
<script src="${CDN.react}"></script>
<script src="${CDN.reactDom}"></script>
<script>${JSX_SHIM}</script>
<script src="${CDN.xyflow}"></script>
<script>${js}</script>
`;
const out = path.join(here, '..', 'map-template.html');
fs.writeFileSync(out, html);
console.log('Готово:', path.relative(process.cwd(), out), `${(html.length / 1024).toFixed(1)} КБ`);

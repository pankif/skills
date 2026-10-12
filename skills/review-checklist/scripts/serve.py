"""Локальный сервер чек-листа: страница + автосохранение решений в файл.

python3 serve.py OUT_DIR [--port 8765]

Открыть: http://127.0.0.1:8765/<key>.html
Решения пишутся в OUT_DIR/<key>-decisions.json после каждого клика.
Слушает только 127.0.0.1. Остановить — Ctrl+C. Только стандартная библиотека.
"""
import json
import os
import re
import sys
import threading
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

API = re.compile(r'^/(?:.*/)?api/([A-Za-z0-9_-]+)/decisions(?:/([A-Za-z0-9_.~-]+))?/?$')
LOCK = threading.Lock()


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map,
                      '.html': 'text/html; charset=utf-8', '.json': 'application/json; charset=utf-8',
                      '.md': 'text/markdown; charset=utf-8'}

    def _file(self, key):
        return os.path.join(self.directory, key + '-decisions.json')

    def _read(self, key):
        try:
            with open(self._file(key), encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, ValueError):
            return {}

    def _send(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        m = API.match(self.path.split('?')[0])
        if not m:
            return super().do_GET()
        with LOCK:
            data = self._read(m.group(1))
        self._send(200, data)

    def do_PUT(self):
        m = API.match(self.path.split('?')[0])
        if not m or not m.group(2):
            return self._send(404, {'error': 'not_found'})
        try:
            length = int(self.headers.get('Content-Length') or 0)
            body = json.loads(self.rfile.read(min(length, 65536)) or b'{}')
        except ValueError:
            return self._send(400, {'error': 'bad_json'})
        entry = {'status': str(body.get('status', ''))[:16],
                 'comment': str(body.get('comment', ''))[:4000],
                 'at': body.get('at') or datetime.now(timezone.utc).isoformat()}
        key, item = m.group(1), m.group(2)
        with LOCK:
            data = self._read(key)
            data[item] = entry
            tmp = self._file(key) + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self._file(key))
        self._send(200, {'ok': True})

    def log_message(self, fmt, *args):
        if self.command == 'PUT':
            sys.stderr.write('сохранено: %s\n' % self.path)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    root = os.path.abspath(sys.argv[1])
    port = int(sys.argv[sys.argv.index('--port') + 1]) if '--port' in sys.argv else 8765
    server = ThreadingHTTPServer(('127.0.0.1', port), partial(Handler, directory=root))
    pages = [f for f in sorted(os.listdir(root)) if f.endswith('.html')]
    for p in pages:
        print(f'http://127.0.0.1:{port}/{p}')
    print('Решения сохраняются в', root, '— остановить: Ctrl+C', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()

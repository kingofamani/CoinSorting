"""接線圖轉 PNG 用的小伺服器（只在本機用；用法見上一層 make_wiring.py 的說明）。

GET  /...               ：提供 接線圖/ 資料夾裡的檔案（SVG、render.html）
POST /save?name=xxx.png ：把收到的 PNG 存到 接線圖/xxx.png（只接受單純檔名、.png 結尾）
"""
import http.server
import os
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 接線圖/
PORT = 8768


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        name = urllib.parse.parse_qs(u.query).get('name', [''])[0]
        if u.path != '/save' or not name.endswith('.png') or os.path.basename(name) != name:
            self.send_error(400, 'bad request')
            return
        n = int(self.headers.get('Content-Length', '0'))
        data = self.rfile.read(n)
        if not data.startswith(b'\x89PNG'):
            self.send_error(400, 'not png')
            return
        with open(os.path.join(ROOT, name), 'wb') as f:
            f.write(data)
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(f'saved {len(data)} bytes'.encode())


if __name__ == '__main__':
    http.server.ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()

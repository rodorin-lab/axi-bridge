#!/usr/bin/env python3
"""
AXI MJPEG Stream Server — scrcpyキャプチャ画像をリアルタイムMJPEG配信
ノア（ChatGPT）から http://localhost:8646/stream でアクセス可能

使い方:
1. このサーバー起動
2. Chromeで http://localhost:8646/stream を開く（ピクチャインピクチャ推奨）
3. ChatGPT通話中にChromeのカメラ/画面共有でそのタブを選ぶ（可能なら）

または:
- http://localhost:8646/snapshot で最新1枚取得（Vision API用）
"""

import http.server
import threading
import time
import os
import io
import socketserver

CAPTURE_DIR = os.path.expanduser("~/scrcpy-capture")
LATEST_IMG = os.path.join(CAPTURE_DIR, "latest.png")
PORT = 8646

# 画像キャッシュ
cached_jpg = b''
cache_lock = threading.Lock()
last_mtime = 0

def get_latest_frame():
    """最新のスクリーンショットをJPEGで取得"""
    global cached_jpg, last_mtime
    try:
        mtime = os.path.getmtime(LATEST_IMG)
        if mtime != last_mtime:
            last_mtime = mtime
            # PNGからJPEG変換（ffmpeg使用、軽量化）
            import subprocess
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", LATEST_IMG, "-f", "image2pipe",
                 "-vcodec", "mjpeg", "-q:v", "5", "-vf", "scale=640:-1", "-"],
                capture_output=True, timeout=3
            )
            with cache_lock:
                cached_jpg = result.stdout
    except:
        pass
    return cached_jpg

class StreamHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/stream':
            self.send_response(200)
            self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=--jpgboundary')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            
            try:
                while True:
                    jpg = get_latest_frame()
                    if jpg:
                        self.wfile.write(b'--jpgboundary\r\n')
                        self.send_header('Content-type', 'image/jpeg')
                        self.send_header('Content-length', str(len(jpg)))
                        self.end_headers()
                        self.wfile.write(jpg)
                        self.wfile.write(b'\r\n')
                    time.sleep(0.5)  # 2FPS
            except:
                pass
        
        elif self.path == '/snapshot':
            jpg = get_latest_frame()
            if jpg:
                self.send_response(200)
                self.send_header('Content-type', 'image/jpeg')
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(jpg)
            else:
                self.send_error(404, 'No image')
        
        elif self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<html><body><h1>AXI MJPEG Stream</h1>'
                           b'<img src="/stream" style="width:100%"><br>'
                           b'<a href="/snapshot">Snapshot</a></body></html>')
        else:
            self.send_error(404)
    
    def log_message(self, format, *args):
        pass  # ログ抑制

class ThreadedServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

if __name__ == "__main__":
    server = ThreadedServer(('0.0.0.0', PORT), StreamHandler)
    print(f"[mjpeg] AXI Stream Server起動: http://localhost:{PORT}/")
    print(f"[mjpeg] ストリーム: http://localhost:{PORT}/stream")
    print(f"[mjpeg] スナップショット: http://localhost:{PORT}/snapshot")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
        print("[mjpeg] 停止")
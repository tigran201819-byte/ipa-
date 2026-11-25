import ctypes
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

try:
    cpp = ctypes.CDLL("./libnative.dylib")
    cpp_res = cpp.fast_sum(40, 2)
except Exception as e:
    cpp_res = str(e)

class BridgeHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        data = {"status": "ok", "cpp_result": cpp_res}
        self.wfile.write(json.dumps(data).encode())

HTTPServer(("127.0.0.1", 8765), BridgeHandler).serve_forever()

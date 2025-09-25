from http.server import BaseHTTPRequestHandler
import json
import os

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        response = {
            'status': 'ok',
            'message': 'API is running',
            'version': '1.0.0'
        }
        self.wfile.write(json.dumps(response).encode())
        return

import os
import http.server
import socketserver
import threading

# 1. Your existing task logic goes here
def run_my_hackathon_task():
    print("START")
    # ... your logic for EASY, MEDIUM, HARD ...
    print("END")

# 2. A simple server to keep the container alive and passing healthchecks
class HealthCheckHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"status": "healthy"}')

def start_server():
    # Standard port is 8080; use 0.0.0.0 to be visible outside the container
    with socketserver.TCPServer(("0.0.0.0", 8080), HealthCheckHandler) as httpd:
        print("INFO: Started")
        # Run your actual task in the background so it doesn't block the server
        threading.Thread(target=run_my_hackathon_task).start()
        httpd.serve_forever()

if __name__ == "__main__":
    start_server()
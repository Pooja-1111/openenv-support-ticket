"""
OpenEnv Hackathon - Support Ticket Triage
FINAL WORKING VERSION - Blocking server, verified connections
"""

import os
import json
import requests
import sys
import time
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

def log(m): 
    print(m, flush=True)
    sys.stdout.flush()

# ==================== CONFIG ====================
PORT = 8080
TASK = os.getenv("TASK_NAME", "support_ticket_triage")
ENDPOINT = os.getenv(f"SCALER_ROUTE_TASK_{TASK.upper()}_ENDPOINT", "http://env-task-server:8000")

log(f"[INIT] Starting with PORT={PORT}")

# ==================== HEALTHCHECK ====================
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): 
        pass
    
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"status":"healthy"}')
        log("[HEALTHCHECK] Responded 200 OK")

# ==================== TRIAGE ====================
def triage(msg):
    m = msg.lower()
    if any(w in m for w in ["charge","bill","payment","refund","$"]):
        return {"decision":"escalate","team":"billing","urgency":"high","draft_response":"Escalating to billing.","reasoning":"Billing"}
    if any(w in m for w in ["password","login","access"]):
        return {"decision":"resolve","team":"support","urgency":"medium","draft_response":"Use password reset.","reasoning":"Self-service"}
    if any(w in m for w in ["bug","crash","error","broken"]):
        return {"decision":"escalate","team":"engineering","urgency":"high","draft_response":"Escalating to engineering.","reasoning":"Bug"}
    if any(w in m for w in ["critical","outage","emergency"]):
        return {"decision":"escalate","team":"engineering","urgency":"critical","draft_response":"Critical! Escalating.","reasoning":"Critical"}
    if any(w in m for w in ["feature","suggestion","add"]):
        return {"decision":"needs_more_info","team":"product","urgency":"low","draft_response":"Tell us more.","reasoning":"Feature"}
    return {"decision":"needs_more_info","team":"support","urgency":"medium","draft_response":"Need more info.","reasoning":"Unclear"}

# ==================== TASKS ====================
def run_tasks():
    log("[TASKS] Starting task execution")
    for level in ["easy", "medium", "hard"]:
        log(f"START {level}")
        try:
            r = requests.post(f"{ENDPOINT}/reset", params={"task_type":level}, timeout=30)
            obs = r.json().get("observation",{})
            for i in range(10):
                act = triage(obs.get("customer_message",""))
                r = requests.post(f"{ENDPOINT}/step", json=act, timeout=30)
                d = r.json()
                log("STEP")
                if d.get("done"): 
                    log(f"[TASKS] {level} completed")
                    break
                obs = d.get("observation",{})
        except Exception as e:
            log(f"[ERROR] {level}: {e}")
        log("END")
        time.sleep(1)
    log("[TASKS] All tasks completed")

# ==================== MAIN ====================
def main():
    # CRITICAL: Create server with address reuse
    HTTPServer.allow_reuse_address = True
    
    # Try to bind to port with retry
    for attempt in range(5):
        try:
            server = HTTPServer(("0.0.0.0", PORT), Handler)
            log(f"[SERVER] Bound to port {PORT} on attempt {attempt+1}")
            break
        except OSError as e:
            log(f"[SERVER] Bind attempt {attempt+1} failed: {e}")
            time.sleep(1)
    else:
        log("[SERVER] FAILED to bind to port")
        sys.exit(1)
    
    # Start server in daemon thread (so main thread can run tasks)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    log("[SERVER] Server thread started")
    
    # CRITICAL: Wait and verify server is actually accepting connections
    time.sleep(2)
    
    # Self-test to ensure server works
    try:
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_sock.settimeout(5)
        test_sock.connect(("127.0.0.1", PORT))
        test_sock.send(b"GET / HTTP/1.0\r\n\r\n")
        response = test_sock.recv(1024)
        test_sock.close()
        log(f"[SERVER] Self-test passed: {response[:50]}...")
    except Exception as e:
        log(f"[SERVER] Self-test failed: {e}")
        # Continue anyway, maybe external access works
    
    log("[SERVER] Ready for healthchecks!")
    
    # Run tasks in main thread
    run_tasks()
    
    # Keep alive for final healthchecks
    log("[MAIN] Keeping alive for 30s...")
    time.sleep(30)
    log("[MAIN] Exiting")

if __name__ == "__main__":
    main()
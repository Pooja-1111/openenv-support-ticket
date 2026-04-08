"""
OpenEnv Hackathon - FINAL ATTEMPT
Try different ports and binding approaches
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

# Try multiple ports - OpenEnv might use different one
PORTS = [8080, 80, 8000, 3000]
TASK = os.getenv("TASK_NAME", "support_ticket_triage")
ENDPOINT = os.getenv(f"SCALER_ROUTE_TASK_{TASK.upper()}_ENDPOINT", "http://env-task-server:8000")

log(f"[INIT] Will try ports: {PORTS}")

# ==================== HEALTHCHECK ====================
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"status":"healthy"}')
        log(f"[HEALTHCHECK] 200 OK on path: {self.path}")

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
    log("[TASKS] Starting")
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
                if d.get("done"): break
                obs = d.get("observation",{})
        except Exception as e:
            log(f"[ERROR] {e}")
        log("END")
        time.sleep(1)

# ==================== MAIN ====================
def main():
    HTTPServer.allow_reuse_address = True
    
    # Try to bind to any available port
    server = None
    for port in PORTS:
        try:
            server = HTTPServer(("0.0.0.0", port), Handler)
            log(f"[SERVER] SUCCESS! Bound to port {port}")
            break
        except OSError as e:
            log(f"[SERVER] Port {port} failed: {e}")
    
    if not server:
        log("[SERVER] CRITICAL: Could not bind to any port!")
        sys.exit(1)
    
    # Start server
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    log("[SERVER] Thread started")
    
    # Wait for server to be ready
    time.sleep(3)
    
    # Run tasks
    run_tasks()
    
    # Keep alive
    log("[MAIN] Keeping alive...")
    time.sleep(60)

if __name__ == "__main__":
    main()
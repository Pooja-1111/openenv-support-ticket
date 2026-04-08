"""
NUCLEAR OPTION - Absolute minimal healthcheck
"""
import os, json, requests, sys, time
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

def log(m): print(m, flush=True)

# Config
PORT = 8080
TASK = os.getenv("TASK_NAME", "support_ticket_triage")
ENDPOINT = os.getenv(f"SCALER_ROUTE_TASK_{TASK.upper()}_ENDPOINT", "http://env-task-server:8000")

# Simplest possible handler
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

# Fallback logic only - no LLM dependencies
def triage(msg):
    m = msg.lower()
    if "charge" in m or "bill" in m or "$" in m:
        return {"decision": "escalate", "team": "billing", "urgency": "high", "draft_response": "Escalating to billing.", "reasoning": "Billing issue"}
    if "password" in m or "login" in m:
        return {"decision": "resolve", "team": "support", "urgency": "medium", "draft_response": "Reset password at /reset.", "reasoning": "Self-service"}
    if "bug" in m or "crash" in m or "error" in m:
        return {"decision": "escalate", "team": "engineering", "urgency": "high", "draft_response": "Escalating to engineering.", "reasoning": "Technical issue"}
    return {"decision": "needs_more_info", "team": "support", "urgency": "medium", "draft_response": "Need more info.", "reasoning": "Unclear"}

def run_task(level):
    log(f"START {level}")
    try:
        r = requests.post(f"{ENDPOINT}/reset", params={"task_type": level}, timeout=30)
        obs = r.json().get("observation", {})
        for i in range(10):
            msg = obs.get("customer_message", "")
            act = triage(msg)
            r = requests.post(f"{ENDPOINT}/step", json=act, timeout=30)
            d = r.json()
            log("STEP")
            if d.get("done"): break
            obs = d.get("observation", {})
    except Exception as e:
        log(f"ERROR: {e}")
    log("END")

def main():
    # Start server FIRST
    s = HTTPServer(('', PORT), H)
    t = threading.Thread(target=s.serve_forever, daemon=True)
    t.start()
    log(f"[SERVER] Started on {PORT}")
    time.sleep(1)  # Ensure ready
    
    # Run all tasks
    for level in ["easy", "medium", "hard"]:
        run_task(level)
        time.sleep(1)
    
    # Stay alive
    time.sleep(60)

if __name__ == "__main__":
    main()
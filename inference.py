"""
OpenEnv Hackathon - Support Ticket Triage
FINAL WORKING VERSION
"""

import os
import json
import requests
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

def log(m): 
    print(m, flush=True)
    sys.stdout.flush()

# ==================== CONFIG ====================
PORT = 8080
TASK = os.getenv("TASK_NAME", "support_ticket_triage")
ENDPOINT = os.getenv(f"SCALER_ROUTE_TASK_{TASK.upper()}_ENDPOINT", "http://env-task-server:8000")

log(f"[INIT] Port: {PORT}")
log(f"[INIT] Endpoint: {ENDPOINT}")

# ==================== HEALTHCHECK HANDLER ====================
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): 
        pass
    
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "healthy"}).encode())
    
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

# ==================== TRIAGE LOGIC ====================
def triage(msg):
    m = msg.lower()
    if any(w in m for w in ["charge", "bill", "payment", "refund", "$", "invoice"]):
        return {
            "decision": "escalate",
            "team": "billing", 
            "urgency": "high",
            "draft_response": "I'm escalating this to our billing team immediately.",
            "reasoning": "Billing issue"
        }
    if any(w in m for w in ["password", "login", "access", "forgot"]):
        return {
            "decision": "resolve",
            "team": "support",
            "urgency": "medium", 
            "draft_response": "Please use the password reset link sent to your email.",
            "reasoning": "Self-service password reset"
        }
    if any(w in m for w in ["bug", "crash", "error", "broken", "not working"]):
        return {
            "decision": "escalate",
            "team": "engineering",
            "urgency": "high",
            "draft_response": "I'm escalating this technical issue to our engineering team.",
            "reasoning": "Technical bug"
        }
    if any(w in m for w in ["critical", "outage", "emergency", "security"]):
        return {
            "decision": "escalate",
            "team": "engineering",
            "urgency": "critical",
            "draft_response": "Critical issue! Escalating immediately.",
            "reasoning": "Critical incident"
        }
    if any(w in m for w in ["feature", "suggestion", "add", "request"]):
        return {
            "decision": "needs_more_info",
            "team": "product",
            "urgency": "low",
            "draft_response": "Thank you for the suggestion! Could you provide more details?",
            "reasoning": "Feature request needs details"
        }
    return {
        "decision": "needs_more_info",
        "team": "support",
        "urgency": "medium",
        "draft_response": "Thank you for contacting us. Could you provide more details?",
        "reasoning": "Need more information"
    }

# ==================== TASK RUNNER ====================
def run_level(level):
    log(f"[TASK] Starting {level}")
    log("START")
    
    try:
        # Reset
        r = requests.post(f"{ENDPOINT}/reset", params={"task_type": level}, timeout=30)
        obs = r.json().get("observation", {})
        
        # Process tickets
        for i in range(10):
            msg = obs.get("customer_message", "")
            ticket_id = obs.get("ticket_id", "unknown")
            log(f"[TASK] Ticket {i+1}: {ticket_id}")
            
            action = triage(msg)
            log(f"[TASK] Action: {action['decision']} -> {action['team']}")
            
            r = requests.post(f"{ENDPOINT}/step", json=action, timeout=30)
            data = r.json()
            log("STEP")
            
            if data.get("done"):
                log(f"[TASK] Done! Score: {data.get('reward', {}).get('overall_score', 0)}")
                break
            
            obs = data.get("observation", {})
            
    except Exception as e:
        log(f"[ERROR] {e}")
    
    log("END")

# ==================== MAIN ====================
def main():
    # Start healthcheck server FIRST
    log("[SERVER] Starting healthcheck server...")
    
    try:
        server = HTTPServer(("0.0.0.0", PORT), Handler)
        server.allow_reuse_address = True
        
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        
        log(f"[SERVER] Running on port {PORT}")
        time.sleep(1)  # Ensure server is ready
        
    except Exception as e:
        log(f"[SERVER] FAILED: {e}")
        return
    
    # Run tasks
    for level in ["easy", "medium", "hard"]:
        run_level(level)
        time.sleep(1)
    
    # Keep alive
    log("[MAIN] Complete, keeping alive...")
    time.sleep(60)

if __name__ == "__main__":
    main()
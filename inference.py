import os
import json
import requests
import traceback
import threading
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from openai import OpenAI

# 1. FORCE LOG FLUSHING: Ensures logs appear immediately in the validator dashboard
def log(message):
    print(message)
    sys.stdout.flush()

# --- CONFIGURATION ---
# Using 0.0.0.0 is MANDATORY for Docker containers to be reachable
API_BASE_URL = os.getenv("API_BASE_URL", "http://0.0.0.0:8080")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
HF_TOKEN = os.getenv("HF_TOKEN")

# Initialize Client with aggressive error handling
try:
    client = OpenAI(
        api_key=HF_TOKEN or os.environ.get("OPENAI_API_KEY", "dummy_key"),
        base_url="https://api-inference.huggingface.co/v1/" if HF_TOKEN else None
    )
    log("INFO: OpenAI Client Initialized")
except Exception as e:
    log(f"ERROR: Client Init Failed: {e}")
    client = None

# --- CORE LOGIC ---
def run_task(task_type: str, max_tickets: int = 3):
    log("START")
    try:
        # Added timeout to prevent hanging the whole process
        reset_resp = requests.post(f"{API_BASE_URL}/reset", params={"task_type": task_type}, timeout=15)
        if reset_resp.status_code != 200:
            log(f"ERROR: Reset failed for {task_type}")
            log("END")
            return
        
        observation = reset_resp.json().get("observation", {})
        ticket_count = 0
        
        while ticket_count < max_tickets:
            customer_message = observation.get("customer_message", "No message")
            
            try:
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[{"role": "user", "content": f"Analyze: {customer_message}. Return JSON."}],
                    response_format={ "type": "json_object" }
                )
                action_data = json.loads(response.choices[0].message.content)
            except Exception as e:
                log(f"FALLBACK: LLM Error: {e}")
                action_data = {"decision": "escalate", "team": "support", "urgency": "medium"}

            step_resp = requests.post(f"{API_BASE_URL}/step", json=action_data, timeout=15)
            log("STEP")
            
            if step_resp.status_code != 200 or step_resp.json().get("done"):
                break
            
            observation = step_resp.json().get("observation", {})
            ticket_count += 1
    except Exception as e:
        log(f"ERROR in run_task: {e}")
    
    log("END")

def main_execution():
    log("INFO: Starting Evaluation Loop")
    for difficulty in ["easy", "medium", "hard"]:
        run_task(difficulty)
    log("INFO: Evaluation Loop Finished")

# --- THE FAIL-SAFE SERVER ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # This answers the 'HEALTHCHECK' from the validator
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "healthy"}).encode())

    def do_POST(self):
        # Some validators trigger via POST /run
        if self.path == '/run':
            threading.Thread(target=main_execution).start()
            self.send_response(202)
        else:
            self.send_response(404)
        self.end_headers()

def run_server():
    # 8080 is the standard port for OpenEnv/Scaler hackathons
    PORT = 8080
    log(f"INFO: Started")
    
    server_address = ('0.0.0.0', PORT)
    httpd = HTTPServer(server_address, HealthCheckHandler)
    
    # Run the main task in a background thread IMMEDIATELY on start
    task_thread = threading.Thread(target=main_execution)
    task_thread.daemon = True
    task_thread.start()
    
    # Keep the server running forever to answer Healthchecks
    httpd.serve_forever()

if __name__ == "__main__":
    try:
        run_server()
    except Exception as e:
        log(f"CRITICAL: Server crashed: {e}")
        traceback.print_exc()
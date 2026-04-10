import os
import sys
import json
import requests
import traceback
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime

# --- CONFIGURATION (STRICTLY FROM ENV) ---
PORT = 8080
# The platform provides this endpoint for the environment
TASK_ENDPOINT = os.getenv("SCALER_ROUTE_TASK_SUPPORT_TICKET_TRIAGE_ENDPOINT", "http://env-task-server:8000")
HF_TOKEN = os.getenv("HF_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")

# --- STDOUT LOGGING HELPER (FLUSH=TRUE) ---
def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)
    sys.stdout.flush()

# --- LLM INITIALIZATION ---
client = None
try:
    if HF_TOKEN:
        from openai import OpenAI
        client = OpenAI(api_key=HF_TOKEN, base_url="https://api-inference.huggingface.co/v1/")
        log("[LLM] Initialized Hugging Face Inference API")
    elif OPENAI_API_KEY:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        log("[LLM] Initialized OpenAI API")
except Exception as e:
    log(f"[LLM] Initialization failed: {e}")

# --- TRIAGE LOGIC ---

def fallback_triage_logic(message):
    message = message.lower()
    
    # 1. Critical Incident / Revenue Impact
    if any(word in message for word in ["critical", "outage", "down", "revenue", "security breach", "data loss"]):
        return {
            "decision": "escalate",
            "team": "engineering",
            "urgency": "critical",
            "draft_response": "We have identified this as a critical incident. Our engineering team has been alerted and is investigating immediately.",
            "reasoning": "Detected keywords indicating high-impact outage or security risk."
        }
    
    # 2. Billing / Payment
    if any(word in message for word in ["charged", "payment", "refund", "invoice", "billing"]):
        return {
            "decision": "escalate",
            "team": "billing",
            "urgency": "high",
            "draft_response": "I've escalated your billing concern to our finance team for a priority review of the charges.",
            "reasoning": "Request involves financial transactions or billing disputes."
        }
    
    # 3. Technical Bugs / Crashes
    if any(word in message for word in ["crash", "error", "bug", "broken", "stuck", "not working"]):
        return {
            "decision": "escalate",
            "team": "engineering",
            "urgency": "high",
            "draft_response": "I am sorry for the technical issue. I have escalated this to our engineering team with your details.",
            "reasoning": "Detected technical failure or software bug."
        }
        
    # 4. Account Access
    if any(word in message for word in ["password", "reset", "login", "can't log", "forgot"]):
        return {
            "decision": "resolve",
            "team": "support",
            "urgency": "medium",
            "draft_response": "You can reset your password by clicking 'Forgot Password' on the login page. I've sent a reset link to your email.",
            "reasoning": "Standard account access request that can be resolved via self-service."
        }
        
    # 5. Feature Requests
    if any(word in message for word in ["feature", "add", "integrate", "would be nice", "can you"]):
        return {
            "decision": "needs_more_info",
            "team": "product",
            "urgency": "low",
            "draft_response": "Thank you for the suggestion! Could you provide more details on how this feature would help your workflow?",
            "reasoning": "Product suggestion requiring requirement gathering."
        }

    # Default fallback
    return {
        "decision": "needs_more_info",
        "team": "support",
        "urgency": "medium",
        "draft_response": "I've received your message. Could you please provide a few more details so I can assist you better?",
        "reasoning": "General inquiry requiring more context for accurate triage."
    }

def analyze_ticket(message):
    if client:
        try:
            log(f"[LLM] Analyzing message: {message[:50]}...")
            prompt = f"Analyze this support ticket and return a JSON triage decision:\nTicket: {message}\n\nRequired format: {{\"decision\": \"...\", \"team\": \"...\", \"urgency\": \"...\", \"draft_response\": \"...\", \"reasoning\": \"...\"}}"
            
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                timeout=25
            )
            
            result = json.loads(response.choices[0].message.content)
            # Basic validation of required fields
            required = ["decision", "team", "urgency", "draft_response", "reasoning"]
            if all(k in result for k in required):
                return result
            else:
                log(f"[LLM] Missing fields in JSON: {result.keys()}")
        except Exception as e:
            log(f"[LLM] Error: {e}")
            
    return fallback_triage_logic(message)

# --- TASK EXECUTION LOOP ---

def run_task(difficulty):
    log("INFO: Started")
    log("START")
    try:
        # 1. Reset Environment
        reset_url = f"{TASK_ENDPOINT}/reset"
        log(f"[TASK] POST {reset_url}?task_type={difficulty}")
        
        try:
            r = requests.post(reset_url, params={"task_type": difficulty}, timeout=30)
            log(f"[TASK] Status: {r.status_code}")
            if r.status_code != 200:
                log(f"[ERROR] Reset failed: {r.text}")
                log("END")
                return
            
            data = r.json()
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            log(f"[ERROR] Reset request failed: {e}")
            log("END")
            return

        obs = data.get("observation", {})
        session_id = data.get("session_id")
        count = 0
        
        # 2. Process Tickets
        while count < 10:
            msg = obs.get("customer_message")
            if not msg:
                log("[TASK] No more tickets or missing message")
                break
                
            log(f"[TASK] Processing Ticket {count+1}: {msg[:60]}...")
            
            # Triage
            action = analyze_ticket(msg)
            
            # Step
            step_url = f"{TASK_ENDPOINT}/step"
            log(f"[TASK] POST {step_url} session_id={session_id}")
            
            try:
                r = requests.post(
                    step_url, 
                    params={"session_id": session_id}, 
                    json=action, 
                    timeout=30
                )
                log("STEP") # Mandatory log
                
                if r.status_code != 200:
                    log(f"[ERROR] Step failed: {r.status_code} - {r.text}")
                    break
                    
                data = r.json()
            except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
                log(f"[ERROR] Step request failed: {e}")
                break
            
            count += 1
            if data.get("done"):
                log("[TASK] Mission completed successfully")
                break
                
            obs = data.get("observation", {})
            
    except Exception as e:
        log(f"[CRITICAL] Unexpected error in task loop: {e}")
        log(traceback.format_exc())
    
    log("END")

def main_execution():
    log("[SYSTEM] Waiting for server to stabilize...")
    time.sleep(5)
    for diff in ["easy", "medium", "hard"]:
        log(f"[SYSTEM] Starting {diff} mission...")
        run_task(diff)
        time.sleep(2)
    log("[SYSTEM] All missions concluded. Keeping container alive for healthchecks.")
    while True:
        time.sleep(60)

# --- HEALTHCHECK SERVER ---

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"status":"healthy"}')

    def log_message(self, format, *args):
        # Silence logs to keep stdout clean
        return

def run_server():
    log(f"[SERVER] Starting healthcheck on 0.0.0.0:{PORT}")
    try:
        httpd = HTTPServer(('0.0.0.0', PORT), HealthCheckHandler)
        
        # START TASK AS DAEMON
        log("[SERVER] Launching task execution thread")
        task_thread = threading.Thread(target=main_execution, daemon=True)
        task_thread.start()
        
        # RUN SERVER IN MAIN THREAD
        httpd.serve_forever()
    except Exception as e:
        log(f"[FATAL] Server crash: {e}")
        log(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    run_server()
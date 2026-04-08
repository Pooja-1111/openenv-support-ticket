"""
OpenEnv Hackathon - Support Ticket Triage Inference Script
"""

import os
import json
import requests
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

def log(message):
    print(message, flush=True)
    sys.stdout.flush()

# ==================== CONFIGURATION ====================
HEALTHCHECK_PORT = 8080
TASK_NAME = os.getenv("TASK_NAME", "support_ticket_triage")
TASK_ENDPOINT = os.getenv(
    f"SCALER_ROUTE_TASK_{TASK_NAME.upper()}_ENDPOINT",
    os.getenv("TASK_ENDPOINT", "http://env-task-server:8000")
)

MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
HF_TOKEN = os.getenv("HF_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

log(f"[CONFIG] Task Endpoint: {TASK_ENDPOINT}")
log(f"[CONFIG] Model: {MODEL_NAME}")

# ==================== LLM CLIENT SETUP ====================
client = None

try:
    if HF_TOKEN:
        from openai import OpenAI
        client = OpenAI(api_key=HF_TOKEN, base_url="https://api-inference.huggingface.co/v1/")
        log("[LLM] Using Hugging Face Inference API")
    elif OPENAI_API_KEY:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        log("[LLM] Using OpenAI API")
    else:
        log("[LLM] WARNING: No API key found - using fallback logic")
except Exception as e:
    log(f"[LLM] ERROR: Failed to initialize client: {e}")

# ==================== TRIAGE LOGIC ====================
def analyze_ticket_with_llm(customer_message: str) -> dict:
    if not client:
        return fallback_triage_logic(customer_message)
    
    try:
        prompt = f"""Analyze this support ticket and return a JSON response:

Ticket: "{customer_message}"

Respond with JSON in this exact format:
{{
    "decision": "resolve" or "escalate" or "needs_more_info",
    "team": "billing" or "engineering" or "product" or "support",
    "urgency": "low" or "medium" or "high" or "critical",
    "draft_response": "Your professional response to the customer",
    "reasoning": "Why you made this decision"
}}

Rules:
- Billing issues (charges, refunds, payments) → escalate to billing team, high urgency
- Password resets, account access → resolve with instructions, medium urgency
- Technical bugs, crashes, errors → escalate to engineering, high urgency
- Feature requests → needs_more_info OR escalate to product, low urgency
- Critical incidents (revenue loss, security, outages) → escalate, critical urgency
"""
        
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=500
        )
        
        content = response.choices[0].message.content
        action = json.loads(content)
        
        required_fields = ["decision", "team", "urgency", "draft_response", "reasoning"]
        for field in required_fields:
            if field not in action:
                return fallback_triage_logic(customer_message)
        
        return action
        
    except Exception as e:
        log(f"[LLM] Error: {e}")
        return fallback_triage_logic(customer_message)

def fallback_triage_logic(customer_message: str) -> dict:
    message_lower = customer_message.lower()
    
    if any(word in message_lower for word in ["charged", "charge", "payment", "refund", "billing", "invoice", "$"]):
        return {
            "decision": "escalate",
            "team": "billing",
            "urgency": "high",
            "draft_response": "I apologize for the billing issue. I'm escalating this to our billing team for immediate investigation.",
            "reasoning": "Billing issue requires finance team review."
        }
    
    if any(word in message_lower for word in ["password", "reset", "login", "log in", "can't access", "forgot"]):
        return {
            "decision": "resolve",
            "team": "support",
            "urgency": "medium",
            "draft_response": "I can help with that! Please visit our password reset page and follow the instructions.",
            "reasoning": "Password reset is a self-service action."
        }
    
    if any(word in message_lower for word in ["crash", "error", "bug", "not working", "broken", "stuck", "freeze"]):
        return {
            "decision": "escalate",
            "team": "engineering",
            "urgency": "high",
            "draft_response": "I apologize for the technical issue. I'm escalating this to our engineering team.",
            "reasoning": "Technical bug requires engineering team analysis."
        }
    
    if any(word in message_lower for word in ["critical", "emergency", "outage", "down", "revenue", "security", "breach"]):
        return {
            "decision": "escalate",
            "team": "engineering",
            "urgency": "critical",
            "draft_response": "This is marked as critical. I'm escalating immediately to our engineering team.",
            "reasoning": "Critical incident requires immediate attention."
        }
    
    if any(word in message_lower for word in ["feature", "add", "integrate", "new", "would be nice", "suggestion"]):
        return {
            "decision": "needs_more_info",
            "team": "product",
            "urgency": "low",
            "draft_response": "Thank you for the suggestion! Can you provide more details about how you'd use this feature?",
            "reasoning": "Feature request requires more details."
        }
    
    return {
        "decision": "needs_more_info",
        "team": "support",
        "urgency": "medium",
        "draft_response": "Thank you for contacting us. Can you provide more details about your issue?",
        "reasoning": "Need more information to properly triage this ticket."
    }

# ==================== TASK EXECUTION ====================
def run_task(task_type: str, max_tickets: int = 10):
    log(f"[TASK] Starting task_type={task_type}")
    log("START")
    
    try:
        log(f"[TASK] Calling {TASK_ENDPOINT}/reset?task_type={task_type}")
        reset_response = requests.post(
            f"{TASK_ENDPOINT}/reset",
            params={"task_type": task_type},
            timeout=30
        )
        
        if reset_response.status_code != 200:
            log(f"[TASK] ERROR: Reset failed with status {reset_response.status_code}")
            log("END")
            return
        
        reset_data = reset_response.json()
        observation = reset_data.get("observation", {})
        log(f"[TASK] Reset successful")
        
        ticket_count = 0
        done = False
        
        while not done and ticket_count < max_tickets:
            ticket_id = observation.get("ticket_id", "unknown")
            customer_message = observation.get("customer_message", "")
            
            log(f"[TASK] Processing ticket #{ticket_count + 1}: {ticket_id}")
            
            action = analyze_ticket_with_llm(customer_message)
            
            log(f"[TASK] Submitting action: {action['decision']} → {action['team']}")
            
            step_response = requests.post(
                f"{TASK_ENDPOINT}/step",
                json=action,
                timeout=30
            )
            
            if step_response.status_code != 200:
                log(f"[TASK] ERROR: Step failed with status {step_response.status_code}")
                break
            
            step_data = step_response.json()
            log("STEP")
            
            done = step_data.get("done", False)
            reward = step_data.get("reward", {})
            score = reward.get("overall_score", 0.0)
            
            log(f"[TASK] Score: {score:.2f}, Done: {done}")
            
            observation = step_data.get("observation", {})
            ticket_count += 1
            
            if done:
                log(f"[TASK] Task completed after {ticket_count} tickets")
                break
        
        log(f"[TASK] Finished task_type={task_type}")
        
    except Exception as e:
        log(f"[TASK] ERROR: {e}")
        log(f"[TASK] Traceback: {traceback.format_exc()}")
    
    log("END")

def main_execution():
    log("[MAIN] Starting main execution")
    
    for difficulty in ["easy", "medium", "hard"]:
        run_task(difficulty, max_tickets=10)
        time.sleep(1)
    
    log("[MAIN] All tasks completed")

# ==================== HEALTHCHECK SERVER ====================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        try:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {"status": "healthy", "message": "OK"}
            self.wfile.write(json.dumps(response).encode())
        except Exception as e:
            log(f"[HEALTHCHECK] Error: {e}")
    
    def do_HEAD(self):
        try:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
        except Exception as e:
            log(f"[HEALTHCHECK] HEAD Error: {e}")

def run_server():
    """
    Start healthcheck server and run tasks.
    """
    server_address = ('0.0.0.0', HEALTHCHECK_PORT)
    
    try:
        httpd = HTTPServer(server_address, HealthCheckHandler)
        httpd.allow_reuse_address = True
        
        log(f"[SERVER] Starting healthcheck server on port {HEALTHCHECK_PORT}")
        
        # Start server in background thread
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()
        
        # Give server time to start
        time.sleep(1)
        
        log("[SERVER] Healthcheck server is running")
        
        # Run tasks
        main_execution()
        
        # Keep alive for final checks
        log("[SERVER] Tasks complete, keeping alive...")
        time.sleep(30)
        
        log("[SERVER] Shutting down")
        httpd.shutdown()
        
    except Exception as e:
        log(f"[SERVER] CRITICAL ERROR: {e}")
        import traceback
        log(f"[SERVER] Traceback: {traceback.format_exc()}")
        raise

# ==================== ENTRY POINT ====================
if __name__ == "__main__":
    try:
        run_server()
    except Exception as e:
        import traceback
        log(f"[CRITICAL] Fatal error: {e}")
        log(f"[CRITICAL] Traceback: {traceback.format_exc()}")
        sys.exit(1)
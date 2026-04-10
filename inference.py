#!/usr/bin/env python3
"""
OpenEnv Hackathon - Support Ticket Triage - BULLETPROOF INFERENCE
This code is designed to pass ALL validator checks on the first try.
"""

import os
import sys
import platform
import json
import time
import requests
import traceback
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# ==================== DIAGNOSTIC LOGGING ====================
print(f"INFO: System Python Version: {sys.version}", flush=True)
print(f"INFO: OS Platform: {platform.platform()}", flush=True)
print("INFO: Started", flush=True)

# ==================== CRITICAL: IMMEDIATE LOGGING ====================
def log(message):
    """Log with immediate flush - validator reads stdout in real-time."""
    print(message, flush=True)
    sys.stdout.flush()

# ==================== CONFIGURATION ====================
PORT = 8080

# CRITICAL: Read task endpoint from environment (NOT localhost!)
TASK_ENDPOINT = os.getenv(
    "SCALER_ROUTE_TASK_SUPPORT_TICKET_TRIAGE_ENDPOINT",
    os.getenv("TASK_ENDPOINT", "http://env-task-server:8000")
)

MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
HF_TOKEN = os.getenv("HF_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

log(f"[INIT] Task Endpoint: {TASK_ENDPOINT}")
log(f"[INIT] Model: {MODEL_NAME}")
log(f"[INIT] HF Token: {'✓' if HF_TOKEN else '✗'}")
log(f"[INIT] OpenAI Key: {'✓' if OPENAI_KEY else '✗'}")

# ==================== LLM CLIENT SETUP ====================
client = None

try:
    if HF_TOKEN:
        from openai import OpenAI
        client = OpenAI(
            api_key=HF_TOKEN,
            base_url="https://api-inference.huggingface.co/v1/"
        )
        log("[LLM] ✓ Hugging Face client initialized")
    elif OPENAI_KEY:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_KEY)
        log("[LLM] ✓ OpenAI client initialized")
    else:
        log("[LLM] ⚠ No API keys - using fallback logic only")
except Exception as e:
    log(f"[LLM] ✗ Client init failed: {e}")
    client = None

# ==================== FALLBACK TRIAGE LOGIC ====================
def fallback_triage(message):
    """Rule-based triage when LLM is unavailable or fails."""
    msg_lower = message.lower()
    
    # Billing issues - escalate to billing
    if any(w in msg_lower for w in ["charged", "charge", "payment", "refund", "billing", "invoice", "$"]):
        return {
            "decision": "escalate",
            "team": "billing",
            "urgency": "high",
            "draft_response": "I apologize for the billing issue. Escalating to our billing team immediately for investigation and resolution.",
            "reasoning": "Billing issues require finance team intervention for refund processing and account correction."
        }
    
    # Password/login - resolve with instructions
    if any(w in msg_lower for w in ["password", "reset", "login", "log in", "access", "forgot", "locked out"]):
        return {
            "decision": "resolve",
            "team": "support",
            "urgency": "medium",
            "draft_response": "I can help! Please visit our password reset page and follow the instructions. You'll receive a reset link via email within minutes.",
            "reasoning": "Password reset is a standard self-service procedure that can be resolved with clear instructions."
        }
    
    # Critical incidents - immediate escalation
    if any(w in msg_lower for w in ["critical", "emergency", "outage", "down", "revenue", "security", "breach", "data loss"]):
        return {
            "decision": "escalate",
            "team": "engineering",
            "urgency": "critical",
            "draft_response": "This is marked as CRITICAL. Escalating immediately to our engineering team for urgent investigation.",
            "reasoning": "Critical incidents require immediate technical team attention to prevent further impact."
        }
    
    # Technical bugs - escalate to engineering
    if any(w in msg_lower for w in ["crash", "error", "bug", "not working", "broken", "stuck", "freeze", "slow"]):
        return {
            "decision": "escalate",
            "team": "engineering",
            "urgency": "high",
            "draft_response": "I apologize for the technical issue. Escalating to our engineering team for investigation and fix.",
            "reasoning": "Technical bugs require engineering analysis and potential code fixes."
        }
    
    # Feature requests - ask for details
    if any(w in msg_lower for w in ["feature", "add", "integrate", "new", "would be nice", "suggestion", "enhancement"]):
        return {
            "decision": "needs_more_info",
            "team": "product",
            "urgency": "low",
            "draft_response": "Thank you for the suggestion! Can you provide more details about your use case and how this feature would help?",
            "reasoning": "Feature requests need detailed requirements before routing to product team."
        }
    
    # Default - ask for clarification
    return {
        "decision": "needs_more_info",
        "team": "support",
        "urgency": "medium",
        "draft_response": "Thank you for contacting us. Can you provide more details about your issue so we can assist you better?",
        "reasoning": "Insufficient information to make informed triage decision."
    }

# ==================== LLM TRIAGE ====================
def llm_triage(message):
    """Attempt to use LLM for intelligent triage."""
    if not client:
        return None
    
    try:
        prompt = f"""You are a support ticket triage expert. Analyze this ticket and respond with ONLY valid JSON.

Customer message: "{message}"

Return JSON with these exact fields:
{{
    "decision": "resolve" | "escalate" | "needs_more_info",
    "team": "billing" | "engineering" | "product" | "support",
    "urgency": "low" | "medium" | "high" | "critical",
    "draft_response": "Professional response to customer",
    "reasoning": "Brief explanation of decision"
}}

Triage rules:
- Billing/payment issues → escalate to billing, high urgency
- Password/login → resolve with instructions, medium urgency
- Bugs/crashes → escalate to engineering, high urgency
- Feature requests → needs_more_info or route to product, low urgency
- Critical/outage/revenue loss → escalate, critical urgency"""

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=500,
            timeout=15
        )
        
        content = response.choices[0].message.content.strip()
        
        # Remove markdown code blocks if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        
        action = json.loads(content)
        
        # Validate required fields
        required = ["decision", "team", "urgency", "draft_response", "reasoning"]
        if not all(field in action for field in required):
            log(f"[LLM] ⚠ Missing fields, using fallback")
            return None
        
        # Validate enum values
        valid_decisions = ["resolve", "escalate", "needs_more_info"]
        valid_teams = ["billing", "engineering", "product", "support"]
        valid_urgency = ["low", "medium", "high", "critical"]
        
        if action["decision"] not in valid_decisions:
            log(f"[LLM] ⚠ Invalid decision: {action['decision']}")
            return None
        
        if action["team"] not in valid_teams:
            log(f"[LLM] ⚠ Invalid team: {action['team']}")
            return None
            
        if action["urgency"] not in valid_urgency:
            log(f"[LLM] ⚠ Invalid urgency: {action['urgency']}")
            return None
        
        log(f"[LLM] ✓ Valid response: {action['decision']} → {action['team']}")
        return action
        
    except json.JSONDecodeError as e:
        log(f"[LLM] ✗ JSON parse error: {e}")
        return None
    except Exception as e:
        log(f"[LLM] ✗ Error: {e}")
        return None

# ==================== ANALYZE TICKET ====================
def analyze_ticket(message):
    """Try LLM first, fallback to rules if it fails."""
    # Try LLM
    action = llm_triage(message)
    if action:
        return action
    
    # Fallback to rules
    log("[TRIAGE] Using fallback logic")
    return fallback_triage(message)

# ==================== TASK EXECUTION ====================
def run_task(difficulty):
    """Execute triage task for one difficulty level."""
    log(f"\n[TASK] ========== Starting {difficulty.upper()} ==========")
    log("START")
    
    try:
        # Step 1: Reset environment
        reset_url = f"{TASK_ENDPOINT}/reset"
        log(f"[TASK] Resetting: {reset_url}?task_type={difficulty}")
        
        try:
            reset_resp = requests.post(
                reset_url,
                params={"task_type": difficulty},
                timeout=30
            )
            
            if reset_resp.status_code != 200:
                log(f"[TASK] ✗ Reset failed: {reset_resp.status_code}")
                log(f"[TASK] Response: {reset_resp.text[:200]}")
                log("END")
                return
                
            reset_data = reset_resp.json()
            observation = reset_data.get("observation", {})
            log(f"[TASK] ✓ Reset OK - First ticket: {observation.get('ticket_id', 'unknown')}")
            
        except requests.exceptions.Timeout:
            log(f"[TASK] ✗ Reset timeout after 30s")
            log("END")
            return
        except requests.exceptions.ConnectionError:
            log(f"[TASK] ✗ Cannot connect to {TASK_ENDPOINT}")
            log("END")
            return
        except Exception as e:
            log(f"[TASK] ✗ Reset error: {e}")
            log("END")
            return
        
        # Step 2: Process tickets
        ticket_count = 0
        max_tickets = 20
        done = False
        
        while not done and ticket_count < max_tickets:
            ticket_id = observation.get("ticket_id", "unknown")
            customer_message = observation.get("customer_message", "")
            
            log(f"\n[TICKET {ticket_count + 1}] ID: {ticket_id}")
            log(f"[TICKET {ticket_count + 1}] Message: {customer_message[:80]}...")
            
            # Analyze ticket
            action = analyze_ticket(customer_message)
            log(f"[TICKET {ticket_count + 1}] Decision: {action['decision']} → {action['team']} ({action['urgency']})")
            
            # Submit action
            try:
                step_url = f"{TASK_ENDPOINT}/step"
                log(f"[TICKET {ticket_count + 1}] Submitting to {step_url}")
                
                step_resp = requests.post(
                    step_url,
                    json=action,
                    timeout=30,
                    headers={"Content-Type": "application/json"}
                )
                
                if step_resp.status_code != 200:
                    log(f"[TICKET {ticket_count + 1}] ✗ Step failed: {step_resp.status_code}")
                    log(f"[TICKET {ticket_count + 1}] Response: {step_resp.text[:200]}")
                    break
                
                step_data = step_resp.json()
                log("STEP")  # REQUIRED by validator
                
                # Check score
                reward = step_data.get("reward", {})
                score = reward.get("overall_score", 0.0)
                log(f"[TICKET {ticket_count + 1}] ✓ Score: {score:.2f}")
                
                # Check if done
                done = step_data.get("done", False)
                if done:
                    log(f"[TASK] ✓ Completed after {ticket_count + 1} tickets")
                    break
                
                # Get next observation
                observation = step_data.get("observation", {})
                ticket_count += 1
                
            except requests.exceptions.Timeout:
                log(f"[TICKET {ticket_count + 1}] ✗ Step timeout")
                break
            except requests.exceptions.ConnectionError:
                log(f"[TICKET {ticket_count + 1}] ✗ Connection error")
                break
            except Exception as e:
                log(f"[TICKET {ticket_count + 1}] ✗ Error: {e}")
                log(traceback.format_exc())
                break
        
        log(f"[TASK] Finished {difficulty}: {ticket_count} tickets processed")
        
    except Exception as e:
        log(f"[TASK] ✗ Fatal error: {e}")
        log(traceback.format_exc())
    
    log("END")

# ==================== MAIN EXECUTION ====================
def main_execution():
    """Run all difficulty levels."""
    log("\n[MAIN] ========== STARTING ALL TASKS ==========")
    
    try:
        for difficulty in ["easy", "medium", "hard"]:
            run_task(difficulty)
            time.sleep(1)  # Brief pause between levels
        
        log("\n[MAIN] ========== ALL TASKS COMPLETE ==========")
    except Exception as e:
        log(f"[MAIN] ✗ Critical error: {e}")
        log(traceback.format_exc())

# ==================== HEALTHCHECK SERVER ====================
class HealthCheckHandler(BaseHTTPRequestHandler):
    """Responds to validator healthcheck probes."""
    
    def log_message(self, format, *args):
        """Suppress default HTTP logging."""
        pass
    
    def do_GET(self):
        """Handle GET requests."""
        try:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status":"healthy"}')
        except Exception as e:
            log(f"[SERVER] ✗ Healthcheck error: {e}")

def run_server():
    """Start healthcheck server and execute tasks."""
    log(f"\n[SERVER] ========== STARTING HEALTHCHECK SERVER ==========")
    log(f"[SERVER] Listening on 0.0.0.0:{PORT}")
    
    try:
        server_address = ('0.0.0.0', PORT)
        httpd = HTTPServer(server_address, HealthCheckHandler)
        
        log("[SERVER] ✓ Server ready")
        log("[SERVER] Starting task execution in background...")
        
        # CRITICAL: Run task in daemon thread so server can respond to healthchecks
        task_thread = threading.Thread(target=main_execution, daemon=True)
        task_thread.start()
        
        log("[SERVER] ✓ Task thread started")
        log("[SERVER] Serving healthcheck requests...")
        
        # Server runs in main thread forever
        httpd.serve_forever()
        
    except Exception as e:
        log(f"[SERVER] ✗ Fatal error: {e}")
        log(traceback.format_exc())
        sys.exit(1)

# ==================== ENTRY POINT ====================
if __name__ == "__main__":
    log("\n" + "="*60)
    log("SUPPORT TICKET TRIAGE - INFERENCE ENGINE")
    log("="*60)
    
    try:
        run_server()
    except KeyboardInterrupt:
        log("\n[SHUTDOWN] Interrupted by user")
        sys.exit(0)
    except Exception as e:
        log(f"\n[CRITICAL] Unhandled exception: {e}")
        log(traceback.format_exc())
        sys.exit(1)
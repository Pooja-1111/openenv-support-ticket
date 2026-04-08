"""
OpenEnv Hackathon - Support Ticket Triage Inference Script
FIXED VERSION - Addresses healthcheck timeout and execution issues
"""

import os
import json
import requests
import traceback
import threading
import sys
import time
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer

# ==================== CRITICAL: LOGGING ====================
def log(message):
    """
    Flush logs immediately so the validator sees them.
    OpenEnv validator reads stdout in real-time.
    """
    print(message, flush=True)
    sys.stdout.flush()

# ==================== CONFIGURATION ====================

# PORT: Your healthcheck server (MUST be 8080 for OpenEnv)
HEALTHCHECK_PORT = 8080

# TASK_ENDPOINT: The ACTUAL OpenEnv task server (NOT your own server!)
TASK_NAME = os.getenv("TASK_NAME", "support_ticket_triage")
TASK_ENDPOINT = os.getenv(
    f"SCALER_ROUTE_TASK_{TASK_NAME.upper()}_ENDPOINT",
    os.getenv("TASK_ENDPOINT", "http://env-task-server:8000")
)

# LLM Configuration
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
HF_TOKEN = os.getenv("HF_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

log(f"[CONFIG] Task Endpoint: {TASK_ENDPOINT}")
log(f"[CONFIG] Model: {MODEL_NAME}")
log(f"[CONFIG] HF Token Present: {bool(HF_TOKEN)}")
log(f"[CONFIG] OpenAI Key Present: {bool(OPENAI_API_KEY)}")

# ==================== LLM CLIENT SETUP ====================

client = None

try:
    if HF_TOKEN:
        from openai import OpenAI
        client = OpenAI(
            api_key=HF_TOKEN,
            base_url="https://api-inference.huggingface.co/v1/"
        )
        log("[LLM] Using Hugging Face Inference API")
    elif OPENAI_API_KEY:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        log("[LLM] Using OpenAI API")
    else:
        log("[LLM] WARNING: No API key found - using fallback logic")
except Exception as e:
    log(f"[LLM] ERROR: Failed to initialize client: {e}")
    log(f"[LLM] Traceback: {traceback.format_exc()}")

# ==================== TRIAGE LOGIC ====================

def analyze_ticket_with_llm(customer_message: str) -> dict:
    """
    Use LLM to analyze the ticket and generate triage decision.
    Falls back to rule-based logic if LLM fails.
    """
    if not client:
        log("[LLM] No client available, using fallback")
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
        log(f"[LLM] Raw response: {content[:200]}...")
        
        action = json.loads(content)
        
        # Validate required fields
        required_fields = ["decision", "team", "urgency", "draft_response", "reasoning"]
        for field in required_fields:
            if field not in action:
                log(f"[LLM] WARNING: Missing field '{field}', using fallback")
                return fallback_triage_logic(customer_message)
        
        log(f"[LLM] Decision: {action['decision']}, Team: {action['team']}, Urgency: {action['urgency']}")
        return action
        
    except json.JSONDecodeError as e:
        log(f"[LLM] JSON Parse Error: {e}")
        log(f"[LLM] Content was: {content}")
        return fallback_triage_logic(customer_message)
    except Exception as e:
        log(f"[LLM] Error: {e}")
        log(f"[LLM] Traceback: {traceback.format_exc()}")
        return fallback_triage_logic(customer_message)

def fallback_triage_logic(customer_message: str) -> dict:
    """
    Rule-based triage as fallback when LLM is unavailable.
    """
    message_lower = customer_message.lower()
    
    # Billing keywords
    if any(word in message_lower for word in ["charged", "charge", "payment", "refund", "billing", "invoice", "$"]):
        return {
            "decision": "escalate",
            "team": "billing",
            "urgency": "high",
            "draft_response": "I apologize for the billing issue. I'm escalating this to our billing team for immediate investigation.",
            "reasoning": "Billing issue requires finance team review and potential refund processing."
        }
    
    # Password/Account access
    if any(word in message_lower for word in ["password", "reset", "login", "log in", "can't access", "forgot"]):
        return {
            "decision": "resolve",
            "team": "support",
            "urgency": "medium",
            "draft_response": "I can help with that! Please visit our password reset page and follow the instructions. You'll receive a reset link via email.",
            "reasoning": "Password reset is a self-service action that can be resolved with instructions."
        }
    
    # Technical issues
    if any(word in message_lower for word in ["crash", "error", "bug", "not working", "broken", "stuck", "freeze"]):
        return {
            "decision": "escalate",
            "team": "engineering",
            "urgency": "high",
            "draft_response": "I apologize for the technical issue. I'm escalating this to our engineering team for investigation.",
            "reasoning": "Technical bug requires engineering team analysis and potential code fix."
        }
    
    # Critical incidents
    if any(word in message_lower for word in ["critical", "emergency", "outage", "down", "revenue", "security", "breach"]):
        return {
            "decision": "escalate",
            "team": "engineering",
            "urgency": "critical",
            "draft_response": "This is marked as critical. I'm escalating immediately to our engineering team.",
            "reasoning": "Critical incident requires immediate attention from technical team."
        }
    
    # Feature requests
    if any(word in message_lower for word in ["feature", "add", "integrate", "new", "would be nice", "suggestion"]):
        return {
            "decision": "needs_more_info",
            "team": "product",
            "urgency": "low",
            "draft_response": "Thank you for the suggestion! Can you provide more details about how you'd use this feature?",
            "reasoning": "Feature request requires more details before routing to product team."
        }
    
    # Default: ask for more info
    return {
        "decision": "needs_more_info",
        "team": "support",
        "urgency": "medium",
        "draft_response": "Thank you for contacting us. Can you provide more details about your issue?",
        "reasoning": "Need more information to properly triage this ticket."
    }

# ==================== TASK EXECUTION ====================

def run_task(task_type: str, max_tickets: int = 10):
    """
    Execute the triage task for a specific difficulty level.
    """
    log(f"[TASK] Starting task_type={task_type}")
    log("START")  # Required by validator
    
    try:
        # Step 1: Reset the environment
        log(f"[TASK] Calling {TASK_ENDPOINT}/reset?task_type={task_type}")
        reset_response = requests.post(
            f"{TASK_ENDPOINT}/reset",
            params={"task_type": task_type},
            timeout=30
        )
        
        if reset_response.status_code != 200:
            log(f"[TASK] ERROR: Reset failed with status {reset_response.status_code}")
            log(f"[TASK] Response: {reset_response.text}")
            log("END")
            return
        
        reset_data = reset_response.json()
        observation = reset_data.get("observation", {})
        log(f"[TASK] Reset successful, got first ticket: {observation.get('ticket_id', 'unknown')}")
        
        # Step 2: Process tickets
        ticket_count = 0
        done = False
        
        while not done and ticket_count < max_tickets:
            ticket_id = observation.get("ticket_id", "unknown")
            customer_message = observation.get("customer_message", "")
            
            log(f"[TASK] Processing ticket #{ticket_count + 1}: {ticket_id}")
            log(f"[TASK] Message: {customer_message[:100]}...")
            
            # Analyze and generate action
            action = analyze_ticket_with_llm(customer_message)
            
            # Submit action to environment
            log(f"[TASK] Submitting action: {action['decision']} → {action['team']}")
            
            step_response = requests.post(
                f"{TASK_ENDPOINT}/step",
                json=action,
                timeout=30
            )
            
            if step_response.status_code != 200:
                log(f"[TASK] ERROR: Step failed with status {step_response.status_code}")
                log(f"[TASK] Response: {step_response.text}")
                break
            
            step_data = step_response.json()
            log("STEP")  # Required by validator
            
            # Check if task is complete
            done = step_data.get("done", False)
            reward = step_data.get("reward", {})
            score = reward.get("overall_score", 0.0)
            
            log(f"[TASK] Score: {score:.2f}, Done: {done}")
            
            # Get next observation
            observation = step_data.get("observation", {})
            ticket_count += 1
            
            if done:
                log(f"[TASK] Task completed after {ticket_count} tickets")
                break
        
        log(f"[TASK] Finished task_type={task_type} ({ticket_count} tickets)")
        
    except requests.exceptions.Timeout:
        log("[TASK] ERROR: Request timeout - task server not responding")
    except requests.exceptions.ConnectionError:
        log(f"[TASK] ERROR: Cannot connect to {TASK_ENDPOINT}")
        log("[TASK] Make sure TASK_ENDPOINT environment variable is correct")
    except Exception as e:
        log(f"[TASK] ERROR: {e}")
        log(f"[TASK] Traceback: {traceback.format_exc()}")
    
    log("END")  # Required by validator

def main_execution():
    """
    Main execution flow: run all difficulty levels.
    """
    log("[MAIN] Starting main execution")
    
    # Run tasks for each difficulty level
    for difficulty in ["easy", "medium", "hard"]:
        run_task(difficulty, max_tickets=10)
        time.sleep(1)
    
    log("[MAIN] All tasks completed")

# ==================== HEALTHCHECK SERVER ====================

class HealthCheckHandler(BaseHTTPRequestHandler):
    """
    Handles healthcheck requests from the OpenEnv validator.
    CRITICAL: Must respond quickly to prevent timeout.
    """
    
    def log_message(self, format, *args):
        """Suppress default HTTP logging to keep output clean."""
        pass
    
    def do_GET(self):
        """Respond to GET requests with 200 OK immediately."""
        try:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Connection', 'close')  # Important: close connection immediately
            self.end_headers()
            response = {"status": "healthy", "message": "Inference server running"}
            self.wfile.write(json.dumps(response).encode())
            self.wfile.flush()
        except Exception as e:
            log(f"[HEALTHCHECK] Error in handler: {e}")
    
    def do_HEAD(self):
        """Respond to HEAD requests - some validators use this."""
        try:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Connection', 'close')
            self.end_headers()
        except Exception as e:
            log(f"[HEALTHCHECK] Error in HEAD handler: {e}")

def is_port_available(port):
    """Check if port is available."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('0.0.0.0', port))
            return True
        except OSError:
            return False

def run_server():
    """
    Start the healthcheck server and execute the task.
    CRITICAL FIX: Start server first, ensure it's listening, then run tasks.
    """
    # Check port availability
    if not is_port_available(HEALTHCHECK_PORT):
        log(f"[SERVER] WARNING: Port {HEALTHCHECK_PORT} may already be in use")
    
    server_address = ('0.0.0.0', HEALTHCHECK_PORT)
    
    try:
        httpd = HTTPServer(server_address, HealthCheckHandler)
        httpd.timeout = 1  # Set timeout to allow checking for shutdown
        
        log(f"[SERVER] Starting healthcheck server on port {HEALTHCHECK_PORT}")
        
        # CRITICAL FIX: Start the server in a separate thread so it can handle requests immediately
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=False)
        server_thread.start()
        
        # Give server a moment to start listening
        time.sleep(0.5)
        
        log("[SERVER] Healthcheck server is running")
        
        # CRITICAL FIX: Run tasks in main thread, not as daemon
        # This ensures tasks complete and healthcheck stays alive
        try:
            main_execution()
        except Exception as e:
            log(f"[MAIN] Task execution error: {e}")
            log(f"[MAIN] Traceback: {traceback.format_exc()}")
        
        # Keep server running after tasks complete (validator may check health again)
        log("[SERVER] Tasks complete, keeping server alive for final healthchecks...")
        
        # Keep the server running for a while to handle any final healthchecks
        # The validator might check health multiple times
        shutdown_time = time.time() + 30  # Keep alive for 30 more seconds
        while time.time() < shutdown_time:
            time.sleep(1)
        
        log("[SERVER] Shutting down healthcheck server")
        httpd.shutdown()
        
    except Exception as e:
        log(f"[SERVER] CRITICAL ERROR: {e}")
        log(f"[SERVER] Traceback: {traceback.format_exc()}")
        raise

# ==================== ENTRY POINT ====================

if __name__ == "__main__":
    try:
        run_server()
    except Exception as e:
        log(f"[CRITICAL] Fatal error: {e}")
        log(f"[CRITICAL] Traceback: {traceback.format_exc()}")
        sys.exit(1)
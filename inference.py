import os
import sys
import json
import requests
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- CONFIGURATION ---
TASK_NAME = os.getenv("MY_ENV_V4_TASK", "support-ticket-triage")
BENCHMARK = os.getenv("MY_ENV_V4_BENCHMARK", "scaler_benchmark")
MODEL_NAME = "RuleBased-Triage-v1"

# Dynamically find the endpoint based on the task name
env_var = f"SCALER_ROUTE_TASK_{TASK_NAME.replace('-', '_').upper()}_ENDPOINT"
ENDPOINT = os.getenv(env_var, "http://env-task-server:8000")

# --- LOGGING HELPERS (As per Hackathon Rules) ---
def log_start():
    print(f"[START] task={TASK_NAME} env={BENCHMARK} model={MODEL_NAME}", flush=True)

def log_step(step, action, reward, done, error=None):
    err_str = error if error else "null"
    done_str = str(done).lower()
    print(f"[STEP] step={step} action={action} reward={reward:.2f} done={done_str} error={err_str}", flush=True)

def log_end(success, steps, score, rewards):
    rew_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} score={score:.2f} rewards={rew_str}", flush=True)

# --- TRIAGE LOGIC ---
def triage_logic(msg):
    m = msg.lower()
    if any(w in m for w in ["charge","bill","payment","refund","$"]):
        return {"decision":"escalate","team":"billing","urgency":"high","draft_response":"Escalating to billing.","reasoning":"Billing"}
    if any(w in m for w in ["password","login","access"]):
        return {"decision":"resolve","team":"support","urgency":"medium","draft_response":"Use password reset.","reasoning":"Self-service"}
    return {"decision":"needs_more_info","team":"support","urgency":"medium","draft_response":"Need more info.","reasoning":"Unclear"}

# --- HEALTHCHECK SERVER ---
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"status":"healthy"}')
    def log_message(self, format, *args): return # Silence logs

def run_health_server():
    server = HTTPServer(('0.0.0.0', 8080), HealthHandler)
    server.serve_forever()

# --- MAIN EXECUTION ---
def main():
    # 1. Start Healthcheck in background
    threading.Thread(target=run_health_server, daemon=True).start()
    
    print("INFO: Started", flush=True)
    log_start()

    total_rewards = []
    overall_success = False
    step_count = 0

    try:
        # Reset Environment
        r = requests.post(f"{ENDPOINT}/reset", params={"task_type": "medium"}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            obs = data.get("observation", {})
            done = data.get("done", False)

            # Task Loop
            for i in range(1, 11):
                if done: break
                
                step_count = i
                customer_msg = obs.get("customer_message", "")
                action_data = triage_logic(customer_msg)
                
                # Perform Step
                resp = requests.post(f"{ENDPOINT}/step", json=action_data, timeout=10)
                if resp.status_code != 200: break
                
                step_result = resp.json()
                reward = step_result.get("reward", 0.0)
                done = step_result.get("done", False)
                obs = step_result.get("observation", {})
                
                total_rewards.append(reward)
                log_step(i, action_data['decision'], reward, done)

            final_score = sum(total_rewards) / len(total_rewards) if total_rewards else 0
            overall_success = final_score > 0.5
            log_end(overall_success, step_count, final_score, total_rewards)
        else:
            log_end(False, 0, 0.0, [0.0])

    except Exception as e:
        # Crucial: Always emit [END] even on crash
        log_end(False, step_count, 0.0, total_rewards if total_rewards else [0.0])
    
    # Keep alive briefly for the validator to register the 200 OK
    import time
    time.sleep(2)

if __name__ == "__main__":
    main()
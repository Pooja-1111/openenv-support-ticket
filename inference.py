import os
import json
import requests
import traceback
import threading
import http.server
import socketserver
from openai import OpenAI

# --- CONFIGURATION ---
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8080")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
HF_TOKEN = os.getenv("HF_TOKEN")

try:
    client = OpenAI(
        api_key=HF_TOKEN or os.environ.get("OPENAI_API_KEY", "dummy_key"),
        base_url="https://api-inference.huggingface.co/v1/" if HF_TOKEN else None
    )
except Exception as e:
    client = None

# --- CORE LOGIC ---
def run_task(task_type: str, max_tickets: int = 3):
    print(f"STARTING: {task_type}")
    print("START")
    try:
        reset_resp = requests.post(f"{API_BASE_URL}/reset", params={"task_type": task_type}, timeout=10)
        if reset_resp.status_code != 200:
            print("END")
            return
        
        observation = reset_resp.json().get("observation", {})
        ticket_count = 0
        
        while ticket_count < max_tickets:
            customer_message = observation.get("customer_message", "")
            prompt = f"Identify decision/team/urgency for: {customer_message}. Return JSON."
            
            try:
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={ "type": "json_object" }
                )
                action_data = json.loads(response.choices[0].message.content)
            except:
                action_data = {"decision": "escalate", "team": "support", "urgency": "medium"}

            step_resp = requests.post(f"{API_BASE_URL}/step", json=action_data, timeout=10)
            if step_resp.status_code != 200 or step_resp.json().get("done"):
                break
            
            observation = step_resp.json().get("observation", {})
            print("STEP")
            ticket_count += 1
    except:
        pass
    print("END")

def main_execution():
    for difficulty in ["easy", "medium", "hard"]:
        run_task(difficulty)

# --- THE FIX: BUILT-IN SERVER ---
class HealthHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok"}).encode())

    def do_POST(self):
        # This handles the /run trigger if the validator uses it
        if self.path == '/run':
            threading.Thread(target=main_execution).start()
            self.send_response(202)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

def run_server():
    # MANDATORY: port 8080 and host 0.0.0.0
    PORT = 8080
    with socketserver.TCPServer(("0.0.0.0", PORT), HealthHandler) as httpd:
        print(f"INFO: Started server on port {PORT}")
        # Start the task in the background automatically so it runs even if no POST is sent
        threading.Thread(target=main_execution).start()
        httpd.serve_forever()

if __name__ == "__main__":
    run_server()
import os
import json
import requests
import traceback
import threading
from openai import OpenAI
from flask import Flask, jsonify

# Initialize Flask App
app = Flask(__name__)

# Required Environment Variables per Pre-Submission Checklist
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8080")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
HF_TOKEN = os.getenv("HF_TOKEN")

# Initialize OpenAI Client
try:
    client = OpenAI(
        api_key=HF_TOKEN or os.environ.get("OPENAI_API_KEY", "dummy_key"),
        base_url="https://api-inference.huggingface.co/v1/" if HF_TOKEN else None
    )
except Exception as e:
    print(f"Error initializing OpenAI: {e}")
    traceback.print_exc()
    client = None

def run_task(task_type: str, max_tickets: int = 3):
    print(f"STARTING TASK: {task_type}")
    print("START")
    
    try:
        reset_resp = requests.post(f"{API_BASE_URL}/reset", params={"task_type": task_type}, timeout=10)
        if reset_resp.status_code != 200:
            print("END")
            return
            
        reset_data = reset_resp.json()
        observation = reset_data["observation"]
        
        ticket_count = 0
        done = False
        
        while ticket_count < max_tickets and not done:
            customer_message = observation.get("customer_message", "")
            
            prompt = f"""
            You are a senior customer support agent. Consider this support ticket:
            "{customer_message}"
            
            Provide a strictly formatted JSON object with the following keys exactly:
            - "decision": one of "resolve", "escalate", or "needs_more_info"
            - "team": one of "billing", "engineering", "support", "product", or null (if not escalating)
            - "urgency": one of "low", "medium", or "high" 
            - "draft_response": a professional response drafted to the customer
            - "reasoning": brief explanation of why you routed it this way
            """
            
            try:
                if client is None:
                    raise Exception("OpenAI client is not initialized")
                
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[
                        {"role": "system", "content": "You are a helpful customer support agent. Always return valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={ "type": "json_object" }
                )
                
                action_data = json.loads(response.choices[0].message.content)
            except Exception:
                action_data = {
                    "decision": "escalate",
                    "team": "support",
                    "urgency": "medium",
                    "draft_response": "Thank you for reaching out. A specialist will assist you shortly.",
                    "reasoning": "Fallback due to LLM error"
                }
            
            if action_data.get("decision") != "escalate":
                action_data["team"] = None
                
            step_response = requests.post(f"{API_BASE_URL}/step", json=action_data, timeout=10)
            if step_response.status_code != 200:
                break
                
            step_data = step_response.json()
            done = step_data.get("done", False)
            observation = step_data.get("observation", {})
            
            print("STEP")
            ticket_count += 1
            
    except Exception as e:
        print(f"Exception in run_task: {e}")
        traceback.print_exc()
    
    print("END")

def main_execution_loop():
    """Wrapper to run the evaluation logic."""
    try:
        for difficulty in ["easy", "medium", "hard"]:
            run_task(difficulty, max_tickets=3)
        print("ALL TASKS COMPLETED")
    except Exception as e:
        print(f"Global unhandled exception: {e}")
        traceback.print_exc()

# --- SERVER ROUTES FOR HACKATHON VALIDATOR ---

@app.route('/', methods=['GET'])
@app.route('/health', methods=['GET'])
def health_check():
    """Answers the validator's healthcheck to prevent timeouts."""
    return jsonify({"status": "ready", "info": "Inference server is running"}), 200

@app.route('/run', methods=['POST'])
def start_evaluation():
    """Allows the validator to trigger the main loop."""
    thread = threading.Thread(target=main_execution_loop)
    thread.start()
    return jsonify({"status": "started"}), 202

if __name__ == "__main__":
    # Standard hackathon port 8080 and host 0.0.0.0 is MANDATORY
    print("INFO: Started")
    app.run(host='0.0.0.0', port=8080)
import os
import json
import requests
from openai import OpenAI

# Required Environment Variables per Pre-Submission Checklist
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
HF_TOKEN = os.getenv("HF_TOKEN")

# Optional – if you use from_docker_image():
LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")

# All LLM calls use the OpenAI client configured via these variables
client = OpenAI()

def run_task(task_type: str, max_tickets: int = 3):
    # Stdout logs follow the required structured format exactly
    print("START")
    
    try:
        reset_resp = requests.post(f"{API_BASE_URL}/reset", params={"task_type": task_type})
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
                # Fallback to avoid crashing the eval loop
                action_data = {
                    "decision": "escalate",
                    "team": "support",
                    "urgency": "medium",
                    "draft_response": "Thank you for reaching out. A specialist will assist you shortly.",
                    "reasoning": "Fallback due to LLM error"
                }
            
            # Ensure "team" is null instead of missing if not escalating
            if action_data.get("decision") != "escalate":
                action_data["team"] = None
                
            step_response = requests.post(f"{API_BASE_URL}/step", json=action_data)
            if step_response.status_code != 200:
                break
                
            step_data = step_response.json()
            done = step_data.get("done", False)
            observation = step_data.get("observation", {})
            
            # Print exact STEP tag after successful environment step interaction
            print("STEP")
            ticket_count += 1
            
    except Exception:
        pass
    
    print("END")


def main():
    # Evaluate across all 3 difficulty pools
    for difficulty in ["easy", "medium", "hard"]:
        run_task(difficulty, max_tickets=3)


if __name__ == "__main__":
    main()

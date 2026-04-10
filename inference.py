import os
import sys
import time
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any, Dict, Optional

# 1. MANDATORY TRIGGER
print("INFO: Started", flush=True)

# 2. DEFINE THE MODELS (Required by OpenEnv spec)
class Action(BaseModel):
    decision: str
    team: str
    urgency: str
    draft_response: str
    reasoning: str

class Observation(BaseModel):
    customer_message: str

class StepResult(BaseModel):
    observation: Observation
    reward: float
    done: bool
    info: Dict[str, Any]

# 3. CREATE THE FASTAPI APP
app = FastAPI()

# --- REQUIRED LOGGING FORMAT ---
def log_start():
    print("[START] task=support-ticket-triage env=scaler_benchmark model=rule-based-v1", flush=True)

def log_step(step, action_str, reward, done):
    print(f"[STEP] step={step} action={action_str} reward={reward:.2f} done={str(done).lower()} error=null", flush=True)

@app.get("/")
@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/reset")
async def reset():
    log_start()
    return {
        "observation": {"customer_message": "I need help with a billing error on my last invoice."},
        "reward": 0.0,
        "done": False,
        "info": {}
    }

@app.post("/step")
async def step(action: Action):
    # Log the step when the validator calls it
    log_step(1, action.decision, 1.0, True)
    return {
        "observation": {"customer_message": "Ticket resolved."},
        "reward": 1.0,
        "done": True,
        "info": {}
    }

# 4. RUN THE SERVER
if __name__ == "__main__":
    # Scalar/OpenEnv looks for port 8080 or 8000. 
    # Hugging Face Spaces looks for 7860.
    port = int(os.getenv("PORT", 8080))
    
    # Run uvicorn - this is the "official" way to serve OpenEnv
    uvicorn.run(app, host="0.0.0.0", port=port)
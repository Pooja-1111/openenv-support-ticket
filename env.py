from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import json
import random
import os
from typing import Optional, List, Literal
from models import Observation, Action, Reward, TicketGroundTruth, LoginRequest, Profile
import uvicorn
import google.generativeai as genai
from dotenv import load_dotenv
from supabase import create_client, Client
from models import Observation, Action, Reward, TicketGroundTruth, LoginRequest, Profile

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

# Initialize Supabase
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

app = FastAPI(title="Support Ticket Triage Environment", version="1.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store current task state
class EnvironmentState:
    def __init__(self):
        self.current_ticket: Optional[dict] = None
        self.current_task: Optional[str] = None  # "easy", "medium", "hard"
        self.current_ground_truth: Optional[TicketGroundTruth] = None
        self.current_profile: Optional[dict] = None
        self.ticket_index: int = 0
        self.easy_tickets: List[dict] = []
        self.medium_tickets: List[dict] = []
        self.hard_tickets: List[dict] = []
        self.custom_tickets: List[dict] = []
        self.load_all_tickets()
    
    def load_all_tickets(self):
        """Load all test data"""
        try:
            with open("test_data/easy_tickets.json") as f:
                self.easy_tickets = json.load(f)
        except:
            self.easy_tickets = []
        
        try:
            with open("test_data/medium_tickets.json") as f:
                self.medium_tickets = json.load(f)
        except:
            self.medium_tickets = []
        
        try:
            with open("test_data/hard_tickets.json") as f:
                self.hard_tickets = json.load(f)
        except:
            self.hard_tickets = []

env_state = EnvironmentState()


@app.get("/")
def root():
    """Health check"""
    return {"status": "ok", "service": "Support Ticket Triage Environment"}


@app.post("/login")
async def login(request: LoginRequest):
    """Upsert a player profile and return the current state"""
    try:
        # Check if player exists
        res = supabase.table("profiles").select("*").eq("player_name", request.player_name).execute()
        
        if res.data:
            # Login existing
            profile = res.data[0]
            # Update avatar if provided
            if request.avatar_url:
                supabase.table("profiles").update({"avatar_url": request.avatar_url}).eq("id", profile["id"]).execute()
                profile["avatar_url"] = request.avatar_url
        else:
            # Create new
            new_profile = {
                "player_name": request.player_name,
                "avatar_url": request.avatar_url or "default_avatar.png",
                "coins": 0,
                "score": 0,
                "hearts": 3,
                "world": 1,
                "xp": 0,
                "level": 1
            }
            res = supabase.table("profiles").insert(new_profile).execute()
            profile = res.data[0]
        
        env_state.current_profile = profile
        return profile
    except Exception as e:
        print(f"Supabase Login Error: {e}")
        raise HTTPException(status_code=500, detail="Database failure")


@app.get("/leaderboard")
async def get_leaderboard():
    """Get the top 10 players by score"""
    try:
        res = supabase.table("profiles").select("player_name, score, coins, world").order("score", desc=True).limit(10).execute()
        return res.data
    except Exception as e:
        print(f"Supabase Leaderboard Error: {e}")
        return []


@app.post("/generate_quest")
async def generate_quest(topic: str = Query(...)):
    """Generate a custom 10-ticket quest using Gemini"""
    prompt = f"""
    You are the 'Quest Master' creating a support ticket mission.
    TOPIC: {topic}
    Generate a JSON list of 5 support tickets. 
    Each ticket MUST have: 'ticket_id', 'customer_message', 'context', and a 'ground_truth' object.
    The 'ground_truth' MUST have: 'expected_decision', 'expected_team', 'expected_urgency', and 'response_quality_hint'.
    
    Make the mission tell a cohesive story related to the topic.
    JSON FORMAT ONLY:
    [
      {{
        "ticket_id": "CUSTOM001",
        "customer_message": "...",
        "context": "...",
        "ground_truth": {{
            "expected_decision": "resolve",
            "expected_team": "none",
            "expected_urgency": "low",
            "response_quality_hint": "..."
        }}
      }},
      ...
    ]
    """
    try:
        response = model.generate_content(prompt)
        json_text = response.text.replace('```json', '').replace('```', '').strip()
        env_state.custom_tickets = json.loads(json_text)
        return {"status": "created", "count": len(env_state.custom_tickets)}
    except Exception as e:
        print(f"Quest Generation Error: {e}")
        raise HTTPException(status_code=500, detail="Gemini failed to craft the quest")


@app.get("/hint")
async def get_hint():
    """Get a hint for the current ticket (costs 50 coins in UI)"""
    if not env_state.current_ticket:
        raise HTTPException(status_code=400, detail="No active mission")
        
    if not env_state.current_profile or env_state.current_profile.get("coins", 0) < 50:
        raise HTTPException(status_code=400, detail="Not enough coins")

    prompt = f"""
    As the Quest Master, give a subtle 8-bit themed hint for this ticket.
    DO NOT give the answer. 
    CUSTOMER: {env_state.current_ticket['customer_message']}
    HINT STYLE: "Player, notice that... The mission requires..."
    """
    try:
        response = model.generate_content(prompt)
        
        # Deduct coins from state and db
        try:
            new_coins = env_state.current_profile["coins"] - 50
            supabase.table("profiles").update({"coins": new_coins}).eq("id", env_state.current_profile["id"]).execute()
            env_state.current_profile["coins"] = new_coins
        except Exception as e:
            print(f"Supabase hint deduction Error: {e}")
            
        return {"hint": response.text.strip()}
    except:
        return {"hint": "The bits are scrambled! No hint available."}


@app.post("/buy_powerup")
async def buy_powerup(powerup_id: str = Query(...)):
    """Purchase a powerup using coins"""
    if not env_state.current_profile:
        raise HTTPException(status_code=400, detail="Not logged in")
        
    p = env_state.current_profile
    cost = 100 if powerup_id == "heart_restore" else (150 if powerup_id == "double_xp" else 9999)
    
    if p.get("coins", 0) < cost:
        raise HTTPException(status_code=400, detail="Not enough coins")
        
    if powerup_id == "heart_restore":
        if p.get("hearts", 3) >= 3:
            raise HTTPException(status_code=400, detail="Hearts are already full!")
        new_hearts = min(3, p.get("hearts", 3) + 1)
        new_coins = p.get("coins", 0) - cost
        
        try:
            supabase.table("profiles").update({"hearts": new_hearts, "coins": new_coins}).eq("id", p["id"]).execute()
            env_state.current_profile["hearts"] = new_hearts
            env_state.current_profile["coins"] = new_coins
            return {"status": "success", "new_hearts": new_hearts, "new_coins": new_coins}
        except Exception as e:
            print(f"Supabase powerup Error: {e}")
            raise HTTPException(status_code=500, detail="Database error during purchase")
            
    elif powerup_id == "double_xp":
        new_coins = p.get("coins", 0) - cost
        try:
            supabase.table("profiles").update({"coins": new_coins}).eq("id", p["id"]).execute()
            env_state.current_profile["coins"] = new_coins
            return {"status": "success", "powerup": "double_xp_active", "new_coins": new_coins}
        except Exception as e:
            print(f"Supabase powerup Error: {e}")
            raise HTTPException(status_code=500, detail="Database error during purchase")
            
    raise HTTPException(status_code=400, detail="Invalid powerup")


@app.get("/stats")
async def get_stats():
    """Get triage performance stats for the current player"""
    if not env_state.current_profile:
        return {"avg_score": 0, "logs": [], "total_triage": 0}
        
    try:
        # Fetch last 10 logs
        pid = env_state.current_profile["id"]
        res = supabase.table("triage_logs").select("*").eq("player_id", pid).order("created_at", desc=True).limit(10).execute()
        logs = res.data
        
        avg_score = sum(log["score"] for log in logs) / len(logs) if logs else 0
        total_res = supabase.table("triage_logs").select("id", count="exact").eq("player_id", pid).execute()
        total_count = total_res.count if total_res.count is not None else 0
        
        return {
            "avg_score": round(avg_score, 2),
            "total_triage": total_count,
            "recent_logs": logs[::-1]  # Return in chronological order for the chart
        }
    except Exception as e:
        print(f"Stats Error: {e}")
        return {"avg_score": 0, "logs": [], "total_triage": 0}

@app.post("/reset")
def reset(task_type: str = "easy"):
    """
    Reset environment for a new task
    task_type: "easy", "medium", or "hard"
    """
    global env_state
    
    if task_type == "easy":
        tickets = env_state.easy_tickets
    elif task_type == "medium":
        tickets = env_state.medium_tickets
    elif task_type == "hard":
        tickets = env_state.hard_tickets
    elif task_type == "custom":
        tickets = env_state.custom_tickets
    else:
        raise HTTPException(status_code=400, detail="task_type must be 'easy', 'medium', 'hard', or 'custom'")
    
    if not tickets:
        raise HTTPException(status_code=500, detail=f"No {task_type} tickets loaded")
    
    # Start with first ticket (deterministic for reproducibility)
    env_state.current_task = task_type
    env_state.ticket_index = 0
    env_state.current_ground_truth = TicketGroundTruth(**tickets[0])
    env_state.current_ticket = tickets[0]
    
    observation = Observation(
        ticket_id=tickets[0]["ticket_id"],
        customer_message=tickets[0]["customer_message"],
        context=tickets[0].get("context"),
        is_followup=False
    )
    
    return {
        "observation": observation.model_dump(),
        "task": task_type
    }


async def evaluate_action_with_gemini(action: Action, ground_truth: TicketGroundTruth, ticket: dict) -> Reward:
    """Use Gemini to dynamically grade the agent's action"""
    prompt = f"""
    You are the 'Quest Master' of a retro 8-bit support ticket triage game. 
    Your job is to grade a 'Player' (Support Agent) on their decision.

    MISSION DETAILS:
    - Ticket ID: {ticket['ticket_id']}
    - Customer Message: {ticket['customer_message']}
    - Context: {ticket.get('context', 'None')}

    PLAYER'S ACTION:
    - Decision: {action.decision}
    - Assigned Team: {action.team}
    - Urgency Level: {action.urgency}
    - Draft Response: {action.draft_response}
    - Player's Reasoning: {action.reasoning}

    GROUND TRUTH (Target):
    - Expected Decision: {ground_truth.expected_decision}
    - Expected Team: {ground_truth.expected_team}
    - Expected Urgency: {ground_truth.expected_urgency}
    - Quality Hint: {ground_truth.response_quality_hint}

    GRADING CRITERIA:
    1. Decision Correct: 1.0 if decision matches ground truth, else 0.0.
    2. Team Correct: 1.0 if team matches, 0.5 if it's a reasonable alternative, else 0.0.
    3. Response Quality: 0.0 to 1.0 based on professionalism and hint.
    4. Feedback: Provide a short, 8-bit style 'Quest Master' critique (max 2 sentences). 
       Be encouraging but firm. Use words like 'Player', 'Quest', 'Mission'.

    RETURN JSON ONLY:
    {{
        "decision_correct": float,
        "team_correct": float,
        "response_quality": float,
        "overall_score": float,
        "live_feedback": "string"
    }}
    """
    try:
        response = model.generate_content(prompt)
        raw_text = response.text.strip()
        print(f"DEBUG: Gemini Raw Response: {raw_text}")
        
        # Strip potential markdown formatting
        json_text = raw_text.replace('```json', '').replace('```', '').strip()
        data = json.loads(json_text)
        
        # Ensure all fields exist with reasonable defaults
        graded_reward = Reward(
            decision_correct=data.get("decision_correct", 0.0),
            team_correct=data.get("team_correct", 0.0),
            response_quality=data.get("response_quality", 0.0),
            overall_score=data.get("overall_score", 0.0),
            live_feedback=data.get("live_feedback", "Quest Master is speechless.")
        )
        return graded_reward
    except Exception as e:
        print(f"GEMINI_ERROR: {str(e)}")
        # Enhanced fallback
        is_dec_correct = 1.0 if action.decision == ground_truth.expected_decision else 0.0
        return Reward(
            decision_correct=is_dec_correct,
            team_correct=1.0 if action.team == ground_truth.expected_team else 0.0,
            response_quality=0.5,
            overall_score=is_dec_correct * 0.8,
            live_feedback=f"Quest Master is temporarily away! Static Reward Applied. Error: {str(e)[:50]}..."
        )


@app.post("/step")
async def step(action: Action):
    """
    Process agent action and return reward + next observation
    """
    if not env_state.current_task or not env_state.current_ground_truth:
        raise HTTPException(status_code=400, detail="Must call /reset first")
    
    # Grade the action with Gemini AI
    reward = await evaluate_action_with_gemini(action, env_state.current_ground_truth, env_state.current_ticket)
    
    # Move to next ticket
    tickets_for_task = {
        "easy": env_state.easy_tickets,
        "medium": env_state.medium_tickets,
        "hard": env_state.hard_tickets,
        "custom": env_state.custom_tickets
    }[env_state.current_task]
    
    # RECORD AUDIT LOG & UPDATE PROFILE
    if env_state.current_profile:
        try:
            # 1. Log the action
            audit_log = {
                "player_id": env_state.current_profile["id"],
                "ticket_id": env_state.current_ticket["ticket_id"],
                "decision": action.decision,
                "reasoning": action.reasoning,
                "score": reward.overall_score,
                "feedback": reward.live_feedback
            }
            supabase.table("triage_logs").insert(audit_log).execute()

            # 2. Update Profile Stats
            # Coins: 100 base (perfect) + Speed Bonus (up to 50)
            # Perfect score = 0.7+
            is_perfect = reward.overall_score >= 0.7
            is_good = reward.overall_score >= 0.4
            
            # Speed Bonus: 50 if under 15s, 20 if under 30s
            speed_bonus = 0
            if is_perfect and action.time_taken:
                if action.time_taken < 15: speed_bonus = 50
                elif action.time_taken < 30: speed_bonus = 20

            coin_gain = (100 if is_perfect else (50 if is_good else 0)) + speed_bonus
            if "double_xp" in action.active_powerups:
                coin_gain *= 2
            
            xp_gain = 20 if is_perfect else (10 if is_good else 0)
            
            p = env_state.current_profile
            new_score = p.get("score", 0) + int(reward.overall_score * 100) + speed_bonus
            new_coins = p.get("coins", 0) + coin_gain
            new_xp = p.get("xp", 0) + xp_gain
            new_level = (new_xp // 100) + 1
            new_hearts = max(0, p.get("hearts", 3) - (1 if reward.overall_score < 0.4 else 0))
            
            # Sync back to Supabase
            supabase.table("profiles").update({
                "score": new_score,
                "coins": new_coins,
                "hearts": new_hearts,
                "xp": new_xp,
                "level": new_level
            }).eq("id", p["id"]).execute()

            # Sync local profile state
            env_state.current_profile.update({
                "score": new_score,
                "coins": new_coins,
                "hearts": new_hearts,
                "xp": new_xp,
                "level": new_level
            })

        except Exception as e:
            print(f"Supabase Triage Update Error: {e}")

    env_state.ticket_index += 1
    done = env_state.ticket_index >= len(tickets_for_task)
    
    next_observation = None
    if not done:
        next_ticket = tickets_for_task[env_state.ticket_index]
        env_state.current_ground_truth = TicketGroundTruth(**next_ticket)
        env_state.current_ticket = next_ticket
        next_observation = Observation(
            ticket_id=next_ticket["ticket_id"],
            customer_message=next_ticket["customer_message"],
            context=next_ticket.get("context"),
            is_followup=False
        )
    
    return {
        "reward": reward.model_dump(),
        "observation": next_observation.model_dump() if next_observation else None,
        "done": done,
        "info": {
            "ticket_id": env_state.current_ticket["ticket_id"],
            "task": env_state.current_task,
            "tickets_completed": env_state.ticket_index,
            "total_tickets": len(tickets_for_task)
        }
    }


@app.get("/state")
def state():
    """
    Get current environment state
    """
    return {
        "current_ticket": env_state.current_ticket,
        "current_task": env_state.current_task,
        "ticket_index": env_state.ticket_index,
        "ground_truth": env_state.current_ground_truth.model_dump() if env_state.current_ground_truth else None
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

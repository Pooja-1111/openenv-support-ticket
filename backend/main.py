from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uvicorn
from datetime import datetime

app = FastAPI(title="Support Ticket Triage API")

# CORS Configuration - CRITICAL for localhost development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8001",  # Your frontend server
        "http://127.0.0.1:8001",
        "http://localhost:3000",  # Backup port
        "*"  # Remove in production, use specific origins only
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== MODELS ====================

class LoginRequest(BaseModel):
    player_name: str
    avatar_url: str

class PlayerProfile(BaseModel):
    player_name: str
    avatar_url: str
    score: int = 0
    coins: int = 0
    hearts: int = 3
    world: int = 1
    xp: int = 0
    level: int = 1

class ActionPayload(BaseModel):
    decision: str  # "resolve", "escalate", "needs_more_info"
    team: str
    urgency: str
    draft_response: str
    reasoning: str
    time_taken: float = 0.0

class TicketObservation(BaseModel):
    ticket_id: str
    customer_message: str
    priority: str = "medium"
    category: str = "general"

class RewardDetail(BaseModel):
    overall_score: float
    live_feedback: str
    breakdown: Dict[str, float] = {}

class StepResponse(BaseModel):
    observation: TicketObservation
    reward: RewardDetail
    done: bool
    info: Dict[str, Any]

# ==================== IN-MEMORY STATE ====================
# Replace with actual database in production

game_sessions: Dict[str, Any] = {}
player_profiles: Dict[str, PlayerProfile] = {}
leaderboard_data: List[Dict[str, Any]] = []
mission_logs: List[Dict[str, Any]] = []

# Sample tickets for different difficulty levels
SAMPLE_TICKETS = {
    "easy": [
        {
            "ticket_id": "EASY001",
            "customer_message": "I was charged twice for my monthly subscription. My account shows $200 instead of $100. Can you help me get a refund?",
            "category": "billing",
            "priority": "high"
        },
        {
            "ticket_id": "EASY002",
            "customer_message": "How do I reset my password? I can't log into my account and I forgot my security questions.",
            "category": "account",
            "priority": "medium"
        },
        {
            "ticket_id": "EASY003",
            "customer_message": "My download is stuck at 50%. It's been 2 hours and nothing is happening. What should I do?",
            "category": "technical",
            "priority": "medium"
        },
        {
            "ticket_id": "EASY004",
            "customer_message": "I need to update my billing address before my next payment. Where do I do this in the account settings?",
            "category": "account",
            "priority": "low"
        },
        {
            "ticket_id": "EASY005",
            "customer_message": "The mobile app keeps logging me out every 5 minutes. I have to re-enter my password constantly. Please help!",
            "category": "technical",
            "priority": "medium"
        }
    ],
    "medium": [
        {
            "ticket_id": "MED001",
            "customer_message": "After the latest update, the export feature crashes when I try to export more than 100 records. This is blocking our quarterly report that's due tomorrow.",
            "category": "bug",
            "priority": "high"
        },
        {
            "ticket_id": "MED002",
            "customer_message": "Can you integrate with Salesforce? We need bidirectional sync for our CRM workflow. Our team of 50 people would use this daily.",
            "category": "feature_request",
            "priority": "low"
        },
        {
            "ticket_id": "MED003",
            "customer_message": "I got an error message 'Database connection timeout' when trying to access my dashboard. My whole team is seeing this. Is there an outage?",
            "category": "technical",
            "priority": "critical"
        },
        {
            "ticket_id": "MED004",
            "customer_message": "We're being charged for 100 seats but only using 75. Can we downgrade our plan mid-cycle and get a prorated refund?",
            "category": "billing",
            "priority": "medium"
        }
    ],
    "hard": [
        {
            "ticket_id": "HARD001",
            "customer_message": "Our API rate limit was exceeded during Black Friday sales causing $50K in lost revenue. We need immediate escalation, compensation discussion, and a permanent increase to our rate limits.",
            "category": "critical_incident",
            "priority": "critical"
        },
        {
            "ticket_id": "HARD002",
            "customer_message": "We discovered a security vulnerability where user emails are visible in the page source. This affects all 10,000 of our customers. We need immediate remediation before we're forced to disclose publicly.",
            "category": "critical_incident",
            "priority": "critical"
        },
        {
            "ticket_id": "HARD003",
            "customer_message": "Data sync between our production and analytics databases has been failing for 3 days. Our entire C-suite dashboard is showing stale data from Monday. This is an emergency.",
            "category": "critical_incident",
            "priority": "critical"
        }
    ]
}

# ==================== ROUTES ====================

@app.get("/")
async def root():
    return {
        "message": "Support Ticket Triage API is running",
        "version": "1.0.0",
        "status": "healthy"
    }

@app.post("/login")
async def login(request: LoginRequest):
    """Login or create player profile"""
    try:
        player_name = request.player_name
        
        # Check if player exists
        if player_name in player_profiles:
            profile = player_profiles[player_name]
        else:
            # Create new profile
            profile = PlayerProfile(
                player_name=player_name,
                avatar_url=request.avatar_url
            )
            player_profiles[player_name] = profile
        
        return profile.dict()
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

@app.post("/reset")
async def reset_game(task_type: str = "easy"):
    """Reset game and return first ticket"""
    try:
        if task_type not in SAMPLE_TICKETS:
            raise HTTPException(status_code=400, detail=f"Invalid task_type: {task_type}")
        
        # Get tickets for this difficulty
        tickets = SAMPLE_TICKETS[task_type]
        if not tickets:
            raise HTTPException(status_code=404, detail="No tickets available")
        
        # Create session
        session_id = f"session_{datetime.now().timestamp()}"
        game_sessions[session_id] = {
            "task_type": task_type,
            "current_index": 0,
            "tickets_completed": 0,
            "total_tickets": 3,  # Max 3 tickets per level
            "ticket_order": list(range(len(tickets)))  # Track order
        }
        
        # Shuffle ticket order for variety
        import random
        random.shuffle(game_sessions[session_id]["ticket_order"])
        
        # Return first ticket
        first_ticket_index = game_sessions[session_id]["ticket_order"][0]
        first_ticket = tickets[first_ticket_index]
        
        return {
            "observation": first_ticket,
            "session_id": session_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reset failed: {str(e)}")

@app.post("/step")
async def process_step(action: ActionPayload, session_id: str = None):
    """Process a triage action and return next ticket"""
    try:
        # Get or create session (fallback for backward compatibility)
        if not session_id or session_id not in game_sessions:
            # Create default session
            session_id = f"session_{datetime.now().timestamp()}"
            game_sessions[session_id] = {
                "task_type": "easy",
                "current_index": 0,
                "tickets_completed": 0,
                "total_tickets": 3, # Max 3 tickets per level
                "ticket_order": list(range(len(SAMPLE_TICKETS["easy"])))
            }
            import random
            random.shuffle(game_sessions[session_id]["ticket_order"])
        
        session = game_sessions[session_id]
        task_type = session["task_type"]
        tickets = SAMPLE_TICKETS[task_type]
        
        # Get current ticket (the one they just triaged)
        current_ticket_index = session["ticket_order"][session["current_index"]]
        current_ticket = tickets[current_ticket_index]
        
        # Evaluate with intelligent scorer
        evaluation = evaluate_action_intelligent(current_ticket, action)
        
        # Update session progress
        session["tickets_completed"] += 1
        session["current_index"] = (session["current_index"] + 1) % len(tickets)
        
        # Get next ticket
        next_ticket_index = session["ticket_order"][session["current_index"]]
        next_ticket = tickets[next_ticket_index]
        
        # Check if game is done (completed all tickets)
        done = session["tickets_completed"] >= session["total_tickets"]
        
        # Build response
        response = StepResponse(
            observation=TicketObservation(**next_ticket),
            reward=RewardDetail(
                overall_score=evaluation["overall_score"],
                live_feedback=evaluation["live_feedback"],
                breakdown=evaluation["breakdown"]
            ),
            done=done,
            info={
                "tickets_completed": session["tickets_completed"],
                "total_tickets": session["total_tickets"],
                "time_taken": action.time_taken,
                "session_id": session_id
            }
        )
        
        # Log the mission
        mission_logs.append({
            "timestamp": datetime.now().isoformat(),
            "ticket_id": current_ticket["ticket_id"],
            "decision": action.decision,
            "score": evaluation["overall_score"],
            "time_taken": action.time_taken
        })
        
        return response.dict()
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Step failed: {str(e)}")

@app.get("/leaderboard")
async def get_leaderboard():
    """Get top players"""
    try:
        # Sort by score
        sorted_profiles = sorted(
            player_profiles.values(),
            key=lambda p: p.score,
            reverse=True
        )[:10]
        
        return [p.dict() for p in sorted_profiles]
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Leaderboard fetch failed: {str(e)}")

@app.get("/stats")
async def get_stats():
    """Get player statistics"""
    try:
        total_missions = len(mission_logs)
        avg_score = sum(log["score"] for log in mission_logs) / total_missions if total_missions > 0 else 0
        
        return {
            "total_triage": total_missions,
            "avg_score": avg_score,
            "recent_logs": mission_logs[-10:] if mission_logs else []
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats fetch failed: {str(e)}")

@app.get("/hint")
async def get_hint():
    """Get a hint for current ticket"""
    try:
        hints = [
            "Consider the urgency and impact on the customer.",
            "Billing issues should typically be escalated to the finance team.",
            "Technical bugs affecting multiple users need immediate escalation.",
            "Simple how-to questions can often be resolved with documentation links.",
            "Always explain your reasoning clearly to build trust."
        ]
        
        import random
        return {"hint": random.choice(hints)}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Hint generation failed: {str(e)}")

@app.post("/generate_quest")
async def generate_custom_quest(topic: str):
    """Generate custom ticket based on topic"""
    try:
        # Simplified - in production, use LLM to generate realistic tickets
        custom_ticket = {
            "ticket_id": f"CUSTOM_{datetime.now().timestamp()}",
            "customer_message": f"I need help with {topic}. Can you assist me with this issue?",
            "category": "custom",
            "priority": "medium"
        }
        
        return {"ticket": custom_ticket}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quest generation failed: {str(e)}")

# ==================== HELPER FUNCTIONS ====================

def evaluate_action_intelligent(ticket: Dict[str, Any], action: ActionPayload) -> Dict[str, Any]:
    """
    Intelligent triage evaluation with context-aware decision trees
    
    Args:
        ticket: Customer support ticket
        action: Player's triage decision
        
    Returns:
        dict with overall_score, live_feedback, breakdown
    """
    
    # Extract ticket context
    category = ticket.get("category", "general").lower()
    priority = ticket.get("priority", "medium").lower()
    message = ticket.get("customer_message", "").lower()
    
    # Extract action details
    decision = action.decision.lower()
    team = action.team.lower()
    urgency = action.urgency.lower()
    draft = action.draft_response
    reasoning = action.reasoning
    
    # Initialize scores
    decision_score = 0.0
    response_score = 0.0
    reasoning_score = 0.0
    feedback_parts = []
    
    # ==================== DECISION CORRECTNESS ====================
    
    # BILLING ISSUES - Should escalate to billing/finance
    if category == "billing" or any(word in message for word in ["charged", "payment", "refund", "invoice", "billing"]):
        if decision == "escalate":
            decision_score = 1.0
            feedback_parts.append("✅ Correct decision to escalate billing issue")
            
            if "billing" in team or "finance" in team:
                decision_score = 1.0
                feedback_parts.append("✅ Routed to correct team")
            elif team == "support":
                decision_score = 0.8
                feedback_parts.append("⚠️ Should route to billing team")
            else:
                decision_score = 0.6
                feedback_parts.append("❌ Wrong team for billing issue")
        elif decision == "resolve":
            decision_score = 0.3
            feedback_parts.append("❌ Billing issues should be escalated")
        else:
            decision_score = 0.5
            feedback_parts.append("⚠️ Clear billing issue - escalate don't ask for info")
    
    # ACCOUNT ACCESS / PASSWORD RESET
    elif category == "account" or any(word in message for word in ["password", "reset", "login", "can't log", "forgot"]):
        if decision == "resolve":
            decision_score = 1.0
            feedback_parts.append("✅ Correct - password resets can be self-served")
            
            if any(word in draft.lower() for word in ["reset", "link", "click", "follow", "steps"]):
                response_score = 1.0
                feedback_parts.append("✅ Provided clear instructions")
            else:
                response_score = 0.6
                feedback_parts.append("⚠️ Include password reset steps")
        elif decision == "escalate":
            decision_score = 0.4
            feedback_parts.append("❌ Password resets don't need escalation")
        else:
            decision_score = 0.6
            feedback_parts.append("⚠️ Send reset link, no need for more info")
    
    # TECHNICAL BUGS
    elif category in ["bug", "technical"] or any(word in message for word in ["crash", "error", "not working", "broken", "stuck"]):
        is_critical = any(word in message for word in ["all users", "everyone", "production", "blocking", "quarterly report"])
        
        if decision == "escalate":
            decision_score = 1.0
            feedback_parts.append("✅ Bugs need engineering team")
            
            if any(word in team for word in ["engineering", "technical", "dev"]):
                decision_score = 1.0
            else:
                decision_score = 0.7
                feedback_parts.append("⚠️ Route to engineering team")
            
            if is_critical and urgency != "critical":
                feedback_parts.append("⚠️ Should be CRITICAL urgency")
                decision_score = max(decision_score - 0.2, 0.5)
        elif decision == "resolve":
            decision_score = 0.3
            feedback_parts.append("❌ Bugs require engineering investigation")
        else:
            if is_critical:
                decision_score = 0.4
                feedback_parts.append("❌ Critical bug - escalate immediately")
            else:
                decision_score = 0.7
                feedback_parts.append("✓ Asking for repro steps is good")
    
    # FEATURE REQUESTS
    elif category == "feature_request" or any(word in message for word in ["can you add", "integrate", "new feature", "would be nice"]):
        if decision == "needs_more_info":
            decision_score = 0.9
            feedback_parts.append("✅ Gather requirements first")
        elif decision == "escalate":
            decision_score = 0.8 if any(word in team for word in ["product", "roadmap"]) else 0.5
            feedback_parts.append("✅ Route to product team" if decision_score > 0.6 else "⚠️ Should go to product team")
        else:
            decision_score = 0.4
            feedback_parts.append("❌ Can't resolve a feature request")
    
    # CRITICAL INCIDENTS
    elif category == "critical_incident" or priority == "critical" or any(word in message for word in ["revenue", "security breach", "data loss", "outage"]):
        if decision == "escalate" and urgency == "critical":
            decision_score = 1.0
            feedback_parts.append("✅ PERFECT - critical incident handled correctly")
        elif decision == "escalate":
            decision_score = 0.7
            feedback_parts.append("⚠️ Should be CRITICAL urgency")
        else:
            decision_score = 0.2
            feedback_parts.append("❌ CRITICAL - needs immediate escalation!")
    
    # DEFAULT
    else:
        if decision == "needs_more_info":
            decision_score = 0.7
            feedback_parts.append("✓ When unsure, ask for clarification")
        elif decision == "resolve":
            decision_score = 0.6
            feedback_parts.append("✓ Attempted resolution")
        else:
            decision_score = 0.7
            feedback_parts.append("✓ Escalation decision")
    
    # ==================== RESPONSE QUALITY ====================
    
    if len(draft) < 20:
        response_score = max(response_score, 0.3)
        feedback_parts.append("❌ Response too short")
    elif len(draft) < 50:
        response_score = max(response_score, 0.6)
        feedback_parts.append("⚠️ Response could be more detailed")
    else:
        response_score = max(response_score, 0.8)
    
    empathy_words = ["sorry", "apologize", "understand", "appreciate", "thank you"]
    if any(word in draft.lower() for word in empathy_words):
        response_score = min(response_score + 0.15, 1.0)
        if response_score < 0.9:
            feedback_parts.append("✅ Professional tone")
    else:
        feedback_parts.append("⚠️ Add empathy to response")
    
    # ==================== REASONING QUALITY ====================
    
    if len(reasoning) < 20:
        reasoning_score = 0.4
        feedback_parts.append("❌ Reasoning too brief")
    elif len(reasoning) < 50:
        reasoning_score = 0.7
        feedback_parts.append("⚠️ Reasoning could be clearer")
    else:
        reasoning_score = 0.9
    
    if any(word in reasoning.lower() for word in ["because", "since", "requires", "needs"]):
        reasoning_score = min(reasoning_score + 0.1, 1.0)
    
    # ==================== OVERALL SCORE ====================
    
    overall_score = (
        decision_score * 0.50 +
        response_score * 0.30 +
        reasoning_score * 0.20
    )
    
    # Generate verdict
    if overall_score >= 0.85:
        verdict = "🌟 EXCELLENT TRIAGE!"
    elif overall_score >= 0.70:
        verdict = "✅ GOOD WORK!"
    elif overall_score >= 0.50:
        verdict = "⚠️ NEEDS IMPROVEMENT"
    else:
        verdict = "❌ INCORRECT TRIAGE"
    
    live_feedback = f"{verdict} " + " | ".join(feedback_parts[:3])
    
    return {
        "overall_score": round(overall_score, 2),
        "live_feedback": live_feedback,
        "breakdown": {
            "decision_quality": round(decision_score, 2),
            "response_quality": round(response_score, 2),
            "reasoning_clarity": round(reasoning_score, 2)
        }
    }

# ==================== SERVER STARTUP ====================

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )

from pydantic import BaseModel
from typing import Optional, Literal, List


class Observation(BaseModel):
    """What the agent observes: the support ticket"""
    ticket_id: str
    customer_message: str
    context: Optional[str] = None  # Additional context like order history, account info
    is_followup: bool = False  # True if this is a multi-turn response


class Action(BaseModel):
    """What the agent decides to do"""
    decision: Literal["resolve", "escalate", "needs_more_info"]
    team: Optional[Literal["billing", "engineering", "support", "product", "none"]] = None
    urgency: Literal["low", "medium", "high"] = "medium"
    draft_response: str
    reasoning: Optional[str] = None
    time_taken: Optional[float] = 0.0  # Seconds spent on triage
    active_powerups: Optional[List[str]] = []  # E.g. ["double_xp"]

class Reward(BaseModel):
    """Numerical feedback on agent performance"""
    decision_correct: float  # 0.0 or 1.0
    team_correct: float  # 0.0, 0.5, or 1.0 (partial credit)
    response_quality: float  # 0.0–1.0 (professionalism, helpfulness)
    overall_score: float  # 0.0–1.0 (weighted average)
    live_feedback: Optional[str] = None  # AI-generated critique


class TicketGroundTruth(BaseModel):
    """Expected answer for grading"""
    ticket_id: str
    expected_decision: Literal["resolve", "escalate", "needs_more_info"]
    expected_team: Optional[Literal["billing", "engineering", "support", "product", "none"]] = None
    expected_urgency: Literal["low", "medium", "high"] = "medium"
    response_quality_hint: str  # What makes a good response?


class LoginRequest(BaseModel):
    """Request to identify a player"""
    player_name: str
    avatar_url: Optional[str] = None


class Profile(BaseModel):
    """The persistent player profile stored in Supabase"""
    id: str  # UUID
    player_name: str
    avatar_url: str
    coins: int
    score: int
    hearts: int
    world: int
    xp: int = 0
    level: int = 1

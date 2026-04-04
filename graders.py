from models import Action, Reward, TicketGroundTruth
from typing import List
import json


def is_professional_response(text: str) -> float:
    """Score response professionalism (0.0–1.0)"""
    score = 1.0
    
    # Check for basic professional markers
    professional_markers = [
        "sincerely", "apologize", "immediately", "assist", "help",
        "resolve", "thank you", "appreciate", "team", "escalat"
    ]
    
    # Check for unprofessional markers
    unprofessional_markers = [
        "don't know", "whatever", "lol", "ur", "idk", "sucks", "stupid"
    ]
    
    text_lower = text.lower()
    
    # Add points for professional language
    for marker in professional_markers:
        if marker in text_lower:
            score += 0.05
    
    # Deduct points for unprofessional language
    for marker in unprofessional_markers:
        if marker in text_lower:
            score -= 0.1
    
    # Check length (too short = not helpful)
    if len(text) < 30:
        score -= 0.2
    
    # Check if it acknowledges the problem
    if "understand" in text_lower or "see" in text_lower or "hear" in text_lower:
        score += 0.1
    
    return max(0.0, min(score, 1.0))


def grade_easy_ticket(action: Action, ground_truth: TicketGroundTruth) -> Reward:
    """
    Grade EASY task: Clear-cut categorization
    Example: "Charged twice" → escalate to billing
    """
    score = 0.0
    
    # Decision correctness (0.0 or 1.0)
    decision_correct = 1.0 if action.decision == ground_truth.expected_decision else 0.0
    score += decision_correct * 0.5
    
    # Team correctness (if applicable)
    team_correct = 0.0
    if action.decision == "escalate":
        team_correct = 1.0 if action.team == ground_truth.expected_team else 0.0
    score += team_correct * 0.3
    
    # Response quality
    response_quality = is_professional_response(action.draft_response)
    score += response_quality * 0.2
    
    overall_score = min(score, 1.0)
    
    return Reward(
        decision_correct=decision_correct,
        team_correct=team_correct,
        response_quality=response_quality,
        overall_score=overall_score
    )


def grade_medium_ticket(action: Action, ground_truth: TicketGroundTruth) -> Reward:
    """
    Grade MEDIUM task: Judgment calls, urgency assessment
    Example: "App is slow sometimes" → is it urgent? Which team?
    """
    score = 0.0
    
    # Decision correctness (weighted)
    if action.decision == ground_truth.expected_decision:
        decision_correct = 1.0
        score += 0.4
    elif (ground_truth.expected_decision == "escalate" and 
          action.decision in ["escalate", "needs_more_info"]):
        # Partial credit: if we should escalate and agent either escalates or asks more info
        decision_correct = 0.7
        score += 0.28
    else:
        decision_correct = 0.0
    
    # Team correctness (if escalating)
    team_correct = 0.0
    if action.decision == "escalate" and ground_truth.expected_team:
        if action.team == ground_truth.expected_team:
            team_correct = 1.0
        elif action.team and ground_truth.expected_team:
            # Partial credit if teams are related (e.g., both technical)
            related_teams = {
                "engineering": ["support", "product"],
                "billing": ["support"],
                "support": ["engineering", "billing"],
                "product": ["engineering"]
            }
            if action.team in related_teams.get(ground_truth.expected_team, []):
                team_correct = 0.5
        score += team_correct * 0.25
    
    # Urgency assessment
    urgency_correct = 1.0 if action.urgency == ground_truth.expected_urgency else 0.7
    score += urgency_correct * 0.15
    
    # Response quality
    response_quality = is_professional_response(action.draft_response)
    score += response_quality * 0.2
    
    overall_score = min(score, 1.0)
    
    return Reward(
        decision_correct=decision_correct,
        team_correct=team_correct,
        response_quality=response_quality,
        overall_score=overall_score
    )


def grade_hard_ticket(action: Action, ground_truth: TicketGroundTruth) -> Reward:
    """
    Grade HARD task: Multi-turn, requires reasoning about follow-ups
    Example: Agent asks "What error message?" and customer replies
    
    For simplicity in this version, we grade on decision + reasoning quality
    """
    score = 0.0
    
    # Decision correctness
    if action.decision == ground_truth.expected_decision:
        decision_correct = 1.0
    elif action.decision == "needs_more_info":
        # If unsure, asking more info is often reasonable
        decision_correct = 0.8
    else:
        decision_correct = 0.0
    score += decision_correct * 0.35
    
    # Team correctness (if escalating)
    team_correct = 0.0
    if action.decision == "escalate" and ground_truth.expected_team:
        if action.team == ground_truth.expected_team:
            team_correct = 1.0
        else:
            # Less strict on hard problems—multiple answers possible
            team_correct = 0.6
        score += team_correct * 0.25
    
    # Reasoning quality (explanation clarity)
    reasoning_quality = 0.5
    if action.reasoning:
        reasoning_text = action.reasoning.lower()
        # Good reasoning mentions specific details, context
        if any(word in reasoning_text for word in 
               ["because", "since", "given", "context", "suggest", "indicate"]):
            reasoning_quality = 1.0
        elif len(action.reasoning) > 50:
            reasoning_quality = 0.8
    score += reasoning_quality * 0.2
    
    # Response quality
    response_quality = is_professional_response(action.draft_response)
    score += response_quality * 0.2
    
    overall_score = min(score, 1.0)
    
    return Reward(
        decision_correct=decision_correct,
        team_correct=team_correct,
        response_quality=response_quality,
        overall_score=overall_score
    )


def load_ground_truth(task_type: str) -> List[TicketGroundTruth]:
    """Load ground truth answers for a task type"""
    try:
        with open(f"test_data/{task_type}_tickets.json", "r") as f:
            data = json.load(f)
            return [TicketGroundTruth(**item) for item in data]
    except FileNotFoundError:
        print(f"Warning: {task_type}_tickets.json not found")
        return []

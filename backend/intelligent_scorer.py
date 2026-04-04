"""
Intelligent Triage Scoring Engine
Evaluates support ticket triage decisions with context-aware logic
"""

def evaluate_action_intelligent(ticket: dict, action: dict) -> dict:
    """
    Smart evaluation of triage decisions based on ticket context
    
    Args:
        ticket: {ticket_id, customer_message, category, priority}
        action: {decision, team, urgency, draft_response, reasoning}
        
    Returns:
        {overall_score: float, live_feedback: str, breakdown: dict}
    """
    
    # Extract ticket context
    category = ticket.get("category", "general").lower()
    priority = ticket.get("priority", "medium").lower()
    message = ticket.get("customer_message", "").lower()
    
    # Extract action details
    decision = action.get("decision", "").lower()
    team = action.get("team", "").lower()
    urgency = action.get("urgency", "medium").lower()
    draft = action.get("draft_response", "")
    reasoning = action.get("reasoning", "")
    
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
            
            # Check team routing
            if "billing" in team or "finance" in team:
                decision_score = 1.0
                feedback_parts.append("✅ Routed to correct team (billing/finance)")
            elif team == "support":
                decision_score = 0.8
                feedback_parts.append("⚠️ Should route to billing team, not general support")
            else:
                decision_score = 0.6
                feedback_parts.append("❌ Wrong team - billing issues go to billing/finance")
                
            # Check urgency
            if urgency == "high" and priority == "high":
                decision_score = min(decision_score + 0.1, 1.0)
            elif urgency != priority:
                feedback_parts.append(f"⚠️ Urgency mismatch: ticket is {priority} but you set {urgency}")
        
        elif decision == "resolve":
            decision_score = 0.3
            feedback_parts.append("❌ Billing issues should be escalated, not resolved directly")
        
        else:  # needs_more_info
            decision_score = 0.5
            feedback_parts.append("⚠️ Customer provided clear billing issue - escalate, don't ask for more info")
    
    # ACCOUNT ACCESS / PASSWORD RESET - Should resolve with instructions
    elif category == "account" or any(word in message for word in ["password", "reset", "login", "can't log", "forgot"]):
        if decision == "resolve":
            decision_score = 1.0
            feedback_parts.append("✅ Correct - password resets can be self-served")
            
            # Check if they provided helpful instructions
            if any(word in draft.lower() for word in ["reset", "link", "click", "follow", "steps"]):
                response_score = 1.0
                feedback_parts.append("✅ Provided clear reset instructions")
            else:
                response_score = 0.6
                feedback_parts.append("⚠️ Response should include password reset steps/link")
        
        elif decision == "escalate":
            decision_score = 0.4
            feedback_parts.append("❌ Password resets don't need escalation - provide self-service instructions")
        
        else:  # needs_more_info
            decision_score = 0.6
            feedback_parts.append("⚠️ Clear password issue - no need for more info, just send reset link")
    
    # TECHNICAL BUGS - Should escalate to engineering
    elif category in ["bug", "technical"] or any(word in message for word in ["crash", "error", "not working", "broken", "stuck"]):
        
        # Check if it affects multiple users or is critical
        is_critical = any(word in message for word in ["all users", "everyone", "production", "blocking", "quarterly report"])
        
        if decision == "escalate":
            decision_score = 1.0
            feedback_parts.append("✅ Correct - technical bugs need engineering team")
            
            # Check team routing
            if any(word in team for word in ["engineering", "technical", "dev"]):
                decision_score = 1.0
            elif team == "support":
                decision_score = 0.7
                feedback_parts.append("⚠️ Route to engineering team, not general support")
            
            # Check urgency for critical bugs
            if is_critical and urgency != "critical":
                feedback_parts.append("⚠️ This bug is blocking work - should be CRITICAL urgency")
                decision_score = max(decision_score - 0.2, 0.5)
        
        elif decision == "resolve":
            decision_score = 0.3
            feedback_parts.append("❌ Bugs require engineering investigation, don't resolve without fix")
        
        else:  # needs_more_info
            if is_critical:
                decision_score = 0.4
                feedback_parts.append("❌ Critical bug - escalate immediately, don't delay asking for info")
            else:
                decision_score = 0.7
                feedback_parts.append("✓ Asking for reproduction steps is good, but consider escalating")
    
    # FEATURE REQUESTS - Should needs_more_info or route to product
    elif category == "feature_request" or any(word in message for word in ["can you add", "integrate", "new feature", "would be nice"]):
        if decision == "needs_more_info":
            decision_score = 0.9
            feedback_parts.append("✅ Good - gather requirements before routing to product")
        
        elif decision == "escalate":
            if any(word in team for word in ["product", "roadmap"]):
                decision_score = 0.8
                feedback_parts.append("✅ Escalated to product team")
            else:
                decision_score = 0.5
                feedback_parts.append("⚠️ Feature requests should go to product team")
        
        else:  # resolve
            decision_score = 0.4
            feedback_parts.append("❌ Can't 'resolve' a feature request - gather info or route to product")
    
    # CRITICAL INCIDENTS - Must escalate immediately
    elif category == "critical_incident" or priority == "critical" or any(word in message for word in ["revenue", "security breach", "data loss", "outage"]):
        if decision == "escalate" and urgency == "critical":
            decision_score = 1.0
            feedback_parts.append("✅ PERFECT - critical incident handled correctly")
        
        elif decision == "escalate" and urgency != "critical":
            decision_score = 0.7
            feedback_parts.append("⚠️ Correct to escalate, but this should be CRITICAL urgency")
        
        else:
            decision_score = 0.2
            feedback_parts.append("❌ CRITICAL - this needs immediate escalation!")
    
    # GENERAL / UNKNOWN - Flexible scoring
    else:
        # Default: reasonable decisions get medium scores
        if decision == "needs_more_info":
            decision_score = 0.7
            feedback_parts.append("✓ When unsure, asking for clarification is safe")
        elif decision == "resolve":
            decision_score = 0.6
            feedback_parts.append("✓ Attempted resolution")
        else:
            decision_score = 0.7
            feedback_parts.append("✓ Escalation decision")
    
    # ==================== RESPONSE QUALITY ====================
    
    # Check response length
    if len(draft) < 20:
        response_score = max(response_score, 0.3)
        feedback_parts.append("❌ Response too short - needs more detail")
    elif len(draft) < 50:
        response_score = max(response_score, 0.6)
        feedback_parts.append("⚠️ Response could be more detailed")
    else:
        response_score = max(response_score, 0.8)
    
    # Check for empathy/professionalism
    empathy_words = ["sorry", "apologize", "understand", "appreciate", "thank you"]
    if any(word in draft.lower() for word in empathy_words):
        response_score = min(response_score + 0.15, 1.0)
        if response_score < 0.9:
            feedback_parts.append("✅ Professional and empathetic tone")
    else:
        feedback_parts.append("⚠️ Consider adding empathy (e.g., 'I apologize for the inconvenience')")
    
    # ==================== REASONING QUALITY ====================
    
    if len(reasoning) < 20:
        reasoning_score = 0.4
        feedback_parts.append("❌ Reasoning too brief - explain your decision")
    elif len(reasoning) < 50:
        reasoning_score = 0.7
        feedback_parts.append("⚠️ Reasoning could be clearer")
    else:
        reasoning_score = 0.9
        feedback_parts.append("✅ Clear reasoning provided")
    
    # Check if reasoning mentions key factors
    if any(word in reasoning.lower() for word in ["because", "since", "requires", "needs"]):
        reasoning_score = min(reasoning_score + 0.1, 1.0)
    
    # ==================== CALCULATE OVERALL SCORE ====================
    
    # Weighted average (decision is most important)
    overall_score = (
        decision_score * 0.50 +  # 50% - correct decision
        response_score * 0.30 +  # 30% - quality response
        reasoning_score * 0.20   # 20% - clear reasoning
    )
    
    # ==================== GENERATE FEEDBACK ====================
    
    # Overall verdict
    if overall_score >= 0.85:
        verdict = "🌟 EXCELLENT TRIAGE!"
    elif overall_score >= 0.70:
        verdict = "✅ GOOD WORK!"
    elif overall_score >= 0.50:
        verdict = "⚠️ NEEDS IMPROVEMENT"
    else:
        verdict = "❌ INCORRECT TRIAGE"
    
    live_feedback = f"{verdict} " + " | ".join(feedback_parts[:3])  # Limit to 3 main points
    
    # ==================== RETURN RESULTS ====================
    
    return {
        "overall_score": round(overall_score, 2),
        "live_feedback": live_feedback,
        "breakdown": {
            "decision_quality": round(decision_score, 2),
            "response_quality": round(response_score, 2),
            "reasoning_clarity": round(reasoning_score, 2)
        }
    }


# ==================== TESTING ====================

if __name__ == "__main__":
    # Test case 1: Billing issue (should escalate)
    ticket1 = {
        "ticket_id": "EASY001",
        "customer_message": "I was charged twice for my monthly subscription. My account shows $200 instead of $100.",
        "category": "billing",
        "priority": "high"
    }
    
    action1_correct = {
        "decision": "escalate",
        "team": "billing",
        "urgency": "high",
        "draft_response": "I apologize for the inconvenience. I'm escalating this to our billing team to investigate the duplicate charge and process a refund immediately.",
        "reasoning": "Billing issue with duplicate charge requires finance team review and refund processing."
    }
    
    action1_wrong = {
        "decision": "resolve",
        "team": "support",
        "urgency": "medium",
        "draft_response": "Try refreshing your account page.",
        "reasoning": "Just a display issue."
    }
    
    print("=== TEST 1: Billing Issue (Correct) ===")
    result = evaluate_action_intelligent(ticket1, action1_correct)
    print(f"Score: {result['overall_score']}")
    print(f"Feedback: {result['live_feedback']}")
    print()
    
    print("=== TEST 1: Billing Issue (Wrong) ===")
    result = evaluate_action_intelligent(ticket1, action1_wrong)
    print(f"Score: {result['overall_score']}")
    print(f"Feedback: {result['live_feedback']}")
    print()
    
    # Test case 2: Password reset (should resolve)
    ticket2 = {
        "ticket_id": "EASY002",
        "customer_message": "How do I reset my password? I can't log into my account.",
        "category": "account",
        "priority": "medium"
    }
    
    action2_correct = {
        "decision": "resolve",
        "team": "none",
        "urgency": "medium",
        "draft_response": "I can help with that! Please visit our password reset page at example.com/reset and follow the instructions. You'll receive a reset link via email within minutes.",
        "reasoning": "Password reset is a self-service action that doesn't require escalation."
    }
    
    print("=== TEST 2: Password Reset (Correct) ===")
    result = evaluate_action_intelligent(ticket2, action2_correct)
    print(f"Score: {result['overall_score']}")
    print(f"Feedback: {result['live_feedback']}")
    print()

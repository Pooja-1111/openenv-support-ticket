# 🎮 Support Ticket Triage Simulator

An immersive, retro-RPG style simulator where users play as a customer support agent. Level up your career, earn coins, and protect your 8-bit hearts by successfully evaluating, categorizing, and responding to simulated support tickets!

## 🌟 Features

- **RPG Gamification:** Progression system featuring Career XP, Level-ups, and a 3-Heart survival mechanic.
- **Intelligent Triage Engine:** A sophisticated Python backend powered by LLMs evaluates the quality of your responses, decision logic, and tone—not just simple keywords.
- **Dynamic Difficulty Worlds:** 3 worlds (Easy, Medium, and Hard) that scale in complexity, with auto-progression upon completion limit rules.
- **Retro Aesthetic:** Custom pixel-art CSS, parallax animated backgrounds, and an embedded 8-bit Chiptune audio engine.
- **Profile Customization:** Choose your avatar and display name on the fly. 

## 🛠️ Tech Stack

- **Frontend:** Vanilla JS (ES6 modules), HTML5, Tailwind CSS, Material Symbols.
- **Backend:** Python 3, FastAPI, Uvicorn, Pydantic.
- **Storage:** LocalStorage (Frontend state), In-Memory Server dictionary (Backend sessions).

## 🚀 Getting Started

To run the full simulator locally, you need to spin up both the FastAPI backend and a local server for the frontend.

### 1. Start the Game Engine (Backend)
Navigate to the `backend` directory and start the Python server:
```bash
cd backend
# Install dependencies if you haven't (fastapi, uvicorn, pydantic, json, requests)
python3 main.py
```
*The backend will automatically bind to `localhost:8000`.*

### 2. Start the Client (Frontend)
Open a new terminal window, navigate to the `frontend` directory, and launch a local static server:
```bash
cd frontend
python3 -m http.server 8001
```

### 3. Play!
Open your browser and navigate to:
`http://localhost:8001/`

*(Note: Do not open index.html as a `file://` directly, as CORS or ES6 module imports will block the API requests.)*

## 📜 How to Play

1. **Select a World:** Start on `WORLD_1`.
2. **Review the Ticket:** Read what the angry/confused customer needs.
3. **Draft a Response:** Select an action (Resolve, Escalate, Need Info), type a professional response to the customer, and explain your reasoning.
4. **Submit:** The Quest Master (Backend Evaluator) will judge your response.
   - **Perfect:** ⭐ +100 Score, +50 XP
   - **Good:** ✓ +50 Score, +20 XP
   - **Miss:** 💔 Lose a heart!
5. Clear **3 tickets** perfectly to automatically progress to the next world! Have fun!

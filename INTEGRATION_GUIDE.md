# 🎮 Support Ticket Triage Dashboard - Setup Guide

## 🚀 Quick Start

### Backend Setup

1. **Navigate to backend directory:**
   ```bash
   cd backend
   ```

2. **Create virtual environment (recommended):**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Start the backend server:**
   ```bash
   python3 main.py
   ```

   You should see:
   ```
   INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
   ```

### Frontend Setup

1. **Navigate to frontend directory:**
   ```bash
   cd frontend
   ```

2. **Serve the frontend (choose one method):**

   **Option A - Python HTTP Server:**
   ```bash
   python3 -m http.server 8001
   ```

   **Option B - Node.js HTTP Server:**
   ```bash
   npx http-server -p 8001
   ```

   **Option C - VS Code Live Server:**
   - Install "Live Server" extension
   - Right-click `index.html` → "Open with Live Server"

3. **Open in browser:**
   ```
   http://127.0.0.1:8001/index.html
   ```

---

## 🔧 Integration Fix Summary

### What Was Causing the Disconnection

1. **CORS Not Configured**
   - **Problem:** Frontend on `localhost:8001` couldn't access backend on `localhost:8000` due to CORS policy
   - **Fix:** Added `CORSMiddleware` to FastAPI with proper origin configuration

2. **No Unified API Client**
   - **Problem:** Direct `fetch()` calls scattered throughout code with inconsistent error handling
   - **Fix:** Created `APIClient` class with timeout, retry logic, and centralized error handling

3. **Response Structure Mismatch**
   - **Problem:** Frontend expected fields that backend wasn't returning
   - **Fix:** Created Pydantic models (`StepResponse`, `RewardDetail`, etc.) ensuring type safety

4. **Missing Error Boundaries**
   - **Problem:** Failed requests crashed the UI without feedback
   - **Fix:** Added try-catch blocks with user-friendly error messages

5. **No Health Check**
   - **Problem:** No way to verify backend connectivity
   - **Fix:** Added `/` endpoint and connection verification in frontend

---

## 🐛 Troubleshooting

### Issue: "Cannot connect to server"

**Symptoms:**
- Frontend shows "Backend Connection Failed"
- Console error: `Failed to fetch`

**Solutions:**

1. **Verify backend is running:**
   ```bash
   curl http://127.0.0.1:8000/
   ```
   Should return: `{"message": "Support Ticket Triage API is running", ...}`

2. **Check port conflicts:**
   ```bash
   lsof -i :8000  # macOS/Linux
   netstat -ano | findstr :8000  # Windows
   ```

3. **Restart backend:**
   ```bash
   # Kill existing process
   pkill -f "python main.py"
   # Start fresh
   python main.py
   ```

### Issue: CORS Errors in Browser Console

**Symptoms:**
- Console shows: `Access to fetch at 'http://localhost:8000/...' from origin 'http://localhost:8001' has been blocked by CORS policy`

**Solutions:**

1. **Verify CORS middleware in `main.py`:**
   ```python
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["http://localhost:8001", "*"],
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```

2. **Check backend logs for CORS issues**

3. **Restart backend after CORS changes**

---

## 🔐 Production Considerations

### Security

1. **CORS - Lock Down Origins:**
   ```python
   # Remove "*" and specify exact domains
   allow_origins=[
       "https://yourdomain.com",
       "https://www.yourdomain.com"
   ]
   ```

---

## 🎯 What to Do Next

1. **Test the connection:**
   - Start backend: `python main.py`
   - Start frontend: `python3 -m http.server 8001`
   - Open browser: `http://localhost:8001`
   - Check console for "✅ Login successful"

🎉 **If all boxes are checked, your integration is working!**
   - Use `python3` if `python` command is not found.


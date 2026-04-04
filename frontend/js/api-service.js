// api-service.js - Unified API Client for Support Ticket Triage

// ==================== CONFIGURATION ====================

const CONFIG = {
    API_BASE: 'http://localhost:8000',
    TIMEOUT: 10000, // 10 seconds
    RETRY_ATTEMPTS: 2
};

// ==================== TYPE DEFINITIONS ====================

/**
 * @typedef {Object} PlayerProfile
 * @property {string} player_name
 * @property {string} avatar_url
 * @property {number} score
 * @property {number} coins
 * @property {number} hearts
 * @property {number} world
 * @property {number} xp
 * @property {number} level
 */

/**
 * @typedef {Object} TicketObservation
 * @property {string} ticket_id
 * @property {string} customer_message
 * @property {string} priority
 * @property {string} category
 */

/**
 * @typedef {Object} GameEngineUpdates
 * @property {number} xp_gain
 * @property {number} coin_gain
 * @property {number} heart_loss
 * @property {number} level_progress_pct
 */

/**
 * @typedef {Object} GameEngineResponse
 * @property {string} status
 * @property {string} feedback
 * @property {GameEngineUpdates} updates
 * @property {TicketObservation} observation
 */

// ==================== ERROR HANDLING ====================

class APIError extends Error {
    constructor(message, statusCode, originalError) {
        super(message);
        this.name = 'APIError';
        this.statusCode = statusCode;
        this.originalError = originalError;
    }
}

// ==================== CORE API CLIENT ====================

class SupportTicketAPI {
    constructor(baseURL = CONFIG.API_BASE) {
        this.baseURL = baseURL;
        this.timeout = CONFIG.TIMEOUT;
    }

    /**
     * Generic fetch wrapper with timeout and error handling
     */
    async _fetch(endpoint, options = {}) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.timeout);

        try {
            const response = await fetch(`${this.baseURL}${endpoint}`, {
                ...options,
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers,
                },
                signal: controller.signal,
            });

            clearTimeout(timeoutId);

            // Handle non-OK responses
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new APIError(
                    errorData.detail || `HTTP ${response.status}: ${response.statusText}`,
                    response.status,
                    errorData
                );
            }

            return await response.json();
        } catch (error) {
            clearTimeout(timeoutId);

            // Handle different error types
            if (error.name === 'AbortError') {
                throw new APIError('Request timeout - server not responding', 408, error);
            }
            if (error instanceof APIError) {
                throw error;
            }
            if (error.message.includes('Failed to fetch')) {
                throw new APIError(
                    'Cannot connect to server. Is the backend running on port 8000?',
                    0,
                    error
                );
            }

            throw new APIError('Unexpected error occurred', 500, error);
        }
    }

    /**
     * Retry wrapper for critical operations
     */
    async _fetchWithRetry(endpoint, options = {}, retries = CONFIG.RETRY_ATTEMPTS) {
        for (let attempt = 0; attempt <= retries; attempt++) {
            try {
                return await this._fetch(endpoint, options);
            } catch (error) {
                if (attempt === retries) throw error;
                
                // Exponential backoff
                await new Promise(resolve => setTimeout(resolve, Math.pow(2, attempt) * 1000));
                console.warn(`Retry attempt ${attempt + 1}/${retries} for ${endpoint}`);
            }
        }
    }

    // ==================== API METHODS ====================

    /**
     * Login or create player profile
     * @param {string} playerName 
     * @param {string} avatarUrl 
     * @returns {Promise<PlayerProfile>}
     */
    async login(playerName, avatarUrl) {
        return await this._fetchWithRetry('/login', {
            method: 'POST',
            body: JSON.stringify({
                player_name: playerName,
                avatar_url: avatarUrl,
            }),
        });
    }

    /**
     * Reset game and get first ticket
     * @param {string} taskType - "easy", "medium", "hard"
     * @returns {Promise<{observation: TicketObservation, session_id: string}>}
     */
    async resetGame(taskType = 'easy') {
        return await this._fetch(`/reset?task_type=${taskType}`, {
            method: 'POST',
        });
    }

    /**
     * Submit triage action and get results using Game Engine
     * @param {Object} action
     * @returns {Promise<GameEngineResponse>}
     */
    async submitAction(action) {
        return await this._fetch('/step', {
            method: 'POST',
            body: JSON.stringify(action),
        });
    }

    /**
     * Get leaderboard
     * @returns {Promise<PlayerProfile[]>}
     */
    async getLeaderboard() {
        return await this._fetch('/leaderboard');
    }

    /**
     * Get player statistics
     * @returns {Promise<{total_triage: number, avg_score: number, recent_logs: Object[]}>}
     */
    async getStats() {
        return await this._fetch('/stats');
    }

    /**
     * Get a hint for current ticket
     * @returns {Promise<{hint: string}>}
     */
    async getHint() {
        return await this._fetch('/hint');
    }

    /**
     * Generate custom quest
     * @param {string} topic 
     * @returns {Promise<{ticket: TicketObservation}>}
     */
    async generateCustomQuest(topic) {
        return await this._fetch(`/generate_quest?topic=${encodeURIComponent(topic)}`, {
            method: 'POST',
        });
    }

    /**
     * Health check
     * @returns {Promise<{status: string, message: string}>}
     */
    async healthCheck() {
        return await this._fetch('/');
    }
}

// ==================== SINGLETON INSTANCE ====================

const apiClient = new SupportTicketAPI();

// ==================== EXPORTS ====================

export { apiClient, APIError, SupportTicketAPI };
export default apiClient;

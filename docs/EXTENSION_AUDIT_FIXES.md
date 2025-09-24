# 🔧 PROMPTFORGEAI EXTENSION - IMMEDIATE FIXES

## 1. ENHANCED USAGE TRACKING

### Background Script Updates (src/background.js):

```javascript
// Enhanced tracking with all user interactions
async function trackUsageEvent(action, details = {}, creditsSpent = 0, source = 'extension') {
  try {
    const result = await apiFetch('/users/usage/track', {
      method: 'POST',
      body: JSON.stringify({
        source,
        action,
        details: {
          ...details,
          timestamp: Date.now(),
          extensionVersion: chrome.runtime.getManifest().version,
          userAgent: navigator.userAgent,
          sessionId: await getSessionId()
        },
        credits_spent: creditsSpent
      })
    });
    
    // Track tracking failures too
    if (!result.ok) {
      console.error('Tracking failed:', action, result.status);
    }
  } catch (error) {
    // Log tracking errors for debugging
    console.error('Tracking error:', action, error.message);
    // Store failed events for retry
    await storeFailedEvent({ action, details, creditsSpent, source, error: error.message });
  }
}

// NEW: Track all critical events
const TRACKING_EVENTS = {
  EXTENSION_INSTALLED: 'extension_installed',
  EXTENSION_UPDATED: 'extension_updated', 
  AUTH_STARTED: 'auth_started',
  AUTH_COMPLETED: 'auth_completed',
  AUTH_FAILED: 'auth_failed',
  PROMPT_UPGRADED: 'prompt_upgraded',
  UPGRADE_FAILED: 'upgrade_failed',
  BUTTON_SHOWN: 'button_shown',
  BUTTON_CLICKED: 'button_clicked',
  CONSENT_GRANTED: 'consent_granted',
  CONSENT_DENIED: 'consent_denied',
  REALTIME_ENABLED: 'realtime_enabled',
  WORKBENCH_OPENED: 'workbench_opened',
  OPTIONS_OPENED: 'options_opened',
  TOKEN_REFRESHED: 'token_refreshed',
  ERROR_OCCURRED: 'error_occurred'
};
```

## 2. FIX AUTHENTICATION ISSUES

### Centralized Auth Manager:

```javascript
// NEW: auth-manager.js
class AuthManager {
  constructor() {
    this.authState = {
      isAuthenticated: false,
      user: null,
      token: null,
      expiresAt: null,
      refreshToken: null
    };
    this.listeners = new Set();
  }

  async initialize() {
    const stored = await chrome.storage.local.get(['pfai_id_token', 'pfai_refresh_token', 'pfai_user_data']);
    if (stored.pfai_id_token) {
      this.authState.token = stored.pfai_id_token;
      this.authState.refreshToken = stored.pfai_refresh_token;
      this.authState.isAuthenticated = true;
      
      // Verify token validity
      await this.validateToken();
    }
  }

  async validateToken() {
    try {
      const response = await this.apiCall('/users/me');
      if (response.ok) {
        const userData = await response.json();
        this.authState.user = userData.data;
        this.notifyListeners();
        return true;
      } else if (response.status === 401) {
        await this.refreshTokenIfNeeded();
        return false;
      }
    } catch (error) {
      await trackUsageEvent(TRACKING_EVENTS.ERROR_OCCURRED, { context: 'token_validation', error: error.message });
      return false;
    }
  }

  async refreshTokenIfNeeded() {
    if (!this.authState.refreshToken) {
      await this.signOut();
      return false;
    }

    try {
      const newToken = await refreshFirebaseIdToken();
      if (newToken) {
        this.authState.token = newToken;
        await chrome.storage.local.set({ pfai_id_token: newToken });
        await trackUsageEvent(TRACKING_EVENTS.TOKEN_REFRESHED);
        return true;
      }
    } catch (error) {
      await trackUsageEvent(TRACKING_EVENTS.ERROR_OCCURRED, { context: 'token_refresh', error: error.message });
    }
    
    await this.signOut();
    return false;
  }

  onAuthStateChanged(callback) {
    this.listeners.add(callback);
    return () => this.listeners.delete(callback);
  }

  notifyListeners() {
    this.listeners.forEach(callback => callback(this.authState));
  }
}
```

## 3. ELIMINATE HARDCODED DATA

### Environment Configuration:

```javascript
// NEW: config.js
const CONFIG = {
  development: {
    API_BASE: 'http://localhost:8000/api/v1',
    FIREBASE_API_KEY: 'AIzaSyCofg2AAY_ksKGlfKEw3CwZMdfGClTC3cw',
    OAUTH_CLIENT_ID: '540830916745-kq9ckjctp8al4qvi0bvf8lav6lnri5bb.apps.googleusercontent.com'
  },
  production: {
    API_BASE: 'https://api.promptforge.ai/api/v1',
    FIREBASE_API_KEY: 'PRODUCTION_FIREBASE_KEY',
    OAUTH_CLIENT_ID: 'PRODUCTION_OAUTH_CLIENT_ID'
  }
};

// Environment detection
function getEnvironment() {
  return chrome.runtime.getManifest().version.includes('dev') ? 'development' : 'production';
}

function getConfig() {
  return CONFIG[getEnvironment()];
}
```

## 4. DASHBOARD DATA SYNC FIXES

### Options Page Sync Manager:

```javascript
// Enhanced options.js with real-time sync
class OptionsPageManager {
  constructor() {
    this.authManager = new AuthManager();
    this.syncInterval = null;
  }

  async initialize() {
    await this.authManager.initialize();
    
    // Listen for auth changes
    this.authManager.onAuthStateChanged((authState) => {
      this.updateUI(authState);
    });

    // Auto-sync every 30 seconds when authenticated
    this.startAutoSync();
    
    // Listen for storage changes from other extension parts
    chrome.storage.onChanged.addListener((changes) => {
      this.handleStorageChange(changes);
    });
  }

  async fetchLatestUserData() {
    if (!this.authManager.authState.isAuthenticated) return null;

    try {
      const [profileResponse, usageResponse] = await Promise.all([
        this.authManager.apiCall('/users/me'),
        this.authManager.apiCall('/users/usage/current')
      ]);

      if (profileResponse.ok && usageResponse.ok) {
        const profile = await profileResponse.json();
        const usage = await usageResponse.json();
        
        return {
          profile: profile.data,
          usage: usage.data
        };
      }
    } catch (error) {
      await trackUsageEvent(TRACKING_EVENTS.ERROR_OCCURRED, { 
        context: 'options_data_fetch', 
        error: error.message 
      });
    }
    return null;
  }

  startAutoSync() {
    this.syncInterval = setInterval(async () => {
      if (this.authManager.authState.isAuthenticated) {
        await this.fetchLatestUserData();
      }
    }, 30000); // 30 seconds
  }

  stopAutoSync() {
    if (this.syncInterval) {
      clearInterval(this.syncInterval);
      this.syncInterval = null;
    }
  }
}
```

## 5. ERROR HANDLING & RETRY LOGIC

### Robust API Client:

```javascript
// Enhanced apiFetch with retry and error handling
async function apiFetch(path, opts = {}, retryCount = 0) {
  const maxRetries = 3;
  const retryDelay = Math.pow(2, retryCount) * 1000; // Exponential backoff

  try {
    const API_BASE = await getApiBaseAsync();
    const url = `${API_BASE}${path.startsWith('/') ? '' : '/'}${path}`;

    const { pfai_id_token } = await chrome.storage.local.get(['pfai_id_token']);
    const headers = Object.assign({ 'Content-Type': 'application/json' }, opts.headers || {});
    
    if (pfai_id_token) {
      headers['Authorization'] = 'Bearer ' + pfai_id_token;
    }

    const resp = await fetch(url, { ...opts, headers });

    // Handle different response scenarios
    if (resp.status === 401) {
      await chrome.storage.local.remove('pfai_id_token');
      await trackUsageEvent(TRACKING_EVENTS.AUTH_FAILED, { 
        context: 'api_call', 
        path, 
        status: 401 
      });
      openLoginPopup();
      return resp;
    }

    if (resp.status === 429) { // Rate limited
      if (retryCount < maxRetries) {
        await sleep(retryDelay);
        return apiFetch(path, opts, retryCount + 1);
      }
    }

    if (!resp.ok && retryCount < maxRetries) {
      // Retry for 5xx errors
      if (resp.status >= 500) {
        await sleep(retryDelay);
        return apiFetch(path, opts, retryCount + 1);
      }
    }

    return resp;

  } catch (error) {
    await trackUsageEvent(TRACKING_EVENTS.ERROR_OCCURRED, {
      context: 'api_fetch',
      path,
      error: error.message,
      retryCount
    });

    if (retryCount < maxRetries) {
      await sleep(retryDelay);
      return apiFetch(path, opts, retryCount + 1);
    }
    
    throw error;
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}
```

## 6. NEW FEATURES IMPLEMENTATION

### A. Real-time Usage Analytics:

```javascript
// NEW: analytics-dashboard.js for options page
class AnalyticsDashboard {
  async generateUsageChart() {
    const usageData = await this.authManager.apiCall('/users/analytics/usage?period=7d');
    if (usageData.ok) {
      const data = await usageData.json();
      this.renderUsageChart(data.data);
    }
  }

  renderUsageChart(data) {
    // Create canvas chart showing:
    // - Daily upgrade counts
    // - Credits spent over time  
    // - Most improved websites
    // - Upgrade success rates
  }
}
```

### B. Smart Offline Mode:

```javascript
// NEW: offline-manager.js
class OfflineManager {
  constructor() {
    this.cachedTechniques = null;
    this.queuedActions = [];
  }

  async loadLocalCompendium() {
    // Load techniques from extension's compendium.json
    const response = await fetch(chrome.runtime.getURL('compendium.json'));
    this.cachedTechniques = await response.json();
  }

  async queueAction(action) {
    this.queuedActions.push({
      ...action,
      timestamp: Date.now(),
      retryCount: 0
    });
    
    // Try to process queue when online
    this.processQueue();
  }

  async processQueue() {
    if (!navigator.onLine) return;

    const pending = [...this.queuedActions];
    this.queuedActions = [];

    for (const action of pending) {
      try {
        await this.executeAction(action);
        await trackUsageEvent('queued_action_processed', { actionType: action.type });
      } catch (error) {
        if (action.retryCount < 3) {
          action.retryCount++;
          this.queuedActions.push(action);
        }
      }
    }
  }
}
```

### C. Enhanced Security Features:

```javascript
// NEW: security-manager.js
class SecurityManager {
  static validateApiResponse(response, expectedSchema) {
    // Validate response against expected schema
    // Prevent injection attacks through API responses
  }

  static sanitizePromptInput(input) {
    // Remove potentially malicious content from prompts
    // Detect and block prompt injection attempts
    return input.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');
  }

  static async checkDomainSafety(domain) {
    // Check against known malicious domains
    // Implement domain reputation checking
  }
}
```

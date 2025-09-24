# API Request Structure Reference

This file documents the expected JSON request structure for all user-related endpoints in the backend. Use this as the canonical source for frontend-backend integration.

---

## /api/v1/users/auth/complete (POST)
- **Description:** Onboard or login a user. No request body required. Auth Bearer token must be sent in the Authorization header.
- **Request Body:** _None_

---

## /api/v1/users/me (GET)
- **Description:** Get the current user's public profile. Auth Bearer token required.
- **Request Body:** _None_

---

## /api/v1/users/me/preferences (PUT)
- **Description:** Update user preferences.
- **Request Body Example:**
```json
{
  "theme": "dark",
  "notifications": true
}
```
- **Notes:**
  - All fields are optional.
  - See `PreferencesModel` in backend for allowed keys.

---

## /api/v1/users/me/preferences (GET)
- **Description:** Get user preferences.
- **Request Body:** _None_

---

## /api/v1/users/credits (GET)
- **Description:** Get user's available credits.
- **Request Body:** _None_

---

## /api/v1/users/update-profile (POST) and /api/v1/users/profile (PUT)
- **Description:** Update user profile information.
- **Request Body Example:**
```json
{
  "profile": {
    "display_name": "Jane Doe",
    "bio": "AI enthusiast",
    "location": "NYC",
    "website": "https://janedoe.com",
    "twitter": "@janedoe",
    "github": "janedoe",
    "linkedin": "janedoe",
    "company": "OpenAI",
    "job_title": "Engineer",
    "preferences": { "theme": "dark" }
  }
}
```
- **Notes:**
  - Only whitelisted fields in `profile` are accepted.

---

## /api/v1/users/delete-account (POST) and /api/v1/users/account (DELETE)
- **Description:** Delete user account (requires confirmation).
- **Request Body Example:**
```json
{
  "confirmation": "DELETE_MY_ACCOUNT"
}
```

---

## /api/v1/users/export-data (GET)
- **Description:** Export all user data (GDPR-style).
- **Request Body:** _None_

---

## /api/v1/users/preferences (PUT)
- **Description:** Update user preferences (alternate endpoint).
- **Request Body Example:**
```json
{
  "theme": "dark",
  "notifications": true
}
```

---

## /api/v1/users/preferences (GET)
- **Description:** Get user preferences (alternate endpoint).
- **Request Body:** _None_

---

## /api/v1/users/stats (GET)
- **Description:** Get high-level user statistics.
- **Request Body:** _None_

---

If you need the structure for any other endpoint, append it below.

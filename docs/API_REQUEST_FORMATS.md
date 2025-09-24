# 📝 PromptForge.ai API - Correct Request Formats

This document shows the correct request formats for all endpoints that require request bodies.

---

## 🚨 **Authentication**
All protected endpoints require a valid bearer token:
```
Authorization: Bearer your-jwt-token-here
```

---

## 📝 **Prompts Endpoints**

### 1. Create New Prompt
```http
POST /api/v1/prompts/
Content-Type: application/json
Authorization: Bearer your-token

{
  "title": "Email Assistant",
  "body": "You are a helpful assistant. Write a {type} email about {topic}.",
  "role": "assistant",
  "category": "business",
  "tags": ["email", "business"],
  "is_public": false
}
```

**Required fields:**
- `title` (3-100 characters)
- `body` (min 1 character)
- `role` (1-100 characters)

### 2. Update Prompt
```http
PUT /api/v1/prompts/{prompt_id}
Content-Type: application/json
Authorization: Bearer your-token

{
  "title": "Updated Email Assistant",
  "body": "You are an expert assistant. Write a {type} email about {topic}.",
  "role": "expert assistant"
}
```

### 3. Test Drive Prompt
```http
POST /api/v1/prompts/test-drive-by-id
Content-Type: application/json
Authorization: Bearer your-token

{
  "prompt_id": "actual-prompt-id-here",
  "inputs": {
    "type": "professional",
    "topic": "project updates"
  }
}
```

### 4. Bulk Action on Prompts
```http
POST /api/v1/prompts/bulk-action
Content-Type: application/json
Authorization: Bearer your-token

{
  "action": "delete",
  "prompt_ids": ["prompt-id-1", "prompt-id-2"],
  "new_status": "archived"
}
```

---

## 🤖 **AI Features Endpoints**

### 1. Remix Prompt
```http
POST /api/v1/ai/remix-prompt
Content-Type: application/json
Authorization: Bearer your-token

{
  "prompt_body": "Write an email about project updates",
  "style": "professional",
  "target_audience": "team members",
  "enhancement_level": "medium"
}
```

**Required fields:**
- `prompt_body` (min 1 character)

### 2. Architect Prompt
```http
POST /api/v1/ai/architect-prompt
Content-Type: application/json
Authorization: Bearer your-token

{
  "description": "Build a REST API for user management",
  "techStack": ["python", "fastapi", "mongodb"],
  "architectureStyle": "microservices"
}
```

**Required fields:**
- `description`
- `techStack` (array)
- `architectureStyle`

### 3. Fuse Prompts
```http
POST /api/v1/ai/fuse-prompts
Content-Type: application/json
Authorization: Bearer your-token

{
  "prompt_a": "You are a helpful email assistant",
  "prompt_b": "You are a professional writer"
}
```

### 4. Generate Enhanced Prompt
```http
POST /api/v1/ai/generate-enhanced-prompt
Content-Type: application/json
Authorization: Bearer your-token

{
  "prompt_a": "Help me write emails",
  "prompt_b": "Make it professional and engaging"
}
```

**Required fields:**
- `prompt_a` (text to enhance)
- `prompt_b` (enhancement context)

### 5. Analyze Prompt
```http
POST /api/v1/ai/analyze-prompt
Content-Type: application/json
Authorization: Bearer your-token

{
  "code": "Write a professional email",
  "analysisType": "prompt",
  "filename": "optional-filename.txt"
}
```

---

## 🏪 **Marketplace Endpoints**

### 1. List Prompt in Marketplace
```http
POST /api/v1/marketplace/list-prompt
Content-Type: application/json
Authorization: Bearer your-token

{
  "prompt_id": "your-prompt-id",
  "price_credits": 10,
  "description": "Professional email writing assistant",
  "tags": ["email", "business", "professional"]
}
```

### 2. Rate Marketplace Prompt
```http
POST /api/v1/marketplace/rate
Content-Type: application/json
Authorization: Bearer your-token

{
  "prompt_id": "marketplace-prompt-id",
  "rating": 5,
  "review_title": "Excellent prompt!",
  "review_content": "Very helpful for writing professional emails",
  "pros": ["Easy to use", "Great results"],
  "cons": ["Could use more examples"],
  "would_recommend": true
}
```

---

## 📦 **Packaging Endpoints**

### 1. Package Prompt for Marketplace
```http
POST /api/v1/packaging/{prompt_id}/package
Content-Type: application/json
Authorization: Bearer your-token

{
  "marketplace_ready": true,
  "sales_copy": "Professional email writing made easy",
  "tags": ["email", "business"],
  "price_usd": 9.99,
  "sales_title": "Email Pro Assistant"
}
```

### 2. Manage Packages Bulk
```http
POST /api/v1/packaging/manage-bulk
Content-Type: application/json
Authorization: Bearer your-token

{
  "action": "update_price",
  "package_ids": ["package-1", "package-2"],
  "new_price": 15.99,
  "bulk_tags": ["premium", "professional"]
}
```

---

## 🤝 **Partnerships Endpoints**

### 1. Request Partnership
```http
POST /api/v1/partnerships/request
Content-Type: application/json
Authorization: Bearer your-token

{
  "business_type": "SaaS",
  "use_case": "AI-powered content generation",
  "expected_monthly_volume": 10000,
  "company_name": "YourCompany Inc",
  "website_url": "https://yourcompany.com",
  "portfolio_urls": ["https://portfolio1.com", "https://portfolio2.com"]
}
```

### 2. Manage Partner Revenue
```http
POST /api/v1/partnerships/revenue
Content-Type: application/json
Authorization: Bearer your-token

{
  "action": "request_payout",
  "payout_amount": 500.00,
  "payment_method": {
    "type": "bank_transfer",
    "account_number": "1234567890"
  },
  "statement_period": "2025-08"
}
```

---

## 🔔 **Notifications Endpoints**

### 1. Create Notification
```http
POST /api/v1/notifications/
Content-Type: application/json
Authorization: Bearer your-token

{
  "title": "Welcome to PromptForge!",
  "message": "Start creating amazing prompts today",
  "type": "welcome",
  "priority": "medium",
  "action_url": "/dashboard"
}
```

### 2. Create Bulk Notifications
```http
POST /api/v1/notifications/bulk
Content-Type: application/json
Authorization: Bearer your-token

{
  "user_ids": ["user1", "user2", "user3"],
  "title": "System Maintenance",
  "message": "Scheduled maintenance tonight",
  "type": "system",
  "priority": "high"
}
```

### 3. Send Push Notification
```http
POST /api/v1/notifications/push
Content-Type: application/json
Authorization: Bearer your-token

{
  "user_id": "target-user-id",
  "title": "New Feature Available",
  "body": "Check out our new AI architect feature",
  "icon": "/icons/feature.png",
  "click_action": "/features/architect"
}
```

---

## 📊 **Analytics Endpoints**

### 1. Log Analytics Events
```http
POST /api/v1/analytics/events
Content-Type: application/json
Authorization: Bearer your-token

{
  "events": [
    {
      "type": "prompt_created",
      "data": {
        "prompt_id": "123",
        "category": "email"
      },
      "timestamp": "2025-09-03T15:30:00Z"
    }
  ],
  "session_id": "session-123"
}
```

### 2. Create Analytics Job
```http
POST /api/v1/analytics/jobs/analytics
Content-Type: application/json
Authorization: Bearer your-token

{
  "job_type": "export_user_data",
  "parameters": {
    "user_id": "user-123",
    "date_range": "30d",
    "format": "csv"
  },
  "job_name": "User Data Export",
  "priority": 10,
  "notification_email": "user@example.com",
  "retention_days": 7
}
```

---

## 💳 **Payments Endpoints**

### 1. Initiate Payment
```http
POST /api/v1/payments/initiate-payment
Content-Type: application/json
Authorization: Bearer your-token

{
  "amount": 29.99,
  "currency": "USD",
  "payment_method": "card",
  "plan": "pro_monthly",
  "success_url": "https://yourapp.com/success",
  "cancel_url": "https://yourapp.com/cancel"
}
```

---

## 📧 **Email Automation Endpoints**

### 1. Unsubscribe from Emails
```http
POST /api/v1/emails/unsubscribe
Content-Type: application/json

{
  "email": "user@example.com",
  "token": "unsubscribe-token-123",
  "categories": ["marketing", "newsletter"]
}
```

### 2. Create Email Template
```http
POST /api/v1/emails/templates
Content-Type: application/json
Authorization: Bearer your-token

{
  "name": "welcome_email",
  "subject": "Welcome to PromptForge!",
  "html_content": "<h1>Welcome {{user_name}}!</h1>",
  "text_content": "Welcome {{user_name}}!",
  "category": "onboarding",
  "variables": ["user_name", "plan_name"]
}
```

### 3. Trigger Feature Announcement
```http
POST /api/v1/emails/automation/trigger-feature-announcement
Content-Type: application/json
Authorization: Bearer your-token

{
  "feature_name": "AI Architect",
  "description": "Build complex prompts with AI assistance",
  "launch_date": "2025-09-15",
  "target_users": ["pro", "enterprise"],
  "include_demo": true
}
```

---

## 💡 **Quick Testing Examples**

### Test with curl:
```bash
# Test create prompt
curl -X POST http://localhost:8000/api/v1/prompts/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-token" \
  -d '{
    "title": "Test Prompt",
    "body": "You are a helpful assistant",
    "role": "assistant"
  }'

# Test remix prompt
curl -X POST http://localhost:8000/api/v1/ai/remix-prompt \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-token" \
  -d '{
    "prompt_body": "Write an email",
    "style": "professional"
  }'
```

---

## 🔍 **Common Validation Errors**

1. **422 Unprocessable Entity**: Missing required fields or invalid field types
2. **401 Unauthorized**: Missing or invalid Authorization header
3. **404 Not Found**: Resource doesn't exist (e.g., prompt_id not found)
4. **400 Bad Request**: Invalid business logic (e.g., insufficient credits)

Make sure all required fields are included and match the exact field names and types shown above!

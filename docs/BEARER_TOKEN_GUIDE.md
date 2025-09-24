# 🔐 How to Get Bearer Token for PromptForge.ai API Testing

## Method 1: Using Firebase Auth (Recommended for Development)

### Step 1: Get Firebase ID Token

You have several options to get a Firebase ID token:

#### Option A: Using Firebase Console (Quickest for Testing)

1. **Go to Firebase Console**: https://console.firebase.google.com
2. **Select your project** (check your `.env` for `GOOGLE_CLOUD_PROJECT`)
3. **Authentication > Users** - Add a test user or use existing
4. **Use Firebase Auth Emulator** or **Frontend SDK** to get ID token

#### Option B: Using a Simple HTML Test Page

Create a test HTML file to get tokens:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Get Firebase Token</title>
    <script src="https://www.gstatic.com/firebasejs/9.0.0/firebase-app.js"></script>
    <script src="https://www.gstatic.com/firebasejs/9.0.0/firebase-auth.js"></script>
</head>
<body>
    <h1>Firebase Token Generator</h1>
    <input type="email" id="email" placeholder="Email" />
    <input type="password" id="password" placeholder="Password" />
    <button onclick="signIn()">Sign In</button>
    <button onclick="getToken()">Get Token</button>
    <pre id="token"></pre>

    <script>
        // Replace with your Firebase config
        const firebaseConfig = {
            apiKey: "your-api-key",
            authDomain: "your-project.firebaseapp.com", 
            projectId: "your-project-id"
        };

        firebase.initializeApp(firebaseConfig);

        async function signIn() {
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            
            try {
                await firebase.auth().signInWithEmailAndPassword(email, password);
                console.log('Signed in successfully');
            } catch (error) {
                console.error('Sign in error:', error);
            }
        }

        async function getToken() {
            const user = firebase.auth().currentUser;
            if (user) {
                const token = await user.getIdToken();
                document.getElementById('token').textContent = token;
                console.log('ID Token:', token);
            } else {
                console.log('No user signed in');
            }
        }
    </script>
</body>
</html>
```

#### Option C: Using Firebase CLI (For Development)

```bash
# Install Firebase CLI
npm install -g firebase-tools

# Login and get token
firebase login
firebase auth:export --format=json users.json

# Or use Firebase Auth Emulator
firebase emulators:start --only auth
```

---

## Method 2: Create a Test Token Endpoint (Quick Development Solution)

Add this temporary endpoint to your API for testing:

### Add to `api/users.py`:

```python
@router.post("/dev/get-test-token", tags=["Development"])
async def get_test_token(email: str = "test@example.com"):
    """DEV ONLY: Generate a test Firebase token for API testing"""
    if os.getenv("ENVIRONMENT") != "development":
        raise HTTPException(status_code=404, detail="Not found")
    
    # Create a custom token (requires Firebase Admin SDK)
    try:
        custom_token = fb_auth.create_custom_token("test-user-123", {
            "email": email,
            "email_verified": True,
            "name": "Test User"
        })
        return {
            "custom_token": custom_token.decode(),
            "instructions": "Use this token to sign in via Firebase Client SDK to get ID token"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Token creation failed: {e}")
```

---

## Method 3: Use curl to Test Auth Complete Endpoint

### Step 1: Create a test user in your system

```bash
# First, let's test the auth complete endpoint with a mock token
curl -X POST http://localhost:8000/api/v1/users/auth/complete \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_FIREBASE_ID_TOKEN_HERE"
```

---

## Method 4: For Testing Without Real Firebase (Mock Token)

### Add this development-only bypass to `auth.py`:

```python
async def verify_firebase_token(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        logger.warning(f"Missing or malformed Authorization header: {authorization}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    
    id_token = authorization.split(" ", 1)[1].strip()
    
    # DEV ONLY: Allow mock token for testing
    if os.getenv("ENVIRONMENT") == "development" and id_token == "mock-test-token":
        return {
            "uid": "test-user-123",
            "email": "test@example.com",
            "email_verified": True,
            "name": "Test User"
        }
    
    try:
        logger.info(f"Verifying Firebase ID token: {id_token[:12]}... (truncated)")
        decoded = fb_auth.verify_id_token(id_token, check_revoked=True)
        logger.info(f"Token verified for uid: {decoded.get('uid')}")
        return decoded
    except Exception as e:
        logger.error(f"Firebase token verification failed: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
```

Then you can use: `Bearer mock-test-token` for testing.

---

## Step-by-Step Testing in Swagger UI

### 1. **Open Swagger UI**: http://localhost:8000/docs

### 2. **Click "Authorize" button** (🔒 icon)

### 3. **Enter Bearer Token**:
```
Bearer your_firebase_id_token_here
```

### 4. **Test Authentication**:
Try the `/api/v1/users/auth/complete` endpoint first to create your user profile.

### 5. **Test Other Endpoints**:
Now you can test all protected endpoints!

---

## Quick Test Sequence

1. **Get Token** (using one of the methods above)
2. **Authorize in Swagger UI**
3. **Test auth/complete**:
   ```json
   POST /api/v1/users/auth/complete
   // No body needed, just valid Bearer token
   ```
4. **Test get user profile**:
   ```json
   GET /api/v1/users/me
   ```
5. **Test other endpoints** from your documentation!

---

## Environment Variables Needed

Make sure your `.env` has:
```env
ENVIRONMENT=development
FIREBASE_SERVICE_ACCOUNT_B64=your_base64_encoded_service_account_json
GOOGLE_CLOUD_PROJECT=your-firebase-project-id
```

---

## 🎯 Recommended for Quick Testing

**Use Method 4** (mock token) for immediate testing:

1. Add the mock token code to `auth.py`
2. Set `ENVIRONMENT=development` in your `.env`
3. Use `Bearer mock-test-token` in Swagger UI
4. Start testing all endpoints immediately!

This will let you test all your API endpoints without setting up complex Firebase authentication first.

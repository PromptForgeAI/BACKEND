# 🔐 Frontend Authentication Integration for VS Code Extension

## 🎯 **WHAT YOUR FRONTEND NEEDS**

Your frontend (`localhost:3000`) needs to handle the route `/auth/vscode` to complete the authentication flow.

## 📋 **IMPLEMENTATION STEPS**

### **1. Create VS Code Auth Route**
Add this route to your frontend router:

```javascript
// Example for React Router
<Route path="/auth/vscode" component={VSCodeAuthPage} />

// Example for Next.js
// pages/auth/vscode.js or app/auth/vscode/page.js
```

### **2. VS Code Auth Page Component**

```javascript
// VSCodeAuthPage.jsx (React example)
import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

function VSCodeAuthPage() {
  const [searchParams] = useSearchParams();
  const [isLoading, setIsLoading] = useState(false);
  
  const callback = searchParams.get('callback');
  const state = searchParams.get('state');
  const source = searchParams.get('source');

  const handleAuthComplete = (token) => {
    if (callback && state) {
      // Redirect back to VS Code with token
      const callbackUrl = `${callback}?token=${token}&state=${state}`;
      window.location.href = callbackUrl;
    }
  };

  return (
    <div className="vscode-auth-page">
      <div className="auth-header">
        <h1>🔐 Connect VS Code to PromptForgeAI</h1>
        <p>Complete authentication to enable AI features in VS Code</p>
      </div>
      
      {/* Your existing auth components */}
      <SignInForm onSuccess={handleAuthComplete} />
      <SignUpForm onSuccess={handleAuthComplete} />
    </div>
  );
}
```

### **3. Auth Flow Handler**

```javascript
// In your auth service/hook
const handleVSCodeAuth = async (email, password) => {
  try {
    setIsLoading(true);
    
    // Your existing login logic
    const response = await signIn(email, password);
    
    if (response.success) {
      const token = response.token; // or response.data.token
      
      // Call the callback handler
      onSuccess?.(token);
    }
  } catch (error) {
    console.error('VS Code auth failed:', error);
  } finally {
    setIsLoading(false);
  }
};
```

## 🌐 **URL PARAMETERS EXPLANATION**

When VS Code opens your frontend, it will include these parameters:

- `callback`: `vscode://promptforgeai.promptforgeai/auth-callback`
- `state`: Random security token (e.g., `kttkjg37fc`)
- `source`: `vscode`

## 🎨 **UI CONSIDERATIONS**

```css
/* VS Code-specific styling */
.vscode-auth-page {
  background: linear-gradient(135deg, #007acc, #005a9e);
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}

.auth-header {
  text-align: center;
  margin-bottom: 2rem;
  color: white;
}

.auth-header h1 {
  font-size: 2.5rem;
  margin-bottom: 0.5rem;
}

.auth-header p {
  opacity: 0.9;
  font-size: 1.1rem;
}
```

## 🔄 **COMPLETE FLOW EXAMPLE**

1. **User clicks "Sign In" in VS Code**
2. **VS Code opens**: `http://localhost:3000/auth/vscode?callback=vscode://promptforgeai.promptforgeai/auth-callback&state=abc123&source=vscode`
3. **Frontend shows auth form**
4. **User signs in successfully**
5. **Frontend redirects to**: `vscode://promptforgeai.promptforgeai/auth-callback?token=user_token_here&state=abc123`
6. **VS Code receives callback and stores token**

## 🚨 **SECURITY NOTES**

- Always validate the `state` parameter
- Use HTTPS in production
- Token should be JWT or API key
- Consider token expiration

## 🧪 **TESTING**

Test the flow by:
1. Running your frontend on `localhost:3000`
2. Opening VS Code extension
3. Clicking "Sign In with PromptForgeAI"
4. Completing auth in browser
5. Confirming VS Code receives token

---

**💡 This integration enables seamless Chrome extension-like authentication in VS Code!**

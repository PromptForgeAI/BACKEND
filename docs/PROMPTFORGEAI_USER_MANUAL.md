# 🧠 PromptForgeAI VS Code Extension — User Guide (Copilot‑First v2)

*Transform prompts inline, directly inside the GitHub Copilot chat/input bar. No extra files, no context‑switching.*

---

## 🚀 What is PromptForgeAI?

PromptForgeAI is an inline prompt‑upgrade and analysis engine that plugs into the **GitHub Copilot chat/input bar** (and standard VS Code input fields). It rewrites, analyzes, and structures your prompt **in place** before you send it. Think: *press a key, your messy thought becomes a clean, powerful prompt—right where you're typing.*

**Core value:** zero friction → **type → upgrade → send**.

---

## 🎯 Quick Start (Zero Manual Files)

### Step 1: Sign In (browser flow; no tokens)

1. Open VS Code.
2. `Ctrl+Shift+P` → **PromptForgeAI: Sign In**.
3. A secure browser tab opens → complete login.
4. Return to VS Code → status bar shows **PF: Signed In**.

> **Note:** API Base URL & secrets are **auto‑managed** by the extension. Users never copy/paste tokens or change base URLs.

### Step 2: Type Anywhere (Copilot bar or editor)

* Place your cursor in the **Copilot chat/input bar** (or any text input field/editor).
* Type your rough prompt.

### Step 3: Upgrade Inline

* Press **`Ctrl+Alt+U` (Win/Linux)** or **`Cmd+Alt+U` (Mac)** to **Upgrade Inline**.
* Your text is replaced **in place** with the upgraded version.
* Press **Enter** to send to Copilot (or continue editing).

---

## ⚡ Inline Magic (No a.md / .txt Required)

PromptForgeAI works **where you type**:

* **Inline Upgrade**: Rewrite/expand with structure, constraints, tone.
* **Inline Analyze**: Popover with Clarity/Specificity/Suggestions—accept fixes.
* **Inline Flags**: Lightweight PFCL flags right in the input (e.g., `/upgrade`, `/clean`, `/brainstorm`, `/structure`, `/cot`).

> The previous flow (creating `.md`/`.txt` files and right‑clicking) is deprecated.

---

## 🎛️ Features

* **🚀 Quick Upgrade (Free)**: fast polish & structure.
* **💎 Pro Upgrade**: goal/constraints/style infusion + anti‑ambiguity pass.
* **🔍 Analyze**: instant rubric with one‑click fixes.
* **🧠 Intelligence Panel** (optional): a side panel for history, templates, and batch upgrades—**not required** for inline use.
* **📈 Analytics**: local stats; opt‑in telemetry.

---

## ⌨️ Keyboard Shortcuts (Inline‑First)

| Action                            | Windows/Linux | Mac         | Notes                             |
| --------------------------------- | ------------- | ----------- | --------------------------------- |
| **Upgrade Inline (replace text)** | `Ctrl+Alt+U`  | `Cmd+Alt+U` | Works in Copilot bar & editors    |
| **Analyze Inline (popover)**      | `Ctrl+Alt+A`  | `Cmd+Alt+A` | Accept suggested fixes            |
| **Quick Suggestions**             | `Ctrl+Alt+S`  | `Cmd+Alt+S` | Idea snippets/cues                |
| **Open Intelligence Panel**       | `Ctrl+Alt+I`  | `Cmd+Alt+I` | Optional workspace                |
| **Apply PFCL Flag**               | `Ctrl+Alt+P`  | `Cmd+Alt+P` | Insert `/upgrade`, `/clean`, etc. |

> All shortcuts can be remapped: **Keyboard Shortcuts → search "PromptForgeAI."**

---

## 🗺️ How to Use (Inline Flow)

### A. Upgrade while typing in Copilot

1. Type: `explain this function`
2. Hit **Upgrade Inline** → becomes:

   > *"Explain the function step‑by‑step, clarify inputs/outputs, time/space complexity, edge cases, and provide a minimal example. Keep it concise (150–200 words)."*
3. Press **Enter** to send via Copilot.

### B. Add constraints with flags

* Type: `/upgrade write a cover letter for data science intern`
* Hit **Upgrade Inline** →

  * role, tone, length, metrics, company context inferred from your workspace.

### C. Analyze without replacing

* Select text → **Analyze Inline** → popover shows Clarity/Specificity/Suggestions → Apply fix.

---

## 🎪 PFCL Flags (Inline)

* `/upgrade` – advanced prompt engineering & constraint infusion.
* `/clean` – remove fluff, keep semantics.
* `/brainstorm` – generate multiple angles/variants.
* `/structure` – headings, bullets, sections.
* `/cot` – chain‑of‑thought style *guidance* (model‑friendly reasoning scaffolds without leaking secrets).

> Flags can be combined: `/upgrade /clean`, `/structure /brainstorm`.

---

## 🔧 Settings (Safe by Default)

* **Plan**: Free / Pro / Enterprise (read‑only).
* **Auto Suggestions**: on/off.
* **Privacy**: telemetry opt‑in; redaction on by default.
* **Workspace Context Sources**: enable/disable codebase snippets, open editors, selection.

> **No manual API Base URL. No token paste.** These are managed securely by the extension.

---

## 🆘 Troubleshooting

**"Not authenticated"**

* Status bar → **PF: Sign In**.
* Or `Ctrl+Shift+P` → **PromptForgeAI: Sign In**.

**Inline shortcuts don't work in Copilot bar**

* Ensure **GitHub Copilot Chat** is enabled.
* Rebind shortcut if Copilot/other extensions conflict.
* `Developer: Reload Window` after install/update.

**No popover on Analyze**

* Check: `Settings → PromptForgeAI → Inline UI` enabled.

**Slow responses**

* Check connection; Free plan rate‑limits apply.
* Pro/Enterprise use priority lanes.

**Panel missing**

* `Ctrl+Alt+I` or Sidebar 🧠 icon.

---

## 📊 Plans

**Free**: Quick Upgrade, inline analyze (basic), daily cap.
**Pro**: Unlimited upgrades, advanced analyzer, workflows, team templates.
**Enterprise**: SSO, org policies, admin templates, audit logs.

---

## 🔐 Privacy & Security

* Browser‑based OAuth; zero local secret storage.
* API endpoints & base URLs are centrally configured and signed.
* On‑device redaction of emails/keys/IDs before send (opt‑out).
* Workspace‑context access is explicit and revocable.

---

## 🧪 Power Tips

* Draft messy → **Upgrade Inline** → ship.
* Save winning prompts in **Templates**; bind to snippets.
* Use **Analyze** when results feel vague—tighten scope/metrics.
* Batch‑upgrade in the panel for docs/README work; stay inline for Copilot.

---

## ❌ Deprecated (Old Flow)

* Creating `.md` or `.txt` just to upgrade → **removed**.
* Manual API base URL or token pasting → **removed**.
* Context‑switch right‑click flows → **replaced by inline actions**.

---

## 📦 Dev Notes (for testers)

* Inline hooks use VS Code **Inline Chat** & **InputBox** APIs.
* Replacement is transactional; undo/redo supported.
* Conflicts resolved via VS Code TextEditorEdit batching.
* Telemetry is privacy‑safe; disable via Settings.

---

## 🎉 You're Ready

Type → **Upgrade Inline** → Send. That's the flow. Stay in the Copilot bar; let PromptForgeAI do the polishing.

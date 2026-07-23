# 🚀 AI Session Dashboard

Unified control dashboard for **atoTerminal**, **Claude Code**, and **Antigravity (AGY)** CLI sessions.

![Dashboard Preview](static/index.html)

## ✨ Key Features

- ⚡ **Multi-CLI Session Overview**: Automatically parses and aggregates sessions from `atoTerminal`, `Claude Code`, and `Antigravity (AGY)`.
- ▶️ **One-Click Session Resume**: Instantly restore & launch sessions in a new tab using **`cmux`** (macOS) or **`Windows Terminal`** (Windows).
- 🔔 **Needs Review & Status Badges**: Detects sessions awaiting user attention or feedback with glowing indicator badges.
- 📦 **Archive & Custom Rename**: Easily organize sessions with custom titles and archiving capabilities.
- 🗑️ **Safe Session Deletion**: Safely clean up unwanted sessions with a confirmation guard.
- 💬 **Full Chat History Modal**: Inspect entire conversation logs, including user prompts, AI responses, and tool calls.
- 🌐 **Cross-Platform**: Fully compatible with macOS and Windows.

---

## 🚀 Quick Start

### 1. Requirements

- Python 3.10+
- [`uv`](https://github.com/astral-sh/uv) (recommended Python package manager)

### 2. Run Locally

```bash
# Clone repository
git clone https://github.com/taku-me/ai-session-dashboard.git
cd ai-session-dashboard

# Start dashboard server with uv
uv run python run.py
```

Open your browser and navigate to: **`http://localhost:8888`**

---

## 🛠️ Architecture

- **Backend**: FastAPI + Uvicorn + Pydantic
- **Frontend**: Glassmorphism UI (Vanilla CSS + HTML5 + JavaScript ES6)
- **Multi-Agent Integrations**:
  - `atoTerminal` (`~/.ato/sessions/`)
  - `Claude Code` (`~/.claude/projects/` & `history.jsonl`)
  - `Antigravity` (`~/.gemini/antigravity-cli/brain/`)

---

## 📄 License

MIT License

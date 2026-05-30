# 🧠 Claude Telegram Agent — LangGraph Edition

A Telegram chatbot whose "brain" is a **LangGraph ReAct agent** powered by Claude. It reasons, calls tools (web search included), observes the results, and loops until it has an answer. Conversation memory is handled by a checkpointer — no manual history bookkeeping.

---

## ✨ Features

- 🧠 **ReAct agent loop** — reason → act → observe, built by `create_react_agent`
- 🔎 **Web search tool** — client-side Tavily search the agent runs itself
- 💾 **Checkpointed memory** — per-conversation state keyed by `thread_id`
- 🧩 **Pluggable tools** — add any Python function as a tool
- ⚡ **Async** — non-blocking Telegram handlers

---

## 🚀 Quick Start

### 1. Set up the environment

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install "python-telegram-bot>=21" python-dotenv \
            langgraph langchain langchain-anthropic langchain-tavily
```

### 3. Configure your keys

Create a `.env` file next to `tg_bot_langgraph.py`:

```dotenv
ANTHROPIC_API_KEY=sk-ant-...
TELEGRAM_BOT_TOKEN=123456:ABC-...
TAVILY_API_KEY=tvly-...
```

> 🔑 **Where to get them**
> - **Telegram token** — message [@BotFather](https://t.me/BotFather) → `/newbot`
> - **Anthropic key** — [console.anthropic.com](https://console.anthropic.com)
> - **Tavily key** — [tavily.com](https://tavily.com) (free tier is plenty)

### 4. Run

```bash
python tg_bot_langgraph.py
```

---

## 💬 Chat Commands

| Command | Action |
|---------|--------|
| `/start` | Greeting and intro |
| `/reset` | Start a fresh conversation thread (clears memory) |

---

## 🧩 How It Works

`create_react_agent` builds a `StateGraph` with two nodes and a loop between them:

```
        ┌─────────┐   tool_calls?   ┌─────────┐
  ──────▶  agent   ├────── yes ─────▶  tools   │
        │  (LLM)  │                 │ (run fn)│
        └────┬────┘                 └────┬────┘
             │ no                        │
             ▼                           │
            END   ◀────────────  (back to agent)
```

1. **agent** node calls Claude. It either answers, or asks to call a tool.
2. A **conditional edge** checks the reply: tool call requested? → go to `tools`. Otherwise → `END`.
3. **tools** node runs the requested Python function and feeds the result back.
4. Control returns to **agent**, which now sees the tool output and continues.

The loop repeats until Claude answers without calling a tool.

Conversation state lives in a **checkpointer**, keyed by `thread_id` (here, the Telegram `chat_id`). There's no manual `history` dict — the graph stores and restores messages for you.

> **Note on web search:** Claude's native `web_search` is a *server-side* tool. LangGraph prefers *client-side* tools so its tool node can run them and you can watch the loop — that's why this version uses **Tavily** instead.

---

## 🔧 Customization

**Add a tool** — any Python function with a docstring becomes one:

```python
def get_time(timezone: str) -> str:
    """Return the current time for an IANA timezone like 'Europe/Istanbul'."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo(timezone)).isoformat()

agent = create_react_agent(model, tools=[search, get_time], prompt=SYSTEM_PROMPT, ...)
```

**Persist memory across restarts** — swap the checkpointer backend:

```python
# In-memory (default) — lost on restart
from langgraph.checkpoint.memory import MemorySaver
checkpointer = MemorySaver()

# SQLite — survives restarts
from langgraph.checkpoint.sqlite import SqliteSaver
checkpointer = SqliteSaver.from_conn_string("checkpoints.sqlite")

# Postgres — production
from langgraph.checkpoint.postgres import PostgresSaver
checkpointer = PostgresSaver.from_conn_string("postgresql://...")
```

**Inspect the loop** — stream the graph's steps to see reasoning vs. tool calls:

```python
async for chunk in agent.astream(
    {"messages": [{"role": "user", "content": user_text}]},
    config=config, stream_mode="updates",
):
    print(chunk)
```

> ⚠️ **Version note:** In the newest LangChain, `create_react_agent` is being renamed to `create_agent` (from the `langchain` package). If the import fails, switch to `from langchain.agents import create_agent`.

---

## 📦 Tech Stack

- **[LangGraph](https://langchain-ai.github.io/langgraph/)** — agent orchestration (the graph engine)
- **[LangChain](https://python.langchain.com)** — model & tool abstractions
- **[langchain-anthropic](https://pypi.org/project/langchain-anthropic/)** — Claude model wrapper
- **[Tavily](https://tavily.com)** — client-side web search tool
- **[python-telegram-bot](https://python-telegram-bot.org)** — async Telegram framework

---

## 🗺️ Roadmap

- [ ] Stream the agent's steps into Telegram in real time
- [ ] Add more tools (calculator, calendar, notes)
- [ ] Switch to a Postgres checkpointer for production
- [ ] Add human-in-the-loop approval before tool calls
- [ ] Dockerfile + VPS deployment

---

## 📄 License

MIT — do whatever you like, no warranty.
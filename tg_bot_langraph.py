"""
tg_bot_langgraph.py — same Telegram bot, but the "brain" is a LangGraph agent.

What LangGraph changes vs the plain-API version (tg_bot.py):
  - The manual `history` dict is GONE. A checkpointer (MemorySaver) stores
    each conversation's state, keyed by thread_id. We pass thread_id = chat_id.
  - The agent runs the ReAct loop for you (reason -> call tool -> observe ->
    answer), instead of you parsing tool_use blocks by hand.
  - Tools are plain Python functions/objects the agent's "tool node" executes.

Note on web search:
  Claude's native web_search is a SERVER-side tool (runs at Anthropic). LangGraph
  prefers CLIENT-side tools so its tool node can run them and you can watch the
  loop. So here we use Tavily search (a client-side tool) instead — same idea,
  but now the ReAct loop is visible and fully under your control.

Install:
    pip install "python-telegram-bot>=21" python-dotenv \
                langgraph langchain langchain-anthropic langchain-tavily

.env:
    ANTHROPIC_API_KEY=sk-ant-...
    TELEGRAM_BOT_TOKEN=123456:ABC...
    TAVILY_API_KEY=tvly-...        # free tier at tavily.com

Run:
    python tg_bot_langgraph.py

Chat commands: /start  /reset
"""

import os
from dotenv import load_dotenv

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from langchain_anthropic import ChatAnthropic
from langchain_tavily import TavilySearch
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

load_dotenv()

# --- Build the agent ONCE at startup ----------------------------------------
SYSTEM_PROMPT = (
    "You are a friendly Telegram assistant. Keep answers short. "
    "Use the search tool for recent events, prices, or weather, and cite sources."
)

# ChatAnthropic is LangChain's wrapper around the Claude API.
model = ChatAnthropic(model="claude-sonnet-4-6", max_tokens=1024)

# A client-side tool: the agent's tool node actually runs this. Add more freely.
search = TavilySearch(max_results=5)

# MemorySaver = in-process checkpointer. It stores each conversation's messages,
# so we no longer manage `history` ourselves. (Swap for SqliteSaver to persist.)
checkpointer = MemorySaver()

# create_react_agent builds a StateGraph (LLM node + tool node + the loop) for us.
# Heads-up: in the newest LangChain this is being renamed to `create_agent`
# (from `langchain`). create_react_agent still works; if your version errors on
# import, switch to: from langchain.agents import create_agent
agent = create_react_agent(
    model,
    tools=[search],
    prompt=SYSTEM_PROMPT,
    checkpointer=checkpointer,
)

# Per-chat "epoch". Bumping it on /reset starts a fresh thread_id => clean memory.
epochs: dict[int, int] = {}


def thread_id_for(chat_id: int) -> str:
    """A conversation key for the checkpointer. New epoch = fresh history."""
    return f"{chat_id}:{epochs.get(chat_id, 0)}"


async def ask_agent(chat_id: int, user_text: str) -> str:
    """Run the agent. thread_id ties this turn to its stored conversation state."""
    config = {"configurable": {"thread_id": thread_id_for(chat_id)}}
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": user_text}]},
        config=config,
    )
    # result["messages"] is the full running transcript; the last one is the answer.
    return result["messages"][-1].content


# --- Telegram handlers -------------------------------------------------------
async def start(update: Update, _: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi! Claude + LangGraph bot with web search. Ask me anything — "
        "I'll search the web when needed. Use /reset to clear the history."
    )


async def reset(update: Update, _: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    epochs[chat_id] = epochs.get(chat_id, 0) + 1  # next turn uses a fresh thread
    await update.message.reply_text("History cleared.")


async def on_message(update: Update, _: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        answer = await ask_agent(chat_id, update.message.text)
    except Exception as e:
        answer = f"Error: {type(e).__name__}: {e}"

    # Telegram truncates messages longer than 4096 chars — split into chunks.
    for i in range(0, len(answer), 4000):
        await update.message.reply_text(answer[i:i + 4000])


def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    print("Bot is running. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
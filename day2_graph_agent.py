import os
import sqlite3
from datetime import datetime
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

load_dotenv()
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
TODAY = os.getenv("TODAY", "2026-10-08")
DB = "file:retail.db?mode=ro"                       # read-only connection string

# ---------- Fake current stock (snapshot as of TODAY; moves to the database on Day 7) ----------
STOCK = {
    ("12", "amul butter"): 0,
    ("12", "britannia bread"): 140,
    ("7", "amul butter"): 85,
    ("7", "britannia bread"): 60,
}

def clean_store(store: str) -> str:
    """Normalise 'store 12' / 'Store 12' / '12' -> '12'."""
    return store.lower().replace("store", "").strip()

def query(sql: str, params: tuple = ()) -> list:
    """Run a read-only, parameterised query and return all rows."""
    conn = sqlite3.connect(DB, uri=True)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()

# ---------- Tool 1: what data exists? ----------
@tool
def list_catalog() -> dict:
    """List the stores and products that have sales data, and the date range covered.
    Call this first if you are unsure of exact store numbers or product names."""
    stores = [r[0] for r in query("SELECT DISTINCT store FROM sales ORDER BY store")]
    products = [r[0] for r in query("SELECT DISTINCT product FROM sales ORDER BY product")]
    first, last = query("SELECT MIN(sale_date), MAX(sale_date) FROM sales")[0]
    return {"stores": stores, "products": products, "sales_from": first, "sales_to": last}

# ---------- Tool 2: current stock ----------
@tool
def check_stock(store: str, product: str) -> dict:
    """Return the CURRENT stock units (today's snapshot) for a product in a store.

    Args:
        store: Store number, digits only, e.g. "12".
        product: Exact product name from list_catalog, e.g. "Amul butter".
    """
    store = clean_store(store)
    units = STOCK.get((store, product.lower()))
    if units is None:
        return {"error": f"No stock record for '{product}' in store {store}. Check names with list_catalog."}
    return {"store": store, "product": product, "units_in_stock_now": units, "as_of": TODAY}

# ---------- Tool 3: before/after comparison with a control group ----------
@tool
def compare_sales(store: str, product: str, split_date: str = "2026-10-01") -> list:
    """Compare average price and average daily units for one product BEFORE vs FROM a split date,
    for the given store AND for all other stores combined (control group).
    Use it to explain why sales changed.

    Args:
        store: Store number, digits only, e.g. "12".
        product: Exact product name from list_catalog, e.g. "Amul butter".
        split_date: Date the change started, format YYYY-MM-DD. Use "2026-10-01" if unknown.
    """
    store = clean_store(store)
    try:
        datetime.strptime(split_date, "%Y-%m-%d")           # validate the date format
    except ValueError:
        return [{"error": f"Bad split_date '{split_date}'. Use YYYY-MM-DD."}]

    rows = query(
        """
        SELECT CASE WHEN store = ? THEN 'store ' || store ELSE 'other stores (control)' END AS grp,
               CASE WHEN sale_date < ? THEN 'before' ELSE 'after' END AS period,
               MIN(sale_date), MAX(sale_date),
               ROUND(AVG(price), 2), ROUND(AVG(units), 1)
        FROM sales
        WHERE LOWER(product) = LOWER(?)
        GROUP BY grp, period
        ORDER BY grp DESC, period DESC
        """,
        (store, split_date, product),
    )
    if not rows:
        return [{"error": f"No sales for '{product}'. Check names with list_catalog."}]
    return [
        {"group": g, "period": p, "from": d1, "to": d2, "avg_price": ap, "avg_daily_units": au}
        for g, p, d1, d2, ap, au in rows
    ]

TOOLS = [list_catalog, check_stock, compare_sales]

# ---------- LLM ----------
llm = ChatGoogleGenerativeAI(model=MODEL, temperature=0, timeout=60, max_retries=2)
llm_with_tools = llm.bind_tools(TOOLS)

SYSTEM = SystemMessage(content=(
    f"You are a retail store operations analyst. Today is {TODAY}. "
    "Use tools for every fact; never guess numbers or names. "
    "If unsure of store numbers or product names, call list_catalog first. "
    "To explain a sales change, use compare_sales (it includes a control group of other stores) "
    "and check current stock. Stock from check_stock is a CURRENT snapshot; never use it to "
    "explain sales in earlier periods. "
    "Report separately: (1) the likely cause of the past change, with numbers, and "
    "(2) any current issue, such as being out of stock now. End with one caveat. "
    "If the question is outside retail sales and stock, say you can't help with it."
))

# ---------- Graph: State, Nodes, Edges ----------
class State(TypedDict):
    messages: Annotated[list, add_messages]            # history; add_messages APPENDS updates

def call_llm(state: State):                             # NODE 1: THINK
    response = llm_with_tools.invoke([SYSTEM] + state["messages"])
    return {"messages": [response]}

graph = StateGraph(State)
graph.add_node("llm", call_llm)
graph.add_node("tools", ToolNode(TOOLS))                # NODE 2: ACT (runs requested tools)
graph.add_edge(START, "llm")                             # start -> LLM
graph.add_conditional_edges("llm", tools_condition)      # tool requested? -> "tools", else -> END
graph.add_edge("tools", "llm")                           # tools -> back to LLM (the loop)
app = graph.compile()

# ---------- Helpers ----------
def show_graph():
    g = app.get_graph()
    print(g.draw_mermaid())
    try:
        with open("graph.png", "wb") as f:
            f.write(g.draw_mermaid_png())
        print("Saved graph.png\n")
    except Exception as e:
        print("Could not draw PNG:", e, "\n")

def show_state(messages):
    print(f"\n========== STATE: {len(messages)} messages ==========")
    for i, msg in enumerate(messages):
        print(f"\n[{i}] ", end="")
        msg.pretty_print()                  # built-in pretty view: type, content, tool calls
    print("=" * 50)

# ---------- Chat loop ----------
if __name__ == "__main__":
    show_graph()
    history = []
    print("Retail Ops Copilot. Ask a question, '/state' to see the state, or 'exit'.")
    while True:
        question = input("\nYou: ").strip()
        if question.lower() in ("exit", "quit"):
            break
        if question == "/state":
            show_state(history)
            continue
        if not question:
            continue
        try:
            history = history + [HumanMessage(content=question)]
            # stream_mode="updates": yields what EACH NODE added to the state, as it happens
            for chunk in app.stream({"messages": history},
                                    config={"recursion_limit": 10},
                                    stream_mode="updates"):
                for node_name, update in chunk.items():
                    print(f"\n----- node '{node_name}' added {len(update['messages'])} message(s) -----")
                    for msg in update["messages"]:
                        msg.pretty_print()
                    history = history + update["messages"]     # same as add_messages: append
            print("\nCopilot:", history[-1].text)
        except Exception as e:
            print("Error:", type(e).__name__, e)
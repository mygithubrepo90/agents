import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

# 1. Setup: read the key from .env and connect to Gemini
load_dotenv()
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
MAX_STEPS = 5  # guardrail: stops the agent looping forever

# 2. Fake data: stock units per (store, product)
STOCK = {
    ("12", "amul butter"): 0,
    ("12", "britannia bread"): 140,
    ("7", "amul butter"): 85,
}

# 3. The tool: the LLM can ASK for this, but OUR code runs it
def check_stock(store: str, product: str) -> dict:
    """Return the current stock units for a product in a store."""
    units = STOCK.get((store, product.lower()))
    if units is None:
        return {"error": f"No record for '{product}' in store {store}"}
    return {"store": store, "product": product, "units": units}

TOOLS = {"check_stock": check_stock}

# 4. Tell Gemini about the tool, and that we run the loop ourselves
config = types.GenerateContentConfig(
    tools=[check_stock],
    system_instruction="You are a retail store operations assistant. Use tools for facts; never guess stock numbers.",
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
)

# 5. The agent loop: THINK -> ACT -> OBSERVE -> repeat
def run_agent(question: str) -> str:
    contents = [types.Content(role="user", parts=[types.Part(text=question)])]
    for step in range(1, MAX_STEPS + 1):
        response = client.models.generate_content(model=MODEL, contents=contents, config=config)

        if not response.function_calls:        # no tool needed -> final answer
            return response.text

        contents.append(response.candidates[0].content)
        for call in response.function_calls:   # ACT: run each requested tool
            print(f"[step {step}] LLM asked for {call.name}({dict(call.args)})")
            result = TOOLS[call.name](**call.args)
            print(f"[step {step}] tool returned {result}")
            contents.append(types.Content(     # OBSERVE: send the result back
                role="user",
                parts=[types.Part.from_function_response(name=call.name, response=result)],
            ))
    return "Stopped: too many steps."

# 6. Try it
if __name__ == "__main__":
    print(run_agent("Is Amul butter in stock in store 12? And in store 7?"))
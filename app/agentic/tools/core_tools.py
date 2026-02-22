# app/agentic/tools/core_tools.py
def ping(text: str) -> dict:
    print("ping tool called with:", text)
    return {"echo": text}

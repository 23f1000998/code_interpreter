import sys
import traceback
from io import StringIO
from typing import List
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

app = FastAPI()

# CORS — let anyone access this
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class CodeRequest(BaseModel):
    code: str

class CodeResponse(BaseModel):
    error: List[int]
    result: str

def execute_python_code(code: str) -> dict:
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        exec(code, {})
        output = sys.stdout.getvalue()
        return {"success": True, "output": output}
    except Exception:
        output = traceback.format_exc()
        return {"success": False, "output": output}
    finally:
        sys.stdout = old_stdout

async def analyze_error_with_ai(code: str, tb: str) -> List[int]:
    token = os.environ.get("AIPIPE_TOKEN")
    prompt = f"""Analyze this Python code and traceback.
Return ONLY a JSON object with key "error_lines" containing a list of integer line numbers where the error occurred.

CODE:
{code}

TRACEBACK:
{tb}"""

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://aipipe.org/openrouter/v1/chat/completions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "model": "google/gemini-2.0-flash-lite-001",
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"}
            }
        )
    data = response.json()
    import json
    result = json.loads(data["choices"][0]["message"]["content"])
    return result.get("error_lines", [])

@app.post("/code-interpreter", response_model=CodeResponse)
async def code_interpreter(request: CodeRequest):
    outcome = execute_python_code(request.code)
    if outcome["success"]:
        return {"error": [], "result": outcome["output"]}
    else:
        lines = await analyze_error_with_ai(request.code, outcome["output"])
        return {"error": lines, "result": outcome["output"]}
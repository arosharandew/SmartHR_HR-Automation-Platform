from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from Orchestrator import Orchestrator
from Database.Helper import get_audit_log, get_stm_context, get_ltm_facts

app = FastAPI(title="HR Automation Platform")
orch = Orchestrator()

class RequestPayload(BaseModel):
    user_id: str
    session_id: str
    text: str

class ResponseModel(BaseModel):
    response: str
    intent: str
    confidence: float
    routed_agent: str
    session_id: str

@app.post("/request", response_model=ResponseModel)
async def handle_request(payload: RequestPayload):
    result = await orch.process(payload.user_id, payload.session_id, payload.text)
    return result

@app.get("/audit/{session_id}")
async def get_audit(session_id: str):
    logs = get_audit_log(session_id=session_id)
    if not logs:
        raise HTTPException(404, "No logs found")
    return {"session_id": session_id, "audit_log": logs}

@app.get("/memory/stm/{session_id}")
async def get_stm(session_id: str, limit: int = 10):
    stm = get_stm_context(session_id, last_n_turns=limit)
    return {"session_id": session_id, "short_term_memory": stm}

@app.get("/memory/ltm/{user_id}")
async def get_ltm(user_id: str, min_significance: float = 0.0):
    ltm = get_ltm_facts(user_id, min_significance)
    return {"user_id": user_id, "long_term_memory": ltm}

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
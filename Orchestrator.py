"""
Orchestrator.py - LangGraph-based router with memory injection, audit, and intent classification.
Includes greeting detection, robust JSON parsing, and proper argument passing.
"""

import time
import re
import json
import asyncio
from typing import TypedDict, Literal
from langgraph.graph import StateGraph, END  # Import END correctly
from Config.LLMConfig import LLMConfig
from Database.Helper import (
    get_stm_context, add_stm_turn, get_ltm_facts, add_ltm_fact,
    log_audit, set_session_state, get_stm_turn_count, clear_old_stm
)
from Agents.SchedulingAgent import SchedulingAgent
from Agents.LeaveAgent import LeaveAgent
from Agents.ComplianceAgent import ComplianceAgent
from Agents.ClarificationAgent import ClarificationAgent
from Agents.ProfileAgent import ProfileAgent

class OrchestratorState(TypedDict):
    user_id: str
    session_id: str
    user_input: str
    memory_context: str
    intent: str
    confidence: float
    response: str
    routed_agent: str
    latency_ms: int
    error: str

class Orchestrator:
    def __init__(self):
        self.scheduling = SchedulingAgent()
        self.leave = LeaveAgent()
        self.compliance = ComplianceAgent()
        self.clarification = ClarificationAgent()
        self.profile = ProfileAgent()
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(OrchestratorState)

        # Add nodes
        workflow.add_node("classify", self._classify_node)
        workflow.add_node("scheduling", self._scheduling_node)
        workflow.add_node("leave", self._leave_node)
        workflow.add_node("compliance", self._compliance_node)
        workflow.add_node("profile", self._profile_node)
        workflow.add_node("clarification", self._clarification_node)
        workflow.add_node("finalize", self._finalize_node)

        # Set entry point
        workflow.set_entry_point("classify")

        # Add conditional edges from classify
        workflow.add_conditional_edges(
            "classify",
            self._route,
            {
                "scheduling": "scheduling",
                "leave": "leave",
                "compliance": "compliance",
                "profile": "profile",
                "clarification": "clarification"
            }
        )

        # Add edges from agents to finalize
        workflow.add_edge("scheduling", "finalize")
        workflow.add_edge("leave", "finalize")
        workflow.add_edge("compliance", "finalize")
        workflow.add_edge("profile", "finalize")
        workflow.add_edge("clarification", "finalize")

        # Add edge from finalize to END (using the imported END constant)
        workflow.add_edge("finalize", END)

        return workflow.compile()

    async def _classify_node(self, state: OrchestratorState) -> OrchestratorState:
        stm = get_stm_context(state["session_id"], last_n_turns=3)
        ltm = get_ltm_facts(state["user_id"], min_significance=0.5)
        memory = self._format_memory(stm, ltm)
        state["memory_context"] = memory
        intent, conf = await self._classify_intent(state["user_input"], memory)
        state["intent"] = intent
        state["confidence"] = conf
        return state

    async def _classify_intent(self, text: str, memory: str) -> tuple:
        # 1. Greetings
        greetings = {"hi", "hello", "hey", "good morning", "good afternoon", "good evening"}
        lower = text.lower().strip()
        if lower in greetings or lower.startswith(("hi", "hello", "hey")):
            return "greeting", 1.0

        # 2. Profile questions
        profile_keywords = ["who am i", "my details", "my department", "my designation",
                           "what is my", "my role", "my user id", "my email", "my phone"]
        if any(kw in lower for kw in profile_keywords):
            return "profile", 0.95

        # 3. Keyword fallback
        txt = text.lower()
        if any(w in txt for w in ["schedule", "book", "arrange", "meeting", "appointment", "call", "online meeting", "physical meeting"]):
            return "scheduling", 0.95
        if any(w in txt for w in ["leave", "vacation", "time off", "sick", "half day", "emergency leave"]):
            return "leave", 0.95
        if any(w in txt for w in ["policy", "compliance", "rule", "regulation", "allowed", "can i", "is it allowed"]):
            return "compliance", 0.95

        # 4. LLM classification
        system = """Classify intent as 'scheduling', 'leave', 'compliance', 'profile', or 'clarification'. 
        Return ONLY valid JSON: {"intent": ..., "confidence": 0.0-1.0}"""
        user = f"Memory:\n{memory}\nUser: {text}"
        try:
            resp = await asyncio.to_thread(LLMConfig.get_llm_response, system, user)
            json_match = re.search(r'\{[^{}]*"intent"[^{}]*\}', resp, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return data.get("intent", "clarification"), data.get("confidence", 0.5)
            else:
                return "clarification", 0.5
        except Exception as e:
            print(f"[ERROR] LLM classification: {e}")
            return "clarification", 0.5

    def _route(self, state: OrchestratorState) -> Literal["scheduling","leave","compliance","profile","clarification"]:
        if state["intent"] == "greeting":
            return "clarification"
        if state["confidence"] < 0.7:
            return "clarification"
        return state["intent"]

    async def _scheduling_node(self, state: OrchestratorState) -> OrchestratorState:
        resp = await self.scheduling.process_request(
            state["user_id"], state["session_id"], state["user_input"], state["memory_context"]
        )
        state["response"] = resp
        state["routed_agent"] = "scheduling"
        return state

    async def _leave_node(self, state: OrchestratorState) -> OrchestratorState:
        resp = await self.leave.process_request(
            state["user_id"], state["session_id"], state["user_input"], state["memory_context"]
        )
        state["response"] = resp
        state["routed_agent"] = "leave"
        return state

    async def _compliance_node(self, state: OrchestratorState) -> OrchestratorState:
        resp = await self.compliance.process_request(
            state["user_id"], state["session_id"], state["user_input"], state["memory_context"]
        )
        state["response"] = resp
        state["routed_agent"] = "compliance"
        return state

    async def _profile_node(self, state: OrchestratorState) -> OrchestratorState:
        resp = await self.profile.process_request(
            state["user_id"], state["session_id"], state["user_input"], state["memory_context"]
        )
        state["response"] = resp
        state["routed_agent"] = "profile"
        return state

    async def _clarification_node(self, state: OrchestratorState) -> OrchestratorState:
        # Handle greeting explicitly
        if state["intent"] == "greeting":
            state["response"] = "Hello! I'm your HR assistant. I can help you with:\n- 📅 Schedule meetings\n- 🌴 Request leave and check balances\n- 📋 Answer policy questions\n- 👤 View your profile\n- ✏️ Cancel or modify requests\n\nWhat would you like to do?"
            state["routed_agent"] = "greeting"
            return state
        resp = await self.clarification.process_request(
            state["user_id"], state["session_id"], state["user_input"], state["memory_context"]
        )
        state["response"] = resp
        state["routed_agent"] = "clarification"
        return state

    async def _finalize_node(self, state: OrchestratorState) -> OrchestratorState:
        # Get correct turn count
        turn_idx = get_stm_turn_count(state["session_id"])
        add_stm_turn(state["session_id"], turn_idx, "user", state["user_input"])
        add_stm_turn(state["session_id"], turn_idx + 1, "agent", state["response"])

        # Clean old STM (keep last 50 turns)
        clear_old_stm(state["session_id"], keep_last=50)

        # Enhanced LTM significance scoring
        lower_input = state["user_input"].lower()
        score = 0.0
        fact_key = None
        fact_val = None

        # Detect recurring patterns
        if "prefer" in lower_input:
            score = 0.7
            fact_key = "preference"
            fact_val = state["user_input"]
        elif "department" in lower_input and "i am in" in lower_input:
            score = 0.9
            fact_key = "department"
            fact_val = state["user_input"]
        elif "designation" in lower_input:
            score = 0.9
            fact_key = "designation"
            fact_val = state["user_input"]

        if fact_key and fact_val:
            add_ltm_fact(state["user_id"], fact_key, fact_val, score, state["session_id"])

        set_session_state(state["session_id"], state["routed_agent"], None)
        return state

    def _format_memory(self, stm: list, ltm: list) -> str:
        stm_text = "\n".join([f"{t['role']}: {t['content']}" for t in stm])
        ltm_text = "\n".join([f"{f['fact_key']}: {f['fact_value']}" for f in ltm])
        return f"Recent conversation:\n{stm_text}\n\nKnown facts:\n{ltm_text}"

    async def process(self, user_id: str, session_id: str, user_input: str) -> dict:
        start = time.time()
        state = OrchestratorState(
            user_id=user_id,
            session_id=session_id,
            user_input=user_input,
            memory_context="",
            intent="",
            confidence=0.0,
            response="",
            routed_agent="",
            latency_ms=0,
            error=""
        )
        try:
            final_state = await self.graph.ainvoke(state)
            latency_ms = int((time.time() - start) * 1000)
            final_state["latency_ms"] = latency_ms
            log_audit(
                user_id=user_id,
                session_id=session_id,
                raw_input=user_input,
                intent=final_state["intent"],
                confidence=final_state["confidence"],
                routed_agent=final_state["routed_agent"],
                response=final_state["response"],
                latency_ms=latency_ms,
                error=None
            )
            return {
                "response": final_state["response"],
                "intent": final_state["intent"],
                "confidence": final_state["confidence"],
                "routed_agent": final_state["routed_agent"],
                "session_id": session_id
            }
        except Exception as e:
            error_msg = str(e)
            latency_ms = int((time.time() - start) * 1000)
            log_audit(user_id, session_id, user_input, "error", 0.0, "error", error_msg, latency_ms, error_msg)
            return {
                "response": "An internal error occurred. Please try again.",
                "intent": "error",
                "confidence": 0.0,
                "routed_agent": "error",
                "session_id": session_id
            }
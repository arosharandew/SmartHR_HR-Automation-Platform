"""
ClarificationAgent.py - Uses LLM to rephrase ambiguous user input and suggest valid intents.
"""

import asyncio
from Config.LLMConfig import LLMConfig

CAPABILITIES = """
I can help you with:

📅 **Schedule Management**
- "Schedule a meeting with John tomorrow at 2pm online"
- "Book a physical meeting with Sarah on Friday at 10am"
- "Show my upcoming meetings"
- "Cancel meeting ID 3"
- "Reschedule my meeting with Tom to Monday at 3pm"
- "Am I free on Thursday afternoon?"
- "Show all my meetings this week"

🌴 **Leave Management**
- "I need leave from 10/05/2026 to 14/05/2026"
- "How many vacation days do I have left?"
- "I need a half-day on Thursday morning"
- "Cancel my leave request"
- "Show my leave history"
- "I need emergency leave today"

📋 **Policy & Compliance**
- "What is the sick leave policy?"
- "How many consecutive leave days can I take?"
- "What are the half-day leave slots?"
- "What is the dress code?"
- "How do I report harassment?"
- "What are the public holidays this year?"

👤 **Profile & Info**
- "Who am I?"
- "What is my department?"
- "Show my user ID"
- "What is my designation?"

❓ **General Help**
- "What can you do?" - Show this menu
- "Help me book a meeting" - Step-by-step guidance
"""

class ClarificationAgent:
    async def process_request(self, user_id: str, session_id: str, user_input: str, memory_context: str = "") -> str:
        lower_input = user_input.lower().strip()

        # Capability query
        if lower_input in ["what can you do", "help", "capabilities", "what can i do", "show me what you can do", "how to use this"]:
            return f"Here's what I can help you with:\n{CAPABILITIES}"

        # Step-by-step guidance
        if "how do i" in lower_input or "show me how" in lower_input or "help me" in lower_input:
            if "meeting" in lower_input or "schedule" in lower_input:
                return "To schedule a meeting:\n1. Say 'Schedule a meeting with [person] on [date] at [time]'\n2. Specify if it's 'online' or 'physical'\n3. Example: 'Schedule a meeting with John tomorrow at 2pm online'"
            elif "leave" in lower_input:
                return "To request leave:\n1. Say 'I need leave from [start date] to [end date]'\n2. Example: 'I need leave from 10th May to 12th May'\n3. For half-day: 'I need a half-day on Thursday morning'"
            elif "balance" in lower_input:
                return "To check your leave balance, say: 'How many vacation days do I have left?'"
            else:
                return f"I can help you with:\n{CAPABILITIES}\nJust tell me what you'd like to do!"

        # Chitchat / small talk
        chitchat = {"how are you", "what's the weather", "tell me a joke", "good", "bad", "nice", "awesome"}
        if any(phrase in lower_input for phrase in chitchat):
            return "I'm your HR assistant! I specialize in helping with meetings, leave requests, and company policies. How can I assist you with your work today?"

        # Complaint / feedback detection
        complaint_keywords = ["complaint", "unhappy", "frustrated", "not fair", "unfair", "issue with", "problem with"]
        if any(kw in lower_input for kw in complaint_keywords):
            return "I'm sorry to hear that. Please raise your concern through the official grievance channel: hr-complaints@company.com or contact HR directly at extension 1234. All complaints are handled confidentially."

        # Greetings
        greetings = {"hi", "hello", "hey", "good morning", "good afternoon", "good evening"}
        if lower_input in greetings or lower_input.startswith(("hi", "hello", "hey")):
            return f"Hello! I'm your HR assistant. {CAPABILITIES.split(chr(10))[0]}"

        # Use LLM for other ambiguous inputs
        system_prompt = """
You are a helpful HR assistant. The user said something unclear. Your task is to:
1. Understand what they probably want (schedule meeting, request leave, check balance, cancel something, ask policy, profile info).
2. Respond with a friendly, helpful message that suggests the correct way to ask.

Be concise and helpful. Do not just say "I don't understand".
"""
        try:
            # Fixed: asyncio.to_thread (not async.io.to_thread)
            response = await asyncio.to_thread(LLMConfig.get_llm_response, system_prompt, user_input)
            return response
        except Exception as e:
            print(f"Clarification LLM error: {e}")
            return f"I'm not sure what you meant. Here's what I can help with:\n{CAPABILITIES}"
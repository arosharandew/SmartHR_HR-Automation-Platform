import asyncio
from Config.LLMConfig import LLMConfig
from Database.Helper import insert_compliance_query

# Full company policy text – REPLACE THIS with your actual policy document
POLICY_DOC = """
1. Leave Management Policies
- Maximum 21 leave days per year.
- Cannot take more than 10 consecutive leave days.
- Half-day slots: 8:00 AM – 2:00 PM (morning), 2:00 PM – 5:00 PM (evening)
- Sick leave requires medical certificate after 2 days.
- Emergency leave: maximum 5 days annually.

2. Working Hours
- Standard working hours: 8 hours per day, 40 hours per week.
- Morning shift: 8:00 AM – 4:00 PM
- Evening shift: 2:00 PM – 10:00 PM
- Night shift: 10:00 PM – 6:00 AM

3. Code of Conduct
- Respect all colleagues.
- Discrimination based on gender, race, religion is prohibited.
- Maintain confidentiality of company data.

4. Attendance Policy
- Late arrival: 3 times = warning, 5 times = HR notice, 8 times = salary deduction.
- Unauthorized absence for 3 consecutive days triggers disciplinary review.

5. Remote Work Policy
- Employees must maintain availability during working hours.
- VPN required for sensitive systems.

6. Data Privacy
- Employee data must remain confidential.
- Access follows role-based permissions.

7. Anti-Harassment
- Zero tolerance for harassment of any form.
- Report through HR portal or anonymous complaint form.
"""


class ComplianceAgent:
    async def process_request(self, user_id: str, session_id: str, user_input: str, memory_context: str = "") -> str:
        system_prompt = f"""
You are an HR compliance assistant. Answer the user's question strictly based on the following policy document.
If the answer is not in the document, say "I cannot find that in the policy. Please contact HR."
Be concise and helpful.

Policy document:
{POLICY_DOC}

User question: {user_input}
"""
        try:
            # Use asyncio.to_thread to avoid blocking the event loop
            answer = await asyncio.to_thread(LLMConfig.get_llm_response, system_prompt, user_input)
        except Exception as e:
            answer = f"Sorry, I couldn't fetch policy information at this time. Error: {e}"

        # Store in database for history (optional, can be async)
        try:
            insert_compliance_query(user_id, user_input, answer)
        except:
            pass

        return answer
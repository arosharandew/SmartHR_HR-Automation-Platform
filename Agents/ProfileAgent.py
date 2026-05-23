"""
ProfileAgent.py - Handles user profile queries (department, designation, user_id, etc.)
"""

from Database.Helper import get_user


class ProfileAgent:
    async def process_request(self, user_id: str, session_id: str, user_input: str, memory_context: str = "") -> str:
        user = get_user(user_id)
        if not user:
            return "User not found."

        lower_input = user_input.lower()

        if "who am i" in lower_input or "my details" in lower_input:
            return f"📋 Your Profile:\n- Name: {user['name']}\n- User ID: {user['user_id']}\n- Email: {user['email']}\n- Phone: {user['phone']}\n- NIC: {user['nic']}\n- Designation: {user['designation']}\n- Department: {user['department']}"

        if "department" in lower_input:
            return f"Your department is: {user['department']}"

        if "designation" in lower_input or "role" in lower_input:
            return f"Your designation is: {user['designation']}"

        if "user id" in lower_input or "id" in lower_input:
            return f"Your user ID is: {user['user_id']}"

        if "email" in lower_input:
            return f"Your email is: {user['email']}"

        if "phone" in lower_input:
            return f"Your phone number is: {user['phone']}"

        if "nic" in lower_input:
            return f"Your NIC is: {user['nic']}"

        return f"Your profile info: Name: {user['name']}, Designation: {user['designation']}, Department: {user['department']}"
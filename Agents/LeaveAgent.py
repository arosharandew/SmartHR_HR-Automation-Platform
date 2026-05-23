"""
LeaveAgent.py - Handles leave requests, balances, and policy compliance.
Enforces: max 21 days/year, max 10 consecutive days, half-day slots.
Supports multi‑turn conversation, pending requests, and cancellation.
"""

import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from Config.LLMConfig import LLMConfig
from Database.Helper import (
    insert_leave_request, get_user_leave_requests, update_leave_status,
    get_or_create_leave_balance, update_leave_balance
)

class LeaveAgent:
    def __init__(self):
        self.pending_requests: Dict[str, Dict] = {}      # for creation
        self.pending_cancellations: Dict[str, Dict] = {}  # for cancellation

    async def process_request(self, user_id: str, session_id: str, user_input: str, memory_context: str = "") -> str:
        # Resume pending flows
        if session_id in self.pending_requests:
            return self._continue_leave_request(user_id, session_id, user_input)
        if session_id in self.pending_cancellations:
            return self._continue_cancel_leave(user_id, session_id, user_input)

        intent = self._classify_intent(user_input)
        if intent == "request_leave":
            return self._start_leave_request(user_id, session_id, user_input)
        elif intent == "check_balance":
            return self._check_balance(user_id)
        elif intent == "cancel_leave":
            return self._start_cancel_leave(user_id, session_id, user_input)
        else:
            return "You can ask for leave (e.g., 'I need leave from 10/05/2026 to 12/05/2026'), check your balance, or cancel a request."

    # ---------- Intent classification ----------
    def _classify_intent(self, text: str) -> str:
        txt = text.lower()
        if any(w in txt for w in ["cancel", "remove", "delete"]):
            return "cancel_leave"
        if any(w in txt for w in ["balance", "remaining", "left", "how many"]):
            return "check_balance"
        if any(w in txt for w in ["request", "apply", "take", "need", "want", "get a leave"]):
            return "request_leave"
        return "request_leave"

    # ---------- Check balance ----------
    def _check_balance(self, user_id: str) -> str:
        bal = get_or_create_leave_balance(user_id)
        used = self._get_used_days(user_id)
        remaining = bal["vacation_days"] - used
        return f"Annual leave: {remaining:.1f} days remaining (used {used:.1f} of {bal['vacation_days']}). Sick days: {bal['sick_days']}."

    def _get_used_days(self, user_id: str) -> float:
        requests = get_user_leave_requests(user_id)
        used = 0.0
        for r in requests:
            if r["status"] == "approved":
                start = datetime.strptime(r["start_date"], "%Y-%m-%d")
                end = datetime.strptime(r["end_date"], "%Y-%m-%d")
                days = (end - start).days + 1
                used += days
        return used

    # ---------- Cancel leave flow ----------
    def _start_cancel_leave(self, user_id: str, session_id: str, user_input: str) -> str:
        """Start cancel flow: show existing leaves and ask for ID."""
        requests = get_user_leave_requests(user_id)
        approved = [r for r in requests if r["status"] == "approved"]
        pending = [r for r in requests if r["status"] == "pending"]

        if not approved and not pending:
            return "You have no leave requests to cancel."

        resp = "Your leave requests:\n"
        for r in approved + pending:
            resp += f"ID {r['id']}: {r['start_date']} to {r['end_date']} ({r['leave_type']}) - {r['status']}\n"
        resp += "\nPlease provide the ID you want to cancel (e.g., 'cancel 2' or just the number)."

        self.pending_cancellations[session_id] = {"user_id": user_id, "step": "awaiting_id"}
        return resp

    def _continue_cancel_leave(self, user_id: str, session_id: str, user_input: str) -> str:
        """Handle reply with meeting ID."""
        # Extract ID from input
        id_match = re.search(r"\b(\d+)\b", user_input)
        if not id_match:
            return "Please provide the numeric ID of the leave request you want to cancel."

        request_id = int(id_match.group(1))
        requests = get_user_leave_requests(user_id)
        target = None
        for r in requests:
            if r["id"] == request_id:
                target = r
                break

        if not target:
            return f"Leave request ID {request_id} not found."

        # Cancel (delete or reject)
        update_leave_status(request_id, "rejected")
        # If approved, also add back the days to balance
        if target["status"] == "approved":
            start = datetime.strptime(target["start_date"], "%Y-%m-%d")
            end = datetime.strptime(target["end_date"], "%Y-%m-%d")
            days = (end - start).days + 1
            bal = get_or_create_leave_balance(user_id)
            update_leave_balance(user_id, vacation_days=bal["vacation_days"] + days)

        del self.pending_cancellations[session_id]
        return f"✅ Leave request ID {request_id} has been cancelled."

    # ---------- Leave request flow (multi‑turn) ----------
    def _start_leave_request(self, user_id: str, session_id: str, user_input: str) -> str:
        details = self._extract_leave_details(user_input)
        start = details.get("start_date")
        end = details.get("end_date")
        leave_type = details.get("leave_type", "vacation")
        half_day = details.get("half_day")

        if not start:
            self.pending_requests[session_id] = {
                "user_id": user_id,
                "step": "awaiting_start_date",
                "original_input": user_input,
                "leave_type": leave_type,
                "half_day": half_day
            }
            return "Please provide the start date (e.g., 10/05/2026 or '10th of may')."

        if not end:
            end = start
            self.pending_requests[session_id] = {
                "user_id": user_id,
                "step": "awaiting_end_date",
                "original_input": user_input,
                "start_date": start,
                "leave_type": leave_type,
                "half_day": half_day
            }
            return "Please provide the end date (or say 'same day' if it's a single day)."

        return self._process_leave_request(user_id, start, end, leave_type, half_day, user_input)

    def _continue_leave_request(self, user_id: str, session_id: str, user_input: str) -> str:
        pending = self.pending_requests[session_id]
        step = pending.get("step")

        if step == "awaiting_start_date":
            start = self._extract_date_from_text(user_input)
            if not start:
                return "Please give a valid start date in DD/MM/YYYY format (e.g., 10/05/2026) or say '10th may'."
            pending["step"] = "awaiting_end_date"
            pending["start_date"] = start
            return "Thanks. Now please provide the end date (or say 'same day' if it's a single day)."

        elif step == "awaiting_end_date":
            end_input = user_input.strip().lower()
            start = pending["start_date"]
            leave_type = pending.get("leave_type", "vacation")
            half_day = pending.get("half_day")

            if end_input == "same day":
                end = start
            else:
                end = self._extract_date_from_text(user_input)
                if not end:
                    return "Please provide a valid end date in DD/MM/YYYY format or say 'same day'."

            del self.pending_requests[session_id]
            return self._process_leave_request(user_id, start, end, leave_type, half_day, pending.get("original_input", "") + " " + user_input)

        return "Something went wrong. Please start over."

    def _extract_leave_details(self, text: str) -> Dict[str, Any]:
        system_prompt = """
        Extract leave details from the user's message. Return a JSON object with:
        - "start_date": DD/MM/YYYY, or null if not found
        - "end_date": DD/MM/YYYY, or null if not found (if single day, same as start)
        - "leave_type": "vacation" or "sick" (default "vacation")
        - "half_day": "morning", "evening", or null
        """
        response = self._safe_llm_response(system_prompt, text)
        data = self._extract_json(response)
        if not data:
            data = self._fallback_extract_leave(text)
        if data.get("start_date"):
            resolved = self._resolve_date(data["start_date"])
            if resolved:
                data["start_date"] = resolved
        if data.get("end_date") and data["end_date"] != data.get("start_date"):
            resolved = self._resolve_date(data["end_date"])
            if resolved:
                data["end_date"] = resolved
        return data

    def _fallback_extract_leave(self, text: str) -> Dict[str, Any]:
        result = {"start_date": None, "end_date": None, "leave_type": "vacation", "half_day": None}
        date_patterns = [
            r"(\d{2}/\d{2}/\d{4})",
            r"(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([a-z]+)(?:\s+(\d{4}))?"
        ]
        dates = []
        for pat in date_patterns:
            matches = re.findall(pat, text, re.I)
            for m in matches:
                if isinstance(m, tuple):
                    if len(m) == 3:
                        day, mon, year = m
                        if not year:
                            year = str(datetime.now().year)
                        month_map = {"jan":"01","feb":"02","mar":"03","apr":"04","may":"05","jun":"06",
                                    "jul":"07","aug":"08","sep":"09","oct":"10","nov":"11","dec":"12"}
                        mon_num = month_map.get(mon[:3].lower(), "01")
                        dates.append(f"{int(day):02d}/{mon_num}/{year}")
                else:
                    dates.append(m)
        if dates:
            result["start_date"] = dates[0]
            if len(dates) > 1:
                result["end_date"] = dates[1]
        if "morning" in text.lower():
            result["half_day"] = "morning"
        elif "evening" in text.lower() or "afternoon" in text.lower():
            result["half_day"] = "evening"
        return result

    def _resolve_date(self, date_str: str) -> Optional[str]:
        if not date_str:
            return None
        date_str = date_str.strip().lower()
        today = datetime.now().date()
        if date_str == "today":
            return today.strftime("%d/%m/%Y")
        if date_str == "tomorrow":
            return (today + timedelta(days=1)).strftime("%d/%m/%Y")
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for idx, day in enumerate(days):
            if date_str == f"next {day}":
                target = idx
                current = today.weekday()
                days_ahead = (target - current) % 7
                if days_ahead == 0:
                    days_ahead = 7
                return (today + timedelta(days=days_ahead)).strftime("%d/%m/%Y")
        match = re.match(r"(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(\w+)(?:\s+(\d{4}))?", date_str, re.I)
        if match:
            day = int(match.group(1))
            month_name = match.group(2)[:3].lower()
            year = match.group(3) if match.group(3) else str(today.year)
            months = {"jan":1, "feb":2, "mar":3, "apr":4, "may":5, "jun":6,
                      "jul":7, "aug":8, "sep":9, "oct":10, "nov":11, "dec":12}
            month = months.get(month_name)
            if month:
                try:
                    date_obj = datetime(int(year), month, day)
                    return date_obj.strftime("%d/%m/%Y")
                except:
                    pass
        return None

    def _extract_date_from_text(self, text: str) -> Optional[str]:
        m = re.search(r"(\d{2}/\d{2}/\d{4})", text)
        if m:
            return m.group(1)
        resolved = self._resolve_date(text.strip())
        return resolved

    def _process_leave_request(self, user_id: str, start_str: str, end_str: str,
                               leave_type: str, half_day: Optional[str], user_prompt: str) -> str:
        import sqlite3
        from Database.Database import get_db_connection

        try:
            start = datetime.strptime(start_str, "%d/%m/%Y")
            end = datetime.strptime(end_str, "%d/%m/%Y")
        except:
            return "Invalid date format. Please use DD/MM/YYYY."

        if start > end:
            return "Start date cannot be after end date."

        days = (end - start).days + 1
        if half_day:
            days = 0.5

        if days > 10:
            return "You cannot request more than 10 consecutive leave days."

        # Use a single connection for transaction
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Get current balance within transaction
            cursor.execute("SELECT vacation_days FROM leave_balances WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if not row:
                cursor.execute("INSERT INTO leave_balances (user_id, vacation_days, sick_days) VALUES (?, 21.0, 10.0)",
                               (user_id,))
                vacation_balance = 21.0
            else:
                vacation_balance = row["vacation_days"]

            # Get used days
            cursor.execute("""
                           SELECT SUM(julianday(end_date) - julianday(start_date) + 1) as used
                           FROM leave_requests
                           WHERE user_id = ?
                             AND status = 'approved'
                           """, (user_id,))
            used_row = cursor.fetchone()
            used = used_row["used"] if used_row and used_row["used"] else 0.0

            if used + days > vacation_balance:
                conn.close()
                return f"Your request exceeds your remaining balance ({vacation_balance - used:.1f} days left)."

            # Overlap check
            cursor.execute("""
                           SELECT start_date, end_date
                           FROM leave_requests
                           WHERE user_id = ?
                             AND status = 'approved'
                             AND date (start_date) <= date (?)
                             AND date (end_date) >= date (?)
                           """, (user_id, end_str, start_str))
            overlap = cursor.fetchone()
            if overlap:
                conn.close()
                return "Your requested dates overlap with an already approved leave."

            # Insert request
            db_start = start.strftime("%Y-%m-%d")
            db_end = end.strftime("%Y-%m-%d")
            cursor.execute("""
                           INSERT INTO leave_requests (user_id, start_date, end_date, leave_type, user_prompt, status)
                           VALUES (?, ?, ?, ?, ?, 'approved')
                           """, (user_id, db_start, db_end, leave_type, user_prompt))

            # Update balance
            new_balance = vacation_balance - days
            cursor.execute("UPDATE leave_balances SET vacation_days = ? WHERE user_id = ?", (new_balance, user_id))

            conn.commit()
            conn.close()

            half_info = f" (half-day, {half_day})" if half_day else ""
            return f"✅ Leave approved for {days} day(s){half_info} from {start_str} to {end_str}. Remaining vacation: {new_balance:.1f} days."

        except Exception as e:
            conn.rollback()
            conn.close()
            return f"Database error: {e}"

    def _safe_llm_response(self, system: str, user: str) -> str:
        try:
            return LLMConfig.get_llm_response(system, user)
        except:
            return ""

    def _extract_json(self, response: str) -> dict:
        if not response:
            return {}
        cleaned = re.sub(r"```json\n?|```", "", response.strip())
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1:
            cleaned = cleaned[start:end+1]
        try:
            import json
            return json.loads(cleaned)
        except:
            return {}
"""
SchedulingAgent.py - Full CRUD for meetings with natural language.
Supports: creation, query, cancellation (by attendee/date/id), modification.
Uses LLM for intent and extraction with robust JSON parsing.
"""

import re
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from Config.LLMConfig import LLMConfig
from Database.Helper import (
    insert_schedule,
    get_meetings_by_date,
    get_meetings_by_type,
    get_upcoming_meetings,
    get_schedule_by_id,
    update_schedule,
    delete_schedule,
    find_meetings_by_attendee
)

class SchedulingAgent:
    def __init__(self):
        self.pending_meetings: Dict[str, Dict] = {}          # for meeting creation
        self.pending_modifications: Dict[str, Dict] = {}      # for modification
        self.pending_cancellations: Dict[str, Dict] = {}      # for cancel flow

    # ---------- MAIN ENTRY ----------
    async def process_request(self, user_id: str, session_id: str, user_input: str, memory_context: str = "") -> str:
        # Resume pending flows
        if session_id in self.pending_meetings:
            return self._continue_meeting_creation(user_id, session_id, user_input)
        if session_id in self.pending_modifications:
            return self._continue_meeting_modification(user_id, session_id, user_input)
        if session_id in self.pending_cancellations:
            return self._continue_meeting_cancellation(user_id, session_id, user_input)

        intent = self._classify_intent(user_input)
        if intent == "create_meeting":
            return self._start_meeting_creation(user_id, session_id, user_input)
        elif intent == "query_meetings":
            return self._answer_meeting_query(user_id, user_input)
        elif intent == "cancel_meeting":
            return self._cancel_meeting(user_id, session_id, user_input)
        elif intent == "modify_meeting":
            return self._start_meeting_modification(user_id, session_id, user_input)
        else:
            return "I'm not sure how to help. You can schedule, cancel, change, or ask about meetings."

    # ---------- INTENT CLASSIFICATION (with fallback) ----------
    def _classify_intent(self, user_input: str) -> str:
        system_prompt = """
        Classify the user's request into one of these intents:
        - "create_meeting" : schedule a new meeting
        - "query_meetings" : ask about existing meetings
        - "cancel_meeting" : delete/remove a meeting
        - "modify_meeting" : change details of a meeting

        Return ONLY the intent word, nothing else.
        """
        try:
            response = self._safe_llm_response(system_prompt, user_input)
            intent = response.strip().lower()
            if intent in ["create_meeting", "query_meetings", "cancel_meeting", "modify_meeting"]:
                return intent
        except:
            pass
        # Fallback keyword matching
        txt = user_input.lower()
        if any(w in txt for w in ["cancel", "remove", "delete"]):
            return "cancel_meeting"
        if any(w in txt for w in ["change", "update", "modify", "reschedule", "move"]):
            return "modify_meeting"
        if any(w in txt for w in ["schedule", "book", "arrange", "create"]):
            return "create_meeting"
        return "query_meetings"

    # ---------- SAFE LLM RESPONSE (handles empty/JSON errors) ----------
    def _safe_llm_response(self, system_prompt: str, user_prompt: str) -> str:
        """Get LLM response and return raw text, fallback to empty string on error."""
        try:
            return LLMConfig.get_llm_response(system_prompt, user_prompt)
        except Exception as e:
            print(f"LLM call failed: {e}")
            return ""

    # ---------- DATE RESOLUTION ----------
    def _convert_natural_date_to_ddmmyy(self, date_str: str) -> Optional[str]:
        """Convert natural language dates like 'May 22nd', '22nd of May' to DD/MM/YYYY."""
        if not date_str:
            return None

        date_str = date_str.strip()
        today = datetime.now().date()

        # Try to parse "May 22nd", "22nd May", "22nd of May"
        patterns = [
            r'(\w+)\s+(\d{1,2})(?:st|nd|rd|th)?',  # "May 22"
            r'(\d{1,2})(?:st|nd|rd|th)?\s+of\s+(\w+)',  # "22nd of May"
            r'(\d{1,2})(?:st|nd|rd|th)?\s+(\w+)',  # "22nd May"
        ]

        months = {
            "january": 1, "jan": 1,
            "february": 2, "feb": 2,
            "march": 3, "mar": 3,
            "april": 4, "apr": 4,
            "may": 5,
            "june": 6, "jun": 6,
            "july": 7, "jul": 7,
            "august": 8, "aug": 8,
            "september": 9, "sep": 9,
            "october": 10, "oct": 10,
            "november": 11, "nov": 11,
            "december": 12, "dec": 12
        }

        for pattern in patterns:
            match = re.search(pattern, date_str, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) == 2:
                    # Check which is month and which is day
                    first, second = groups[0].lower(), groups[1].lower()
                    if first in months:
                        month = months[first]
                        day = int(second)
                    elif second in months:
                        month = months[second]
                        day = int(first)
                    else:
                        continue

                    # Assume current year if not specified
                    year = today.year
                    # If the date is in the past, assume next year (e.g., "May 22" when today is June)
                    try:
                        date_obj = datetime(year, month, day)
                        if date_obj < today:
                            date_obj = datetime(year + 1, month, day)
                        return date_obj.strftime("%d/%m/%Y")
                    except:
                        pass
        return None
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
            if date_str == day:
                target = idx
                current = today.weekday()
                days_ahead = (target - current) % 7
                if days_ahead == 0:
                    days_ahead = 7
                return (today + timedelta(days=days_ahead)).strftime("%d/%m/%Y")

        # "23rd of may" etc.
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

    # ---------- JSON EXTRACTION WITH CLEANING ----------
    def _extract_json(self, response_text: str) -> dict:
        if not response_text:
            return {}
        cleaned = re.sub(r"```json\s*|\s*```", "", response_text, flags=re.I).strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1:
            cleaned = cleaned[start:end+1]
        try:
            return json.loads(cleaned)
        except:
            print(f"JSON parse error: {cleaned[:200]}")
            return {}

    # ---------- MEETING CREATION ----------
    def _start_meeting_creation(self, user_id: str, session_id: str, user_input: str) -> str:
        extracted = self._extract_meeting_details(user_input)
        required = ["date", "time", "schedule_type", "with_whom"]
        missing = [f for f in required if not extracted.get(f)]
        if missing:
            self.pending_meetings[session_id] = {
                "user_id": user_id,
                "user_prompt": user_input,
                "extracted": extracted,
                "missing": missing
            }
            return self._ask_for_missing_fields(missing)
        return self._create_meeting_record(user_id, user_input, extracted)

    def _extract_meeting_details(self, text: str) -> Dict[str, Any]:
        system_prompt = """
        Extract meeting details from the user's message. Return a JSON object with keys:
        "date": a date in DD/MM/YYYY format, or a relative term like "next Monday", "tomorrow", "friday", "23rd of may".
        "time": a time in HH:MM AM/PM format (e.g., "10:00 AM", "2:30 PM").
        "schedule_type": either "online" or "physical".
        "with_whom": the name of the person or department.

        If a field is not mentioned, use null.
        ONLY return the JSON object, no other text.
        """
        response = self._safe_llm_response(system_prompt, text)
        data = self._extract_json(response)
        if not data:
            data = self._fallback_extract(text)
        if data.get("date"):
            resolved = self._resolve_date(data["date"])
            if resolved:
                data["date"] = resolved
        return data

    def _fallback_extract(self, text: str) -> Dict[str, Any]:
        result = {"date": None, "time": None, "schedule_type": None, "with_whom": None}
        # Date
        ddmmyy = re.search(r"(\d{2}/\d{2}/\d{4})", text)
        if ddmmyy:
            result["date"] = ddmmyy.group(1)
        else:
            m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([a-z]+)(?:\s+(\d{4}))?", text, re.I)
            if m:
                day, mon, year = m.group(1), m.group(2), m.group(3) or str(datetime.now().year)
                month_map = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
                mon_num = month_map.get(mon[:3].lower())
                if mon_num:
                    result["date"] = f"{int(day):02d}/{mon_num:02d}/{year}"
            else:
                for day in ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]:
                    if day in text.lower():
                        result["date"] = f"next {day}" if "next" in text.lower() else day
                        break
        # Time
        t = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", text, re.I)
        if t:
            hour = int(t.group(1))
            minute = t.group(2) or "00"
            ampm = t.group(3).lower()
            hour12 = hour % 12
            if ampm == "pm" and hour != 12:
                hour12 += 12
            result["time"] = f"{hour12:02d}:{minute} {ampm.upper()}"
        # Type
        if "online" in text.lower():
            result["schedule_type"] = "online"
        elif "physical" in text.lower():
            result["schedule_type"] = "physical"
        # Attendee
        w = re.search(r"with\s+([A-Za-z0-9\s]+?)(?:\s+(?:online|physical|at|on|$))", text, re.I)
        if w:
            result["with_whom"] = w.group(1).strip()
        return result

    def _ask_for_missing_fields(self, missing: List[str]) -> str:
        field_names = {
            "date": "date (e.g., 23/05/2026 or next Friday)",
            "time": "time (e.g., 10:00 AM)",
            "schedule_type": "type (online or physical)",
            "with_whom": "who the meeting is with"
        }
        names = [field_names[f] for f in missing]
        if len(names) == 1:
            return f"Please provide the {names[0]}."
        return f"Please provide: {', '.join(names)}."

    def _continue_meeting_creation(self, user_id: str, session_id: str, user_input: str) -> str:
        pending = self.pending_meetings[session_id]
        missing = pending["missing"]
        extracted = pending["extracted"]
        new_details = self._extract_meeting_details(user_input)

        for f in missing:
            if new_details.get(f):
                extracted[f] = new_details[f]

        still_missing = [f for f in missing if not extracted.get(f)]
        if still_missing:
            pending["missing"] = still_missing
            pending["extracted"] = extracted
            return self._ask_for_missing_fields(still_missing)
        else:
            full_prompt = pending["user_prompt"] + " " + user_input
            del self.pending_meetings[session_id]
            return self._create_meeting_record(user_id, full_prompt, extracted)

    def _create_meeting_record(self, user_id: str, user_prompt: str, details: Dict) -> str:
        date_str = details.get("date")
        if not date_str:
            return "I still need the date. Please give a specific date like 23/05/2026 or 'next Friday'."
        try:
            date_obj = datetime.strptime(date_str, "%d/%m/%Y")
            db_date = date_obj.strftime("%Y-%m-%d")
            day_of_week = date_obj.strftime("%A")
        except:
            return f"Could not understand the date '{date_str}'. Use DD/MM/YYYY or 'next Friday'."

        time_str = details.get("time")
        if not time_str:
            return "I also need the time, like 2:30 PM."
        if not re.match(r"\d{1,2}:\d{2}\s?(AM|PM)", time_str, re.I):
            return "Please provide time in format like '10:00 AM'."
        time_str = re.sub(r"(\d+:\d+)\s?(AM|PM)", r"\1 \2", time_str, flags=re.I).upper()

        s_type = details.get("schedule_type", "").lower()
        if s_type not in ["online", "physical"]:
            return "Please say if the meeting is online or physical."

        with_whom = details.get("with_whom")
        if not with_whom:
            return "Who is this meeting with?"

        try:
            new_id = insert_schedule(user_id, db_date, time_str, day_of_week,
                                     s_type, user_prompt, with_whom)
            return f"✅ Meeting scheduled! {date_str} at {time_str} with {with_whom} (ID: {new_id})"
        except Exception as e:
            return f"Database error: {e}"

    # ---------- MEETING QUERIES ----------
    def _answer_meeting_query(self, user_id: str, user_input: str) -> str:
        """Answer natural language questions about existing meetings."""
        interpretation = self._interpret_meeting_query(user_input)
        query_type = interpretation.get("type", "unknown")

        if query_type == "list_by_date":
            date_str = interpretation.get("date")
            if not date_str:
                return "Which date are you asking about? Please specify (e.g., '25/05/2026' or 'May 22nd')."

            # Try to resolve relative dates
            resolved = self._resolve_date(date_str)
            if not resolved:
                # Try natural date conversion
                resolved = self._convert_natural_date_to_ddmmyy(date_str)

            if not resolved:
                return f"I didn't understand the date '{date_str}'. Please use DD/MM/YYYY, 'tomorrow', or say 'May 22nd'."

            try:
                db_date = datetime.strptime(resolved, "%d/%m/%Y").strftime("%Y-%m-%d")
                meetings = get_meetings_by_date(user_id, db_date)
                if not meetings:
                    return f"No meetings on {resolved}."
                response = f"Meetings on {resolved}:\n"
                for m in meetings:
                    response += f"- {m['time']} - {m['schedule_type']} with {m['with_whom']} (ID: {m['id']})\n"
                return response
            except Exception as e:
                return f"Sorry, couldn't process date: {e}"

        elif query_type == "list_by_type":
            mtype = interpretation.get("schedule_type")
            if mtype not in ["online", "physical"]:
                return "Specify 'online' or 'physical'."
            meetings = get_meetings_by_type(user_id, mtype)
            if not meetings:
                return f"No {mtype} meetings."
            response = f"Your {mtype} meetings:\n"
            for m in meetings:
                response += f"- {m['date']} at {m['time']} with {m['with_whom']} (ID: {m['id']})\n"
            return response

        else:
            upcoming = get_upcoming_meetings(user_id, limit=5)
            if not upcoming:
                return "No upcoming meetings. Schedule one?"
            response = "Your upcoming meetings:\n"
            for m in upcoming:
                response += f"- {m['date']} at {m['time']} - {m['schedule_type']} with {m['with_whom']} (ID: {m['id']})\n"
            return response

    def _interpret_meeting_query(self, user_input: str) -> Dict[str, Any]:
        """Use LLM to extract query type and parameters with robust JSON extraction."""
        system_prompt = """
        Interpret the user's query about their meetings. Return a JSON object with:
        - "type": one of "list_by_date", "list_by_type", "check_time", or "unknown"
        - "date": if asking about a specific date, extract as DD/MM/YYYY
        - "schedule_type": "online" or "physical" if specified

        Examples:
        User: "Do I have any meetings on Monday 25th May?" -> {"type": "list_by_date", "date": "25/05/2026"}
        User: "Show my online meetings" -> {"type": "list_by_type", "schedule_type": "online"}
        User: "What meetings are scheduled for tomorrow?" -> {"type": "list_by_date", "date": "tomorrow"}

        ONLY return the JSON object. No extra text, no explanation, no markdown.
        """
        try:
            response = self._safe_llm_response(system_prompt, user_input)
            # Robust JSON extraction
            json_match = re.search(r'\{[^{}]*"type"[^{}]*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return {"type": "unknown"}
        except Exception as e:
            print(f"Query interpretation error: {e}")
            return {"type": "unknown"}

    # ---------- CANCEL MEETING (with pending state) ----------
    def _cancel_meeting(self, user_id: str, session_id: str, user_input: str) -> str:
        # Try ID first
        meeting_id = self._extract_meeting_id(user_input)
        if meeting_id:
            meeting = get_schedule_by_id(meeting_id)
            if meeting and meeting["user_id"] == user_id:
                if delete_schedule(meeting_id):
                    return f"✅ Meeting ID {meeting_id} has been cancelled."
                else:
                    return "Could not delete meeting."
            else:
                return "Meeting not found or you don't have permission."

        # Try to extract attendee name
        attendee = self._extract_attendee_name(user_input)
        if attendee:
            return self._cancel_by_attendee(user_id, attendee, user_input)

        # No ID and no name – ask for name and store pending state
        self.pending_cancellations[session_id] = {"user_id": user_id}
        return "Who is the meeting with? Please give me the attendee name."

    def _continue_meeting_cancellation(self, user_id: str, session_id: str, user_input: str) -> str:
        # User replied with a bare name (or something)
        attendee = self._extract_attendee_name(user_input)
        if not attendee:
            del self.pending_cancellations[session_id]
            return "I didn't catch the name. Please say 'cancel meeting with John' or give me the meeting ID."
        del self.pending_cancellations[session_id]
        return self._cancel_by_attendee(user_id, attendee, user_input)

    def _cancel_by_attendee(self, user_id: str, attendee: str, original_text: str) -> str:
        date_str = self._extract_date_from_text(original_text)
        db_date = None
        if date_str:
            resolved = self._resolve_date(date_str)
            if resolved:
                try:
                    db_date = datetime.strptime(resolved, "%d/%m/%Y").strftime("%Y-%m-%d")
                except:
                    pass

        meetings = find_meetings_by_attendee(user_id, attendee, db_date)
        if not meetings:
            return f"No meeting found with '{attendee}'."
        if len(meetings) > 1:
            resp = f"Found multiple meetings with '{attendee}':\n"
            for m in meetings:
                resp += f"- {m['date']} at {m['time']} (ID: {m['id']})\n"
            resp += "Please say which meeting ID to cancel, e.g. 'cancel ID 3'."
            return resp
        meeting = meetings[0]
        if delete_schedule(meeting["id"]):
            return f"✅ Cancelled meeting with {meeting['with_whom']} on {meeting['date']} at {meeting['time']}."
        return "Could not delete meeting."

    def _extract_meeting_id(self, text: str) -> Optional[int]:
        m = re.search(r"\b(?:id\s*)?(\d+)\b", text, re.I)
        return int(m.group(1)) if m else None

    def _extract_attendee_name(self, text: str) -> Optional[str]:
        """
        Extract a person's name. Handles:
        - "with Mr Kumara"
        - "cancel meeting Kumara"
        - "Kumara" (bare)
        - "Mr Kumara"
        """
        # Pattern 1: "with [Name]"
        m = re.search(r"with\s+((?:Mr\.?|Ms\.?|Mrs\.?|Dr\.?)?\s*[A-Za-z][A-Za-z\s]*?)(?:\s+(?:online|physical|at|on)\b|$)", text, re.I)
        if m:
            name = m.group(1).strip()
            if len(name) > 1:
                return name

        # Pattern 2: "cancel meeting [Name]"
        m = re.search(r"(?:cancel|remove|delete)\s+(?:the\s+)?meeting\s+(?:with\s+)?((?:Mr\.?|Ms\.?|Mrs\.?|Dr\.?)?\s*[A-Za-z][A-Za-z\s]*?)(?:\s+(?:on|at)\b|$)", text, re.I)
        if m:
            name = m.group(1).strip()
            if len(name) > 1:
                return name

        # Pattern 3: "cancel [Name]" (after intent classification, the word "cancel" may be present)
        m = re.search(r"cancel\s+((?:Mr\.?|Ms\.?|Mrs\.?|Dr\.?)?\s*[A-Za-z][A-Za-z\s]{1,40})", text, re.I)
        if m:
            name = m.group(1).strip()
            if len(name) > 1:
                return name

        # Pattern 4: bare name (single word or two words, all letters, not a command)
        stripped = text.strip()
        skip = {"okay", "yes", "no", "exit", "quit", "help", "cancel", "meeting", "meetings",
                "change", "update", "modify", "show", "list", "schedule", "book", "arrange"}
        if re.match(r"^(?:Mr\.?|Ms\.?|Mrs\.?|Dr\.?)?\s*[A-Za-z][A-Za-z\s]{1,40}$", stripped):
            if stripped.lower() not in skip:
                return stripped

        return None

    def _extract_date_from_text(self, text: str) -> Optional[str]:
        m = re.search(r"on\s+([A-Za-z0-9/\s]+?)(?:\s+(?:with|at|$))", text, re.I)
        if m:
            return m.group(1).strip()
        return None

    # ---------- MEETING MODIFICATION ----------
    def _start_meeting_modification(self, user_id: str, session_id: str, user_input: str) -> str:
        meeting_id = self._extract_meeting_id(user_input)
        meeting = None

        if meeting_id:
            meeting = get_schedule_by_id(meeting_id)
            if not meeting or meeting["user_id"] != user_id:
                return "Meeting not found or you don't have permission."
        else:
            attendee = self._extract_attendee_name(user_input)
            if attendee:
                matches = find_meetings_by_attendee(user_id, attendee)
                if not matches:
                    return f"No meeting found with '{attendee}'. Use 'show my meetings' to see IDs."
                if len(matches) > 1:
                    resp = f"Found multiple meetings with '{attendee}':\n"
                    for m in matches:
                        resp += f"- {m['date']} at {m['time']} (ID: {m['id']})\n"
                    resp += "Which meeting ID would you like to change?"
                    self.pending_modifications[session_id] = {
                        "user_id": user_id, "step": "awaiting_id", "original_input": user_input
                    }
                    return resp
                meeting = matches[0]
            else:
                self.pending_modifications[session_id] = {
                    "user_id": user_id, "step": "awaiting_id", "original_input": user_input
                }
                return "Which meeting would you like to change? Please give me the meeting ID or attendee name."

        changes = self._extract_changes(user_input)
        if not changes:
            self.pending_modifications[session_id] = {
                "user_id": user_id, "step": "awaiting_changes", "meeting_id": meeting["id"]
            }
            return (f"What would you like to change about the meeting on {meeting['date']} "
                    f"at {meeting['time']} with {meeting['with_whom']}?\n"
                    "Example: 'change time to 3 PM' or 'reschedule to next Monday at 10 AM'.")
        return self._apply_modification(meeting["id"], changes)

    def _extract_changes(self, text: str) -> Dict[str, Any]:
        system_prompt = """
        Extract what the user wants to change about a meeting.
        Return a JSON object with ONLY the keys that are being changed, from:
          date (DD/MM/YYYY or relative like "next Monday")
          time (HH:MM AM/PM, e.g. "03:00 PM")
          schedule_type ("online" or "physical")
          with_whom (name)
        If nothing is being changed, return {}.
        ONLY return the JSON object, no other text.
        Examples:
          "change time to 3 PM"             -> {"time": "03:00 PM"}
          "reschedule to next Monday 10 AM" -> {"date": "next Monday", "time": "10:00 AM"}
          "make it physical"                -> {"schedule_type": "physical"}
        """
        response = self._safe_llm_response(system_prompt, text)
        changes = self._extract_json(response)
        if changes.get("date"):
            resolved = self._resolve_date(changes["date"])
            if resolved:
                changes["date"] = resolved
        return {k: v for k, v in changes.items() if v}

    def _apply_modification(self, meeting_id: int, changes: Dict[str, Any]) -> str:
        if update_schedule(meeting_id, **changes):
            summary = ", ".join(f"{k} → {v}" for k, v in changes.items())
            return f"✅ Meeting ID {meeting_id} updated: {summary}."
        return "Could not update the meeting. Please try again."

    def _continue_meeting_modification(self, user_id: str, session_id: str, user_input: str) -> str:
        pending = self.pending_modifications[session_id]
        step = pending.get("step")

        if step == "awaiting_id":
            meeting_id = self._extract_meeting_id(user_input)
            if not meeting_id:
                attendee = self._extract_attendee_name(user_input)
                if attendee:
                    matches = find_meetings_by_attendee(user_id, attendee)
                    if len(matches) == 1:
                        meeting_id = matches[0]["id"]
                if not meeting_id:
                    return "Please give me the meeting ID number or attendee name."

            meeting = get_schedule_by_id(meeting_id)
            if not meeting or meeting["user_id"] != user_id:
                del self.pending_modifications[session_id]
                return "Meeting not found or you don't have permission."

            changes = self._extract_changes(user_input)
            if not changes:
                changes = self._extract_changes(pending.get("original_input", ""))
            if not changes:
                pending["step"] = "awaiting_changes"
                pending["meeting_id"] = meeting_id
                return (f"What would you like to change about the meeting on {meeting['date']} "
                        f"at {meeting['time']} with {meeting['with_whom']}?\n"
                        "Example: 'change time to 3 PM'.")
            del self.pending_modifications[session_id]
            return self._apply_modification(meeting_id, changes)

        elif step == "awaiting_changes":
            meeting_id = pending["meeting_id"]
            changes = self._extract_changes(user_input)
            if not changes:
                return "I didn't catch what you'd like to change. Example: 'change time to 3 PM'."
            del self.pending_modifications[session_id]
            return self._apply_modification(meeting_id, changes)

        del self.pending_modifications[session_id]
        return self._start_meeting_modification(user_id, session_id, user_input)
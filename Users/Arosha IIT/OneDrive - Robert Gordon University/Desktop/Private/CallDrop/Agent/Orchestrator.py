import re
import pandas as pd
from .Query_Engine import QueryEngine
from .Rag_Engine import query_rag, build_vector_store
from .Config import ENGINEERED_CSV_PATH
from .Config import FEATURE_COLUMNS
from Configure.LLM_Config import get_completion

class Orchestrator:
    def __init__(self):
        self.qe = QueryEngine()
        # Ensure RAG index exists
        try:
            from .Rag_Engine import load_vector_store
            idx, _ = load_vector_store()
            if idx is None:
                build_vector_store(ENGINEERED_CSV_PATH)
        except:
            build_vector_store(ENGINEERED_CSV_PATH)

    def reload_data(self):
        """Reload CSV data and rebuild query engine and RAG index."""
        self.qe = QueryEngine()  # fresh DataFrame
        # Optional: rebuild RAG index to include new calls
        try:
            from .Rag_Engine import build_vector_store
            from .Config import ENGINEERED_CSV_PATH
            build_vector_store(ENGINEERED_CSV_PATH)
            print("✅ RAG index rebuilt after data reload.")
        except Exception as e:
            print(f"⚠️ RAG rebuild skipped: {e}")

    def _answer_structured(self, user_input):
        inp = user_input.lower()

        # --- Call ID (with or without 'id') ---
        m = re.search(r'\bcall\s+id\s*(\d+)\b', user_input, re.IGNORECASE)
        if not m:
            m = re.search(r'\bcall\s*(\d+)\b', user_input, re.IGNORECASE)
        if m:
            cid = int(m.group(1))
            row = self.qe.get_call_by_id(cid)
            if row is None:
                return f"No call with ID {cid} found.", True
            outcome = "dropped" if row['is_drop'] == 1 else "ended normally"
            dt = row['datetime'].strftime("%Y-%m-%d %H:%M:%S") if pd.notna(row.get('datetime')) else "unknown"
            return (f"Call ID {cid} on {dt} {outcome}.\n"
                    f"Duration: {row['call_duration_sec']} sec.\n"
                    f"Signal min: {row['rsrp_min']} dBm, max: {row['rsrp_max']} dBm, slope last5: {row['rsrp_slope_last5']:.2f} dB/s.\n"
                    f"Tower load: {row['tower_load_mean']:.0f}%, speed: {row['speed_kmph_mean']:.1f} km/h."), True

        # --- How many total calls? ---
        if re.search(r'(how many|total|number of).*calls?', inp):
            total = self.qe.get_total_calls()
            drops = self.qe.get_drop_count()
            return f"There are {total} calls in total, of which {drops} were dropped.", True

        # --- First N calls ---
        m = re.search(r'(first|earliest|oldest)\s*(\d+)\s*calls?', inp)
        if m:
            n = int(m.group(2))
            calls = self.qe.get_first_n_calls(n)
            lines = [f"First {n} calls:"]
            for c in calls:
                outcome = "dropped" if c['is_drop'] == 1 else "normal"
                lines.append(f"ID {c['call_id']} at {c['datetime']} - {outcome}")
            return "\n".join(lines), True

        # --- Last N calls ---
        m = re.search(r'(last|recent|latest)\s*(\d+)\s*calls?', inp)
        if m:
            n = int(m.group(2))
            calls = self.qe.get_last_n_calls(n)
            lines = [f"Last {n} calls:"]
            for c in calls:
                outcome = "dropped" if c['is_drop'] == 1 else "normal"
                lines.append(f"ID {c['call_id']} at {c['datetime']} - {outcome}")
            return "\n".join(lines), True

        # --- First/last call (no number) ---
        if re.search(r'(first|earliest|oldest)\s+call', inp):
            row = self.qe.get_first_call()
            outcome = "dropped" if row['is_drop'] == 1 else "ended normally"
            dt = row['datetime'].strftime("%Y-%m-%d %H:%M:%S")
            return f"The first call is ID {row['call_id']} on {dt} {outcome}.", True

        if re.search(r'(last|recent|latest)\s+call', inp):
            row = self.qe.get_last_call()
            outcome = "dropped" if row['is_drop'] == 1 else "ended normally"
            dt = row['datetime'].strftime("%Y-%m-%d %H:%M:%S")
            return f"The most recent call is ID {row['call_id']} on {dt} {outcome}.", True

        # --- When last drop happened ---
        if re.search(r'last\s+drop', inp):
            drops = self.qe.df[self.qe.df['is_drop'] == 1]
            if drops.empty:
                return "No drops in history.", True
            last_drop = drops.iloc[-1]
            dt = last_drop['datetime'].strftime("%Y-%m-%d %H:%M:%S")
            return f"The last drop occurred on {dt} (call ID {last_drop['call_id']}).", True

        # --- How many drops? ---
        if re.search(r'how many.*drop', inp):
            count = self.qe.get_drop_count()
            total = self.qe.get_total_calls()
            return f"There are {count} dropped calls out of {total} total calls.", True

        # --- Average RSRP of dropped calls ---
        if re.search(r'average.*rsrp.*drop', inp):
            avg = self.qe.get_avg_rsrp_min_dropped()
            return f"The average minimum RSRP for dropped calls is {avg:.1f} dBm.", True

        # --- General statistics ---
        if re.search(r'(statistics|summary|overview|drop rate)', inp):
            stats = self.qe.get_stats()
            return (f"Total calls: {stats['total']}\n"
                    f"Dropped: {stats['drops']} ({stats['drop_rate']:.1f}%)\n"
                    f"Average min RSRP: dropped {stats['avg_rsrp_drop']:.0f} dBm, normal {stats['avg_rsrp_normal']:.0f} dBm\n"
                    f"Average slope last5: dropped {stats['avg_slope_drop']:.2f}, normal {stats['avg_slope_normal']:.2f}"), True

        # --- Date filter ---
        m = re.search(r'(\d{4}-\d{2}-\d{2})', user_input)
        if m:
            date_str = m.group(1)
            calls = self.qe.get_calls_on_date(date_str)
            if not calls:
                return f"No calls on {date_str}.", True
            lines = [f"Calls on {date_str}:"]
            for c in calls:
                outcome = "dropped" if c['is_drop'] == 1 else "normal"
                lines.append(f"ID {c['call_id']} at {c['datetime'].strftime('%H:%M:%S')} - {outcome}")
            return "\n".join(lines), True

        # --- Predict from raw feature list (comma or space separated) ---
        # Look for "predict" followed by numbers
        if re.search(r'\b(predict|forecast|estimate)\b', user_input, re.IGNORECASE):
            # Try to extract a sequence of numbers (floats or ints) separated by commas or spaces
            numbers = re.findall(r'-?\d+\.?\d*', user_input)
            if len(numbers) == len(FEATURE_COLUMNS):
                try:
                    features = [float(x) for x in numbers]
                    result = self.qe.predict_from_features(features)
                    if result is None:
                        return "Model not loaded. Cannot predict.", True
                    outcome = "will drop" if result['prediction'] == 1 else "will be stable"
                    prob = result['probability'] * 100
                    return (f"🔮 Prediction: {outcome} (confidence {prob:.1f}%).\n"
                            f"Drop probability: {prob:.1f}%"), True
                except Exception as e:
                    return f"Error during prediction: {str(e)}", True
            else:
                # If not exact match, maybe they want to predict by call ID (handled elsewhere)
                pass

        return None, False

    def answer(self, user_input):
        # 1. Try structured first
        answer, handled = self._answer_structured(user_input)
        if handled:
            return answer

        # 2. Fallback to RAG with global dataset summary + retrieved documents
        # Get global statistics to include in context
        stats = self.qe.get_stats()
        global_summary = (
            f"Dataset contains {stats['total']} calls, of which {stats['drops']} were dropped ({stats['drop_rate']:.1f}%). "
            f"Average minimum RSRP for dropped calls is {stats['avg_rsrp_drop']:.0f} dBm, for normal calls {stats['avg_rsrp_normal']:.0f} dBm. "
            f"Average signal crash slope (last 5 seconds) for dropped calls is {stats['avg_slope_drop']:.2f}, for normal calls {stats['avg_slope_normal']:.2f}."
        )

        # Retrieve relevant documents
        retrieved_docs = query_rag(user_input, top_k=30)
        if retrieved_docs.startswith("RAG index not built"):
            return "I'm still setting up. Please try again in a moment."

        full_context = f"Global dataset summary:\n{global_summary}\n\nDetailed examples (most relevant to your question):\n{retrieved_docs}"

        system = """You are a helpful assistant. Use the provided information to answer the user's question.
        If the information does not contain the exact answer, use the global summary and your reasoning.
        Do not mention 'context', 'dataset', or 'retrieved documents'. Answer naturally, like a telecom expert, Please communicate in a warm, friendly, and engaging way 😊✨ Use emojis naturally to make conversations feel more lively, supportive, and enjoyable while keeping explanations clear, easy to understand, and encouraging 💬🌟
Maintain a positive, human-like tone that feels approachable and motivating — making even technical or complex topics feel simple, fun, and comfortable to learn 🚀💡."""
        prompt = f"{full_context}\n\nUser question: {user_input}\nAnswer:"
        answer, _ = get_completion(prompt, system_prompt=system, temperature=0.3, max_tokens=800)
        return answer
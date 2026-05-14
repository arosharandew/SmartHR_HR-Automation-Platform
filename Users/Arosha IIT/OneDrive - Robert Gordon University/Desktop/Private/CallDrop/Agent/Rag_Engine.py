import pandas as pd
import numpy as np
import os
import pickle
import faiss
from sentence_transformers import SentenceTransformer
from .Config import VECTOR_STORE_DIR, ENGINEERED_CSV_PATH

embedder = SentenceTransformer('all-MiniLM-L6-v2')
VECTOR_STORE_PATH = VECTOR_STORE_DIR

class Document:
    def __init__(self, page_content, metadata):
        self.page_content = page_content
        self.metadata = metadata

def create_document_from_row(row):
    outcome = "dropped" if row.get('is_drop') == 1 else "ended normally"
    dt = row.get('datetime', 'unknown time')
    if pd.notna(dt):
        dt_str = dt.strftime("%Y-%m-%d %H:%M:%S")
    else:
        dt_str = "unknown time"
    text = f"Call ID {row['call_id']} on {dt_str} {outcome}. "
    text += f"Duration: {row['call_duration_sec']} seconds. "
    text += f"Signal strength min {row['rsrp_min']:.0f} dBm, max {row['rsrp_max']:.0f} dBm, average {row['rsrp_mean']:.0f} dBm. "
    text += f"Final signal {row['rsrp_last']:.0f} dBm. Signal crash slope in last 5 seconds: {row['rsrp_slope_last5']:.2f} dB/s. "
    text += f"Time spent with signal below -110 dBm: {row['rsrp_time_below_minus110']} seconds. "
    text += f"Tower load average {row['tower_load_mean']:.0f}%, maximum {row['tower_load_max']:.0f}%. "
    text += f"Speed average {row['speed_kmph_mean']:.1f} km/h, maximum {row['speed_kmph_max']:.1f} km/h. "
    bands = []
    if row.get('band_5G_n78') == 1: bands.append("5G_n78")
    if row.get('band_LTE_B20') == 1: bands.append("LTE_B20")
    if row.get('band_LTE_B3') == 1: bands.append("LTE_B3")
    text += f"Network band(s): {', '.join(bands)}."
    return Document(text, {'call_id': row['call_id']})

def build_vector_store(engineered_csv_path=None):
    if engineered_csv_path is None:
        engineered_csv_path = ENGINEERED_CSV_PATH
    df = pd.read_csv(engineered_csv_path)
    if 'datetime' not in df.columns:
        if 'date' in df.columns and 'time' in df.columns:
            df['datetime'] = pd.to_datetime(df['date'].astype(str) + ' ' + df['time'].astype(str))
        elif 'start_timestamp' in df.columns:
            df['datetime'] = pd.to_datetime(df['start_timestamp'], unit='s')
        else:
            df['datetime'] = pd.to_datetime(df['call_id'], origin='unix', unit='s')
    documents = []
    for _, row in df.iterrows():
        doc = create_document_from_row(row)
        documents.append(doc)
    texts = [doc.page_content for doc in documents]
    embeddings = embedder.encode(texts, show_progress_bar=True)
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings.astype(np.float32))
    os.makedirs(VECTOR_STORE_PATH, exist_ok=True)
    faiss.write_index(index, os.path.join(VECTOR_STORE_PATH, "calls.index"))
    with open(os.path.join(VECTOR_STORE_PATH, "documents.pkl"), "wb") as f:
        pickle.dump(documents, f)
    print(f"Vector store built with {len(documents)} documents.")

def load_vector_store():
    index_path = os.path.join(VECTOR_STORE_PATH, "calls.index")
    docs_path = os.path.join(VECTOR_STORE_PATH, "documents.pkl")
    if not os.path.exists(index_path) or not os.path.exists(docs_path):
        return None, None
    index = faiss.read_index(index_path)
    with open(docs_path, "rb") as f:
        documents = pickle.load(f)
    return index, documents

def query_rag(query, top_k=30):   # increased to 30
    index, documents = load_vector_store()
    if index is None:
        return "RAG index not built. Run build_vector_store first."
    query_embedding = embedder.encode([query])[0].astype(np.float32).reshape(1, -1)
    distances, indices = index.search(query_embedding, top_k)
    retrieved = [documents[i] for i in indices[0] if i != -1]
    context = "\n\n".join([doc.page_content for doc in retrieved])
    return context
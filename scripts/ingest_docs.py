import os
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
import sys

from dotenv import load_dotenv
load_dotenv()

from docling.document_converter import DocumentConverter
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_vertexai import VertexAIEmbeddings
from langchain_community.vectorstores import Chroma

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import get_settings

# =========================
# CONFIG
# =========================
SETTINGS = get_settings()
DOCS_DIR = str(SETTINGS.docs_dir)
CHROMA_DB_DIR = str(SETTINGS.chroma_db_dir)
CACHE_FILE = str(SETTINGS.ingestion_cache_file)

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100
MAX_WORKERS = 1  # Reduced from 4 to 1 to prevent Docling out-of-memory errors (std::bad_alloc / os error 1455)

# =========================
# UTILITIES
# =========================

def file_hash(path):
    hasher = hashlib.md5()
    with open(path, "rb") as f:
        hasher.update(f.read())
    return hasher.hexdigest()


def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


# =========================
# DOCLING PARSER
# =========================

def parse_with_docling(file_path):
    try:
        converter = DocumentConverter()
        result = converter.convert(file_path)
        text = result.document.export_to_markdown()

        return Document(
            page_content=text,
            metadata={
                "source": file_path,
                "filename": os.path.basename(file_path),
                "ingested_at": datetime.utcnow().isoformat()
            }
        )
    except Exception as e:
        print(f"[ERROR] Docling failed: {file_path} -> {e}")
        return None


# =========================
# INGESTION PIPELINE
# =========================

def ingest():
    print("Starting ingestion pipeline...")

    os.makedirs(CHROMA_DB_DIR, exist_ok=True)
    os.makedirs(DOCS_DIR, exist_ok=True)

    cache = load_cache()
    new_cache = {}

    files = [
        os.path.join(DOCS_DIR, f)
        for f in os.listdir(DOCS_DIR)
        if f.lower().endswith((".pdf",))
    ]

    print(f"Found {len(files)} files")

    # =========================
    # STEP 1: CHANGE DETECTION
    # =========================
    to_process = []

    for path in files:
        h = file_hash(path)
        new_cache[path] = h

        if path not in cache or cache[path] != h:
            to_process.append(path)

    print(f"{len(to_process)} files changed / new")

    if not to_process:
        print("No changes detected. Skipping ingestion.")
        return

    # =========================
    # STEP 2: PARALLEL PARSING
    # =========================
    docs = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(parse_with_docling, f): f for f in to_process}

        for future in as_completed(futures):
            result = future.result()
            if result:
                docs.append(result)

    print(f"Parsed {len(docs)} documents")

    if not docs:
        print("No documents parsed successfully")
        return

    # =========================
    # STEP 3: CHUNKING
    # =========================
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP
    )

    chunks = splitter.split_documents(docs)
    print(f"Created {len(chunks)} chunks")

    # =========================
    # STEP 4: EMBEDDING + STORE
    # =========================
    embeddings = VertexAIEmbeddings(
        model_name="text-embedding-004"
    )

    vectordb = Chroma(
        persist_directory=CHROMA_DB_DIR,
        embedding_function=embeddings
    )

    vectordb.add_documents(chunks)

    print("Persisting to Chroma...")

    # =========================
    # STEP 5: SAVE CACHE
    # =========================
    save_cache(new_cache)

    print("Ingestion complete!")


# =========================
# ENTRYPOINT
# =========================

if __name__ == "__main__":
    ingest()


import os
import io
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple
from functools import lru_cache

import chromadb
import fitz
import pytesseract

from PIL import Image
from dotenv import load_dotenv
from google import genai
from google.genai import types


# ==============================
# LOGGING
# ==============================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==============================
# LOAD ENVIRONMENT
# ==============================

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


# ==============================
# PROJECT PATHS
# ==============================

CHROMA_DIR = BASE_DIR / "chroma_db"
UPLOAD_DIR = BASE_DIR / "uploaded_materials"

COLLECTION_NAME = "course_materials"


# ==============================
# GEMINI SETTINGS
# ==============================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.8-flash"
)

EMBEDDING_MODEL = os.getenv(
    "GEMINI_EMBEDDING_MODEL",
    "gemini-embedding-001"
)

# 60 seconds timeout
GEMINI_TIMEOUT_MS = 60000

# Maximum one retry
MAX_RETRIES = 1


# ==============================
# OCR SETTINGS
# ==============================

OCR_LANG = os.getenv("TESSERACT_LANG", "eng")

TESSERACT_CMD = os.getenv("TESSERACT_CMD")

if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = (
        TESSERACT_CMD.strip().strip('"')
    )
else:
    default_tesseract = (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    )

    if Path(default_tesseract).exists():
        pytesseract.pytesseract.tesseract_cmd = (
            default_tesseract
        )


# ==============================
# CLIENTS
# ==============================

_gemini_client = None
_chroma_client = None
_collection = None


# ==============================
# GEMINI CLIENT
# ==============================

def get_gemini_client():

    global _gemini_client

    if _gemini_client is None:

        if not GEMINI_API_KEY:
            raise RuntimeError(
                "GEMINI_API_KEY is not configured in .env"
            )

        _gemini_client = genai.Client(
            api_key=GEMINI_API_KEY,
            http_options=types.HttpOptions(
                timeout=GEMINI_TIMEOUT_MS
            )
        )

    return _gemini_client


# ==============================
# CHROMADB COLLECTION
# ==============================

def get_collection():

    global _chroma_client
    global _collection

    if _collection is None:

        CHROMA_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        _chroma_client = chromadb.PersistentClient(
            path=str(CHROMA_DIR)
        )

        _collection = _chroma_client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={
                "description":
                "AI Programming Tutor course materials"
            }
        )

    return _collection


# ==============================
# GEMINI EMBEDDING
# ==============================

def embed_texts(
    texts: List[str],
    task_type: str
) -> List[List[float]]:

    if not texts:
        return []

    client = get_gemini_client()

    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(
            task_type=task_type
        )
    )

    if not response.embeddings:
        raise RuntimeError(
            "Gemini returned no embeddings"
        )

    return [
        embedding.values
        for embedding in response.embeddings
    ]


# ==============================
# QUERY EMBEDDING CACHE
# ==============================

@lru_cache(maxsize=256)
def get_cached_query_embedding(
    question: str
) -> tuple:

    embeddings = embed_texts(
        [question],
        "RETRIEVAL_QUERY"
    )

    return tuple(embeddings[0])


# ==============================
# TEXT CHUNKING
# ==============================

def chunk_text(
    text: str,
    chunk_size: int = 1200,
    overlap: int = 200
) -> List[str]:

    text = " ".join(text.split())

    if not text:
        return []

    chunks = []
    start = 0

    while start < len(text):

        end = min(
            start + chunk_size,
            len(text)
        )

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = end - overlap

    return chunks


# ==============================
# OCR TEXT EXTRACTION
# ==============================

def extract_page_text(page) -> Tuple[str, bool]:

    text = page.get_text("text").strip()

    if len(text) >= 30:
        return text, False

    try:

        matrix = fitz.Matrix(
            300 / 72,
            300 / 72
        )

        pix = page.get_pixmap(
            matrix=matrix,
            alpha=False
        )

        image = Image.open(
            io.BytesIO(pix.tobytes("png"))
        )

        ocr_text = pytesseract.image_to_string(
            image,
            lang=OCR_LANG,
            config="--psm 6"
        ).strip()

        return ocr_text, True

    except pytesseract.TesseractNotFoundError as exc:

        raise RuntimeError(
            "Tesseract OCR is not installed or configured."
        ) from exc

    except pytesseract.TesseractError as exc:

        raise RuntimeError(
            f"OCR failed. Check language '{OCR_LANG}'. "
            f"Details: {exc}"
        ) from exc


# ==============================
# PDF INGESTION
# ==============================

def ingest_pdf(filename: str) -> Dict[str, Any]:

    safe_name = Path(filename).name
    pdf_path = UPLOAD_DIR / safe_name

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF not found: {safe_name}"
        )

    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(
            "Only PDF files can be indexed"
        )

    documents = []
    metadatas = []
    ids = []

    ocr_pages = 0

    pdf_document = fitz.open(str(pdf_path))

    try:

        for page_index, page in enumerate(pdf_document):

            page_number = page_index + 1

            text, used_ocr = extract_page_text(page)

            if used_ocr:
                ocr_pages += 1

            page_chunks = chunk_text(text)

            for chunk_number, chunk in enumerate(
                page_chunks,
                start=1
            ):

                documents.append(chunk)

                metadatas.append({
                    "filename": safe_name,
                    "page": page_number,
                    "chunk": chunk_number
                })

                ids.append(
                    f"{safe_name}:"
                    f"page-{page_number}:"
                    f"chunk-{chunk_number}"
                )

        total_pages = len(pdf_document)

    finally:
        pdf_document.close()

    if not documents:
        raise ValueError(
            "No readable text found in PDF, even after OCR."
        )

    embeddings = embed_texts(
        documents,
        "RETRIEVAL_DOCUMENT"
    )

    if len(embeddings) != len(documents):
        raise RuntimeError(
            "Embedding count does not match document count"
        )

    collection = get_collection()

    collection.delete(
        where={"filename": safe_name}
    )

    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas
    )

    return {
        "message": "PDF indexed successfully",
        "filename": safe_name,
        "pages": total_pages,
        "ocr_pages": ocr_pages,
        "chunks": len(documents)
    }


# ==============================
# GEMINI ANSWER WITH RETRY
# ==============================

def generate_answer(prompt: str) -> str:

    client = get_gemini_client()

    for attempt in range(MAX_RETRIES + 1):

        try:

            start_time = time.time()

            logger.info(
                "Sending answer request to Gemini..."
            )

            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=1024
                )
            )

            answer = response.text

            elapsed = time.time() - start_time

            logger.info(
                "Gemini response received in %.2f seconds",
                elapsed
            )

            if not answer or not answer.strip():
                raise RuntimeError(
                    "Gemini returned an empty answer"
                )

            return answer.strip()

        except Exception as exc:

            error_message = str(exc).upper()

            temporary_error = any(
                error in error_message
                for error in [
                    "503",
                    "UNAVAILABLE",
                    "429",
                    "RESOURCE_EXHAUSTED",
                    "500",
                    "INTERNAL",
                    "504",
                    "DEADLINE_EXCEEDED"
                ]
            )

            if temporary_error and attempt < MAX_RETRIES:

                wait_seconds = 3

                logger.warning(
                    "Gemini temporary error. "
                    "Retrying in %s seconds. Error: %s",
                    wait_seconds,
                    exc
                )

                time.sleep(wait_seconds)
                continue

            raise RuntimeError(
                f"Gemini answer generation failed "
                f"using model '{GEMINI_MODEL}': {exc}"
            ) from exc

    raise RuntimeError(
        "Gemini answer generation failed"
    )


# ==============================
# ASK AI TUTOR
# ==============================

def ask_question(
    question: str,
    top_k: int = 4
) -> Dict[str, Any]:

    start_time = time.time()

    question = question.strip()

    if not question:
        raise ValueError(
            "Question cannot be empty"
        )

    collection = get_collection()

    if collection.count() == 0:
        raise ValueError(
            "No course material has been indexed yet"
        )

    # Query embedding cache
    embedding_start = time.time()

    query_embedding = list(
        get_cached_query_embedding(question)
    )

    logger.info(
        "Embedding completed in %.2f seconds",
        time.time() - embedding_start
    )

    # Retrieve relevant chunks
    retrieval_start = time.time()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=max(1, min(top_k, 4)),
        include=[
            "documents",
            "metadatas",
            "distances"
        ]
    )

    logger.info(
        "ChromaDB retrieval completed in %.2f seconds",
        time.time() - retrieval_start
    )

    documents = results.get("documents", [[]])[0] or []
    metadatas = results.get("metadatas", [[]])[0] or []
    distances = results.get("distances", [[]])[0] or []

    if not documents:
        raise ValueError(
            "No relevant course material was found"
        )

    context_parts = []
    sources = []

    for document, metadata, distance in zip(
        documents,
        metadatas,
        distances
    ):

        context_parts.append(
            f"Source: {metadata['filename']}, "
            f"page {metadata['page']}\n"
            f"{document}"
        )

        sources.append({
            "filename": metadata["filename"],
            "page": metadata["page"],
            "chunk": metadata["chunk"],
            "distance": distance
        })

    context = "\n\n---\n\n".join(context_parts)
    context = context[:6000]

    prompt = f"""
You are an AI Programming Tutor.

Answer the student's question using
the course-material context below.

Rules:

1. Prefer the supplied course material.
2. If information is insufficient, clearly say so.
3. Do not invent facts or page numbers.
4. Explain concepts in a student-friendly way.
5. Keep the answer clear and concise.

Course material context:

{context}

Student question:

{question}
"""

    answer = generate_answer(prompt)

    logger.info(
        "Total ask_question time: %.2f seconds",
        time.time() - start_time
    )

    return {
        "answer": answer,
        "sources": sources
    }

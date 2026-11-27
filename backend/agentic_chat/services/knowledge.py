"""Small local vector RAG index for approved files in this chatbot's knowledge folder."""
import json
import math
import re
import sqlite3
import unicodedata
from pathlib import Path

import requests

from .ollama import chat
from .settings import EMBED_MODEL, INDEX_PATH, KNOWLEDGE_DIR, OLLAMA_URL

SUPPORTED_EXTENSIONS = {".md", ".txt", ".pdf"}


def _read_file(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as error:
            raise RuntimeError("Install the V2 dependencies to index PDF documents.") from error
        return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    return path.read_text(encoding="utf-8", errors="replace")


def _chunks(text: str, size: int = 1100, overlap: int = 160) -> list[str]:
    result = []
    sections = re.split(r"(?=^#{1,3}\s+)", text, flags=re.MULTILINE)
    for section in sections:
        normalized = re.sub(r"\s+", " ", section).strip()
        if not normalized:
            continue
        start = 0
        while start < len(normalized):
            end = min(len(normalized), start + size)
            if end < len(normalized):
                boundary = normalized.rfind(" ", start + size // 2, end)
                if boundary > start:
                    end = boundary
            result.append(normalized[start:end].strip())
            if end == len(normalized):
                break
            start = max(start + 1, end - overlap)
    return result


def _embed(texts: list[str]) -> list[list[float]]:
    response = requests.post(
        f"{OLLAMA_URL}/api/embed",
        json={"model": EMBED_MODEL, "input": texts},
        timeout=60,
    )
    response.raise_for_status()
    embeddings = response.json().get("embeddings")
    if not isinstance(embeddings, list) or len(embeddings) != len(texts):
        raise ValueError("Ollama returned an invalid embedding response.")
    return embeddings


def _connect():
    connection = sqlite3.connect(INDEX_PATH)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_chunks (
            id INTEGER PRIMARY KEY,
            source TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding TEXT,
            UNIQUE(source, chunk_index)
        );
        """
    )
    connection.commit()
    return connection


def index_documents(*, lexical_only: bool = False) -> dict:
    files = sorted(
        path for path in KNOWLEDGE_DIR.rglob("*")
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_EXTENSIONS
        and path.name.casefold() != "readme.md"
    )
    records = []
    for path in files:
        source = path.relative_to(KNOWLEDGE_DIR).as_posix()
        for index, chunk in enumerate(_chunks(_read_file(path))):
            records.append((source, index, chunk))
    if lexical_only:
        vectors = [None] * len(records)
        retrieval_mode = "lexical_fallback"
    else:
        try:
            vectors = _embed([row[2] for row in records]) if records else []
            retrieval_mode = "vector"
        except (requests.RequestException, ValueError):
            vectors = [None] * len(records)
            retrieval_mode = "lexical_fallback"

    connection = _connect()
    try:
        connection.execute("DELETE FROM knowledge_chunks")
        connection.executemany(
            "INSERT INTO knowledge_chunks(source, chunk_index, content, embedding) VALUES (?, ?, ?, ?)",
            [
                (source, index, content, json.dumps(vector) if vector is not None else None)
                for (source, index, content), vector in zip(records, vectors)
            ],
        )
        connection.commit()
    finally:
        connection.close()
    return {"documents": len(files), "chunks": len(records), "retrieval_mode": retrieval_mode}


def _cosine(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def search_knowledge(query: str, limit: int = 4) -> tuple[list[dict], str]:
    connection = _connect()
    try:
        rows = connection.execute(
            "SELECT source, chunk_index, content, embedding FROM knowledge_chunks"
        ).fetchall()
    finally:
        connection.close()
    if not rows:
        return [], "empty"

    query_vector = None
    if any(row[3] for row in rows):
        try:
            query_vector = _embed([query])[0]
        except (requests.RequestException, ValueError):
            query_vector = None

    stop_words = {
        "what", "is", "our", "the", "a", "an", "of", "for", "do", "does", "we", "you",
        "what", "quelle", "quelles", "quel", "quels", "est", "notre", "nos", "le", "la",
        "les", "des", "du", "de", "un", "une", "pour", "comment", "sont", "avez", "votre",
    }
    query_terms = set(re.findall(r"[a-zA-Z0-9À-ÿ]+", query.lower())) - stop_words
    scored = []
    for source, chunk_index, content, raw_vector in rows:
        if query_vector is not None and raw_vector:
            score = _cosine(query_vector, json.loads(raw_vector))
        else:
            content_terms = re.findall(r"[a-zA-Z0-9À-ÿ]+", content.lower())
            score = sum(min(content_terms.count(term), 3) for term in query_terms) / max(1, len(query_terms))
        scored.append({"source": source, "chunk_index": chunk_index, "content": content, "score": score})
    scored.sort(key=lambda item: item["score"], reverse=True)
    mode = "vector" if query_vector is not None else "lexical_fallback"
    return scored[: max(1, min(limit, 10))], mode


def answer_from_knowledge(query: str) -> dict:
    hits, retrieval_mode = search_knowledge(query)
    if not hits:
        normalized_query = unicodedata.normalize("NFKD", query.casefold())
        normalized_query = "".join(
            char for char in normalized_query if not unicodedata.combining(char)
        )
        french = bool(re.search(
            r"\b(quelle|quelles|quel|quels|comment|combien|livraison|retour|"
            r"garantie|remboursement|politique|conditions|est|sont|avez|votre)\b",
            normalized_query,
        ))
        if french:
            answer = (
                "Je n’ai pas encore de document approuvé qui décrit cette politique. "
                "Je préfère ne pas inventer la réponse. Ajoutez le document concerné à la base de connaissances."
            )
        else:
            answer = (
                "I don't have an approved company document covering that policy yet, "
                "so I can't give a reliable answer. Add the relevant document to the knowledge base."
            )
        return {
            "answer": answer,
            "sources": [],
            "retrieval_mode": retrieval_mode,
        }
    context = "\n\n".join(
        f"[Source: {hit['source']} | chunk {hit['chunk_index']}]\n{hit['content']}"
        for hit in hits
    )
    try:
        answer = chat([
            {
                "role": "system",
                "content": (
                    "Answer using only the supplied business-document excerpts. "
                    "If they do not contain the answer, say so clearly. Cite filenames "
                    "in square brackets, for example [returns_policy.md]. Do not invent policy. "
                    "If a source is marked draft, sample, or illustrative, say clearly that it is not "
                    "an approved company policy and present its terms only as a proposal for testing. "
                    "Reply in the same language as the user's question."
                ),
            },
            {"role": "user", "content": f"Question: {query}\n\nDocument excerpts:\n{context}"},
        ])
    except (requests.RequestException, ValueError):
        # Keep document answers usable when the local chat model is unavailable.
        excerpt = next((hit["content"] for hit in hits if hit["score"] > 0), hits[0]["content"])
        source_is_draft = any("draft" in hit["source"].casefold() for hit in hits)
        all_context = " ".join(hit["content"] for hit in hits)
        source_is_draft = source_is_draft or bool(
            re.search(r"\b(draft|sample|illustrative|brouillon|illustratif)\b", all_context, flags=re.IGNORECASE)
        )
        french_query = bool(re.search(r"\b(livraison|retour|garantie|remboursement|politique|paiement)\b", query.casefold()))
        if source_is_draft and french_query:
            answer = "Ce document est un brouillon illustratif, pas une politique officielle confirmée. Extrait pertinent : " + excerpt
        elif source_is_draft:
            answer = "This is an illustrative draft, not a confirmed company policy. Relevant document excerpt: " + excerpt
        else:
            answer = "Relevant document excerpt: " + excerpt
    sources = list(dict.fromkeys(hit["source"] for hit in hits if hit["score"] > 0))
    return {"answer": answer, "sources": sources, "retrieval_mode": retrieval_mode}


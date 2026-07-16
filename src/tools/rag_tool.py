"""
src/tools/rag_tool.py
======================
RAG (Retrieval-Augmented Generation) tool using FAISS + sentence-transformers.
Loads documents from the knowledge_base/, chunks them, embeds with
all-MiniLM-L6-v2 (local, zero cost), and stores in a FAISS index.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type

import numpy as np
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from config.settings import settings
from src.utils.cache import cache_manager
from src.utils.logger import get_logger

log = get_logger(__name__)

# Lazy imports to avoid slow startup when FAISS/transformers not needed
_faiss = None
_sentence_transformer = None


def _get_faiss():
    global _faiss
    if _faiss is None:
        import faiss

        _faiss = faiss
    return _faiss


def _get_encoder():
    global _sentence_transformer
    if _sentence_transformer is None:
        from sentence_transformers import SentenceTransformer

        log.info(f"Loading embedding model: {settings.embedding_model}")
        _sentence_transformer = SentenceTransformer(
            settings.embedding_model,
            device=settings.embedding_device,
        )
    return _sentence_transformer


# ── Document chunk ────────────────────────────────────────────────────────────


class DocumentChunk(BaseModel):
    chunk_id: str
    document_id: str
    source_path: str
    source_name: str
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    chunk_index: int = 0
    embedding: Optional[List[float]] = None

    @property
    def citation_metadata(self) -> Dict[str, str]:
        return {
            "source_path": self.source_path,
            "source_name": self.source_name,
            "chunk_index": str(self.chunk_index),
        }


# ── FAISS Vector Store ────────────────────────────────────────────────────────


class FAISSVectorStore:
    """FAISS-backed vector store with local embeddings."""

    DIMENSION = 384  # all-MiniLM-L6-v2 output dimension

    def __init__(self, store_path: Path) -> None:
        self._store_path = store_path
        self._store_path.mkdir(parents=True, exist_ok=True)
        self._index_path = store_path / "faiss.index"
        self._chunks_path = store_path / "chunks.jsonl"
        self._chunks: List[DocumentChunk] = []
        self._index = None
        self._loaded = False

    def _ensure_index(self) -> Any:
        """Lazy-load or create FAISS index."""
        if self._index is None:
            faiss = _get_faiss()
            if self._index_path.exists() and self._chunks_path.exists():
                self._index = faiss.read_index(str(self._index_path))
                self._load_chunks()
                log.info(f"[RAG] Loaded existing FAISS index: {self._index.ntotal} vectors")
            else:
                self._index = faiss.IndexFlatIP(self.DIMENSION)
                log.info("[RAG] Created new FAISS index")
        return self._index

    def _load_chunks(self) -> None:
        self._chunks = []
        if self._chunks_path.exists():
            with open(self._chunks_path, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        data.pop("embedding", None)  # Don't reload vectors
                        self._chunks.append(DocumentChunk(**data))

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """Embed a list of texts using the local model with caching."""
        encoder = _get_encoder()
        vectors = []
        texts_to_embed = []
        cache_indices = []

        for i, text in enumerate(texts):
            cached = cache_manager.get_embedding(text)
            if cached is not None:
                vectors.append(np.array(cached, dtype=np.float32))
            else:
                texts_to_embed.append(text)
                cache_indices.append(i)

        if texts_to_embed:
            new_vectors = encoder.encode(
                texts_to_embed,
                normalize_embeddings=True,
                show_progress_bar=False,
                batch_size=32,
            )
            for idx, vec, text in zip(cache_indices, new_vectors, texts_to_embed):
                cache_manager.set_embedding(text, vec.tolist())
                vectors.insert(idx, vec)

        return np.array(vectors, dtype=np.float32)

    def add_chunks(self, chunks: List[DocumentChunk]) -> int:
        """Add document chunks to the vector store."""
        if not chunks:
            return 0

        index = self._ensure_index()
        texts = [c.text for c in chunks]
        vectors = self.embed_texts(texts)

        # Normalise for cosine similarity via inner product
        index.add(vectors)

        # Persist chunks metadata
        with open(self._chunks_path, "a", encoding="utf-8") as f:
            for chunk in chunks:
                chunk.embedding = None  # Don't store large vectors in JSON
                f.write(chunk.model_dump_json() + "\n")

        self._chunks.extend(chunks)

        # Save FAISS index
        faiss = _get_faiss()
        faiss.write_index(index, str(self._index_path))
        log.info(f"[RAG] Added {len(chunks)} chunks. Total: {index.ntotal}")
        return len(chunks)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[DocumentChunk, float]]:
        """Semantic search over the vector store."""
        index = self._ensure_index()
        if index.ntotal == 0:
            return []

        encoder = _get_encoder()
        query_vec = encoder.encode([query], normalize_embeddings=True, show_progress_bar=False)

        k = min(top_k, index.ntotal)
        scores, indices = index.search(query_vec.astype(np.float32), k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and idx < len(self._chunks):
                results.append((self._chunks[idx], float(score)))

        return results

    @property
    def total_chunks(self) -> int:
        return len(self._chunks)


# ── Document loader and chunker ───────────────────────────────────────────────


class DocumentLoader:
    """Loads and chunks documents from the knowledge_base directory."""

    def load_directory(self, directory: Path) -> List[DocumentChunk]:
        """Load all supported documents from a directory."""
        chunks = []
        if not directory.exists():
            return chunks

        for file_path in directory.rglob("*"):
            if file_path.is_file():
                try:
                    new_chunks = self.load_file(file_path)
                    chunks.extend(new_chunks)
                except Exception as exc:
                    log.warning(f"[RAG] Failed to load {file_path}: {exc}")

        log.info(f"[RAG] Loaded {len(chunks)} chunks from {directory}")
        return chunks

    def load_file(self, file_path: Path) -> List[DocumentChunk]:
        """Load and chunk a single file."""
        suffix = file_path.suffix.lower()
        text = ""

        if suffix in [".txt", ".md"]:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        elif suffix == ".csv":
            import csv

            rows = []
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows.append(" | ".join(f"{k}: {v}" for k, v in row.items()))
            text = "\n".join(rows)
        elif suffix == ".json":
            data = json.loads(file_path.read_text(encoding="utf-8"))
            text = json.dumps(data, indent=2)
        else:
            return []

        if not text.strip():
            return []

        return self._chunk_text(text, str(file_path), file_path.name)

    def _chunk_text(self, text: str, source_path: str, source_name: str) -> List[DocumentChunk]:
        """Split text into overlapping chunks."""
        words = text.split()
        chunk_size = settings.chunk_size
        overlap = settings.chunk_overlap
        chunks = []
        doc_id = hashlib.sha256(source_path.encode()).hexdigest()[:12]

        i = 0
        chunk_idx = 0
        while i < len(words):
            chunk_words = words[i : i + chunk_size]
            chunk_text = " ".join(chunk_words).strip()
            if chunk_text:
                chunk_id = f"{doc_id}_{chunk_idx}"
                chunks.append(
                    DocumentChunk(
                        chunk_id=chunk_id,
                        document_id=doc_id,
                        source_path=source_path,
                        source_name=source_name,
                        text=chunk_text,
                        chunk_index=chunk_idx,
                        metadata={"source": source_path},
                    )
                )
                chunk_idx += 1
            i += chunk_size - overlap

        return chunks


# ── RAG Tool ──────────────────────────────────────────────────────────────────


class RAGInput(BaseModel):
    action: str = Field(
        ...,
        description=("Action: 'search', 'index_directory', 'index_text', 'stats'"),
    )
    query: Optional[str] = Field(None, description="Semantic search query")
    directory: Optional[str] = Field(None, description="Directory path to index")
    text: Optional[str] = Field(None, description="Text content to add to index")
    source_name: Optional[str] = Field(None, description="Source name for indexed text")
    top_k: int = Field(default=5, ge=1, le=20)


class RAGTool(BaseTool):
    """
    RAG tool for semantic search over the knowledge base.

    Uses FAISS for vector storage and all-MiniLM-L6-v2 for embeddings
    (local model — zero API cost).

    Supports indexing documents from files and performing semantic search
    to retrieve relevant context for the analyst and writer agents.
    """

    name: str = "rag_search"
    description: str = (
        "Search the internal knowledge base using semantic search. "
        "Use 'search' to find relevant documents about competitors or industry topics. "
        "Use 'index_directory' to add documents to the knowledge base. "
        "Returns relevant text chunks with source citations."
    )
    args_schema: Type[BaseModel] = RAGInput

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._vector_store = FAISSVectorStore(settings.vectorstore_dir)
        self._loader = DocumentLoader()
        self._indexed_dirs: set = set()

    def _run(
        self,
        action: str,
        query: Optional[str] = None,
        directory: Optional[str] = None,
        text: Optional[str] = None,
        source_name: Optional[str] = None,
        top_k: int = 5,
    ) -> str:
        if action == "search":
            return self._search(query, top_k)
        elif action == "index_directory":
            return self._index_directory(directory)
        elif action == "index_text":
            return self._index_text(text, source_name)
        elif action == "stats":
            return f"Vector store: {self._vector_store.total_chunks} chunks indexed"
        else:
            return f"Unknown action: {action}"

    def _search(self, query: Optional[str], top_k: int) -> str:
        """Execute semantic search."""
        if not query:
            return "Error: query required for search."

        # Auto-index knowledge base on first search
        kb_dir = Path("./knowledge_base")
        if str(kb_dir) not in self._indexed_dirs and kb_dir.exists():
            self._index_directory(str(kb_dir))

        results = self._vector_store.search(query, top_k=top_k)

        if not results:
            return f"No relevant documents found for: {query}"

        lines = [f"## RAG Search Results for: '{query}'\n"]
        for i, (chunk, score) in enumerate(results, 1):
            lines.append(
                f"**[RAG-{i}]** (relevance: {score:.3f})\n"
                f"Source: {chunk.source_name}\n"
                f"Path: {chunk.source_path}\n"
                f"Content:\n{chunk.text[:600]}\n"
            )
        return "\n".join(lines)

    def _index_directory(self, directory: Optional[str]) -> str:
        """Index all documents in a directory."""
        if not directory:
            directory = str(settings.vectorstore_dir.parent)

        dir_path = Path(directory)
        if not dir_path.exists():
            return f"Directory not found: {directory}"

        if str(dir_path) in self._indexed_dirs:
            return f"Directory already indexed: {directory}"

        chunks = self._loader.load_directory(dir_path)
        if not chunks:
            return f"No indexable documents found in {directory}"

        added = self._vector_store.add_chunks(chunks)
        self._indexed_dirs.add(str(dir_path))
        return f"Indexed {added} chunks from {directory}"

    def _index_text(self, text: Optional[str], source_name: Optional[str]) -> str:
        """Index raw text content."""
        if not text:
            return "Error: text required."
        source = source_name or "inline_content"
        chunks = self._loader._chunk_text(text, source, source)
        added = self._vector_store.add_chunks(chunks)
        return f"Indexed {added} chunks from inline content"

    def get_vector_store(self) -> FAISSVectorStore:
        """Return the underlying vector store (for direct use)."""
        return self._vector_store


# Singleton
rag_tool = RAGTool()

__all__ = [
    "RAGTool",
    "rag_tool",
    "FAISSVectorStore",
    "DocumentLoader",
    "DocumentChunk",
]

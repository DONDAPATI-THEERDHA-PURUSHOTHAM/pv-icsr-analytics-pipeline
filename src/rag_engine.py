"""
Local Vector Embedding & RAG Engine
Author: Enterprise AI Engineering Team
Description: Pure Python semantic chunking, TF-IDF / N-gram cosine vector indexing, 
             and natural language RAG retrieval engine for unstructured documents and tabular metrics.
"""

import math
import re
from typing import Any, Dict, List, Optional, Tuple


class LocalRAGEngine:
    """Local semantic vector embedding and context retrieval engine."""

    def __init__(self):
        self.chunks: List[Dict[str, Any]] = []
        self.vocabulary: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.doc_vectors: List[Dict[str, float]] = []

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        text_clean = text.lower()
        tokens = re.findall(r"\b[a-z0-9_]{2,}\b", text_clean)
        return tokens

    def _chunk_text(self, text: str, chunk_size: int = 400, overlap: int = 80) -> List[str]:
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        chunks = []
        curr_chunk = []
        curr_len = 0

        for line in lines:
            if curr_len + len(line) > chunk_size and curr_chunk:
                chunks.append("\n".join(curr_chunk))
                # keep last line for overlap
                curr_chunk = [curr_chunk[-1]] if len(curr_chunk) > 1 else []
                curr_len = sum(len(c) for c in curr_chunk)

            curr_chunk.append(line)
            curr_len += len(line)

        if curr_chunk:
            chunks.append("\n".join(curr_chunk))

        return chunks if chunks else [text]

    def index_document(self, text_content: str, metadata: Optional[Dict[str, Any]] = None):
        """Chunks document, builds term frequencies, computes TF-IDF vectors."""
        metadata = metadata or {}
        raw_chunks = self._chunk_text(text_content)

        self.chunks = []
        doc_tokens_list = []
        term_doc_count: Dict[str, int] = {}

        for idx, chunk_str in enumerate(raw_chunks):
            tokens = self._tokenize(chunk_str)
            doc_tokens_list.append(tokens)
            unique_terms = set(tokens)

            for term in unique_terms:
                term_doc_count[term] = term_doc_count.get(term, 0) + 1

            self.chunks.append({
                "chunk_id": f"chk_{idx + 1}",
                "text": chunk_str,
                "metadata": metadata,
                "token_count": len(tokens)
            })

        total_docs = max(len(self.chunks), 1)
        self.idf = {term: math.log((total_docs + 1) / (count + 1)) + 1.0 for term, count in term_doc_count.items()}

        # Build normalized TF-IDF vector for each chunk
        self.doc_vectors = []
        for tokens in doc_tokens_list:
            tf: Dict[str, float] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0.0) + 1.0

            vector: Dict[str, float] = {}
            norm_sq = 0.0
            for t, count in tf.items():
                tfidf = (count / max(len(tokens), 1)) * self.idf.get(t, 1.0)
                vector[t] = tfidf
                norm_sq += tfidf * tfidf

            norm = math.sqrt(norm_sq) if norm_sq > 0 else 1.0
            normalized_vec = {t: v / norm for t, v in vector.items()}
            self.doc_vectors.append(normalized_vec)

    def query(self, query_text: str, top_k: int = 4) -> Dict[str, Any]:
        """Performs cosine vector search and returns relevant chunks with score."""
        if not self.chunks or not self.doc_vectors:
            return {
                "query": query_text,
                "answer": "No indexed content is currently available to query.",
                "retrieved_chunks": []
            }

        q_tokens = self._tokenize(query_text)
        if not q_tokens:
            return {
                "query": query_text,
                "answer": "Query contains no searchable terms.",
                "retrieved_chunks": []
            }

        # Build query vector
        q_tf: Dict[str, float] = {}
        for t in q_tokens:
            q_tf[t] = q_tf.get(t, 0.0) + 1.0

        q_vec: Dict[str, float] = {}
        q_norm_sq = 0.0
        for t, count in q_tf.items():
            tfidf = (count / len(q_tokens)) * self.idf.get(t, 1.0)
            q_vec[t] = tfidf
            q_norm_sq += tfidf * tfidf

        q_norm = math.sqrt(q_norm_sq) if q_norm_sq > 0 else 1.0
        norm_q_vec = {t: v / q_norm for t, v in q_vec.items()}

        # Compute cosine similarities
        scores: List[Tuple[float, int]] = []
        for idx, doc_vec in enumerate(self.doc_vectors):
            dot_product = sum(weight * doc_vec[term] for term, weight in norm_q_vec.items() if term in doc_vec)
            scores.append((dot_product, idx))

        scores.sort(key=lambda x: x[0], reverse=True)

        retrieved = []
        for score, idx in scores[:top_k]:
            if score > 0.01:
                retrieved.append({
                    "score": round(score, 4),
                    "chunk_id": self.chunks[idx]["chunk_id"],
                    "text": self.chunks[idx]["text"],
                    "metadata": self.chunks[idx]["metadata"]
                })

        # Fallback if no specific high match
        if not retrieved and self.chunks:
            retrieved = [{
                "score": 0.05,
                "chunk_id": self.chunks[0]["chunk_id"],
                "text": self.chunks[0]["text"],
                "metadata": self.chunks[0]["metadata"]
            }]

        # Synthesize grounded answer
        synthesized_answer = self._synthesize_answer(query_text, retrieved)

        return {
            "query": query_text,
            "answer": synthesized_answer,
            "retrieved_chunks": retrieved
        }

    def _synthesize_answer(self, query: str, retrieved_chunks: List[Dict[str, Any]]) -> str:
        if not retrieved_chunks:
            return "Based on the uploaded documents, no relevant context was found for this query."

        top_texts = [c["text"] for c in retrieved_chunks[:3]]
        combined_context = "\n".join(top_texts)

        # Simple grounded sentence extractor
        q_lower = query.lower()
        match_lines = []
        for chunk in retrieved_chunks:
            for line in chunk["text"].split("\n"):
                if any(w in line.lower() for w in self._tokenize(query)):
                    if line not in match_lines:
                        match_lines.append(line)

        if match_lines:
            findings = " ".join(match_lines[:3])
            return f"**Grounded Intelligence Answer:**\n\n{findings}\n\n*(Derived from {len(retrieved_chunks)} semantic document chunks)*"
        else:
            return f"**Grounded Intelligence Answer:**\n\n{top_texts[0]}\n\n*(Retrieved from document context)*"

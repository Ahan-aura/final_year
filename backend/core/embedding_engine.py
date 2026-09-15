"""
Semantic Vector and Embedding Engine for Skill Discovery.
Provides deterministic vector embeddings, cosine similarity,
and domain taxonomy keyword matching.
"""

import re
import math
from typing import List, Dict, Any, Optional

TAXONOMY_KEYWORDS = {
    # Tabular Cleaning Keywords
    "impute": 3.0, "missing": 3.0, "nan": 2.5, "null": 2.5, "median": 2.2, "mean": 2.2,
    "coerce": 3.0, "type": 2.5, "cast": 2.5, "currency": 2.5, "dollar": 2.0, "numeric": 2.0,
    "duplicate": 3.0, "dedup": 3.0, "unique": 2.0, "repeated": 2.0, "drop_duplicates": 2.5,
    "outlier": 3.0, "iqr": 3.0, "zscore": 2.5, "cap": 2.0, "quantile": 2.0, "fence": 2.0,
    "column": 2.5, "header": 2.5, "snake_case": 3.0, "standardize": 2.0, "lowercase": 2.0,
    "date": 3.0, "datetime": 3.0, "timestamp": 2.5, "iso8601": 2.5, "parse": 2.0, "format": 2.0,
    
    # Code Debugging Keywords
    "off_by_one": 3.0, "boundary": 2.5, "index": 2.5, "slice": 2.0, "range": 2.0, "length": 2.0,
    "keyerror": 3.0, "attributeerror": 3.0, "none": 2.5, "optional": 2.0, "lookup": 2.0, "null": 2.0,
    "mismatch": 3.0, "str": 2.0, "int": 2.0, "concat": 2.0, "float": 2.0, "conversion": 2.0,
    "loop": 3.0, "termination": 2.5, "infinite": 3.0, "while": 2.5, "advance": 2.0, "decrement": 2.0,
    "operator": 3.0, "logical": 2.5, "inversion": 2.5, "and": 1.8, "or": 1.8, "equality": 2.0,
    "zero_division": 3.0, "zerodivisionerror": 3.0, "empty": 2.5, "base_case": 2.5, "recursion": 2.5
}

class EmbeddingEngine:
    """Calculates dense semantic representations and cosine similarities."""

    def __init__(self, vector_dim: int = 128):
        self.vector_dim = vector_dim

    def _tokenize(self, text: str) -> List[str]:
        cleaned = re.sub(r"[^a-zA-Z0-9_]+", " ", text.lower())
        tokens = [t for t in cleaned.split() if len(t) > 1]
        bigrams = [f"{tokens[i]}_{tokens[i+1]}" for i in range(len(tokens) - 1)]
        return tokens + bigrams

    def compute_embedding(self, text: str) -> List[float]:
        if not text:
            return [0.0] * self.vector_dim

        tokens = self._tokenize(text)
        vec = [0.0] * self.vector_dim

        for token in tokens:
            weight = TAXONOMY_KEYWORDS.get(token, 1.0)
            h = hash(token)
            idx1 = abs(h) % self.vector_dim
            idx2 = abs((h >> 8) ^ 0x5bd1e995) % self.vector_dim
            vec[idx1] += weight
            vec[idx2] += (weight * 0.5)

        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 1e-9:
            vec = [round(x / norm, 5) for x in vec]
        else:
            vec = [0.0] * self.vector_dim

        return vec

    @staticmethod
    def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        dot = sum(a * b for a, b in zip(vec1, vec2))
        return max(0.0, min(1.0, float(dot)))

    def semantic_similarity(self, query: str, target: str, target_vec: Optional[List[float]] = None) -> float:
        q_vec = self.compute_embedding(query)
        if target_vec is None or len(target_vec) != len(q_vec):
            target_vec = self.compute_embedding(target)

        cos_sim = self.cosine_similarity(q_vec, target_vec)

        q_tokens = set(self._tokenize(query))
        t_tokens = set(self._tokenize(target))
        if q_tokens and t_tokens:
            jaccard = len(q_tokens & t_tokens) / float(len(q_tokens | t_tokens))
        else:
            jaccard = 0.0

        hybrid = (0.70 * cos_sim) + (0.30 * jaccard)
        return round(hybrid, 4)

_engine = None

def get_embedding_engine() -> EmbeddingEngine:
    global _engine
    if _engine is None:
        _engine = EmbeddingEngine()
    return _engine
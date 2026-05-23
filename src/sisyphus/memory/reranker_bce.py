import logging
import os
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

_BCE_PATH = os.path.expanduser("~/.cache/modelscope/maidalun/bce-reranker-base_v1")


class BCERerankerSimple:
    def __init__(self, model_path: str = _BCE_PATH):
        self._model_path = model_path
        self._tokenizer = None
        self._model = None

    def _ensure_loaded(self) -> bool:
        if self._model is not None:
            return True
        if not os.path.isdir(self._model_path):
            logger.warning("BCE model not found at %s", self._model_path)
            return False
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(self._model_path, trust_remote_code=True)
            self._model = AutoModelForSequenceClassification.from_pretrained(self._model_path, trust_remote_code=True)
            self._model.eval()
            logger.info("BCE reranker loaded (%s)", self._model_path)
            return True
        except Exception as exc:
            logger.warning("Failed to load BCE: %s", exc)
            return False

    def rerank(self, query: str, documents: List[str], top_k: Optional[int] = None) -> List[Tuple[int, float]]:
        if not self._ensure_loaded():
            return list(enumerate([0.0] * len(documents)))
        try:
            import torch
            pairs = [[query, doc] for doc in documents]
            enc = self._tokenizer(pairs, padding=True, truncation=True, return_tensors="pt", max_length=512)
            with torch.no_grad():
                scores = self._model(**enc).logits.squeeze(-1).tolist()
            if isinstance(scores, float):
                scores = [scores]
            indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
            if top_k is not None:
                indexed = indexed[:top_k]
            return indexed
        except Exception as exc:
            logger.warning("BCE rerank failed: %s", exc)
            return list(enumerate([0.0] * len(documents)))

    def close(self):
        self._model = None
        self._tokenizer = None

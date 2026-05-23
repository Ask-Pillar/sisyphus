"""Tests for BGEReranker — cross-encoder reranker wrapper."""

import pytest
from unittest.mock import patch, MagicMock
from sisyphus.memory.retrieval import BGEReranker


class TestBGERerankerInit:
    def test_default_model_path(self):
        reranker = BGEReranker()
        assert reranker._model_path.endswith("bge-reranker-v2-m3")
        assert reranker._model is None

    def test_custom_path(self):
        reranker = BGEReranker(model_path="/tmp/custom-model")
        assert reranker._model_path == "/tmp/custom-model"


class TestBGERerankerEnsureLoaded:
    def test_already_loaded_returns_true(self):
        reranker = BGEReranker()
        reranker._model = MagicMock()
        reranker._tokenizer = MagicMock()
        assert reranker._ensure_loaded() is True

    def test_missing_directory_returns_false(self, tmp_path):
        missing = str(tmp_path / "nonexistent_model")
        reranker = BGEReranker(model_path=missing)
        assert reranker._ensure_loaded() is False

    @patch("os.path.isdir", return_value=True)
    @patch("torch.backends.mps.is_available", return_value=False)
    @patch("torch.cuda.is_available", return_value=False)
    def test_loads_on_cpu_when_no_accelerator(self, mock_cuda, mock_mps, mock_isdir):
        mock_model = MagicMock()
        mock_tokenizer = MagicMock()
        mock_auto = MagicMock()
        mock_auto.from_pretrained.return_value = mock_model
        # Inject mocks into sys.modules so the local import picks them up
        import sys
        mock_transformers = MagicMock()
        mock_transformers.AutoModelForSequenceClassification = mock_auto
        mock_transformers.AutoTokenizer = MagicMock()
        mock_transformers.AutoTokenizer.from_pretrained.return_value = mock_tokenizer
        with patch.dict("sys.modules", {"transformers": mock_transformers}):
            reranker = BGEReranker(model_path="/fake/model")
            result = reranker._ensure_loaded()
            assert result is True
            assert reranker._device == "cpu"

    @patch("os.path.isdir", return_value=True)
    def test_failed_import_falls_back(self, mock_isdir):
        reranker = BGEReranker(model_path="/fake/model")
        result = reranker._ensure_loaded()
        assert result is False


class TestBGERerankerRerank:
    def test_fallback_on_missing_model(self):
        reranker = BGEReranker(model_path="/nonexistent")
        docs = ["doc1", "doc2", "doc3"]
        result = reranker.rerank("test query", docs)
        assert len(result) == 3
        assert all(score == 0.0 for _, score in result)

    def test_returns_indexed_scores_sorted(self):
        reranker = BGEReranker()
        reranker._model = MagicMock()
        reranker._tokenizer = MagicMock()
        reranker._device = "cpu"
        # Simulate tokenizer output
        reranker._tokenizer.return_value = {"input_ids": MagicMock(), "attention_mask": MagicMock()}
        # Simulate model output with logits
        mock_logits = MagicMock()
        mock_logits.squeeze.return_value.cpu.return_value.tolist.return_value = [0.1, 0.9, 0.5]
        reranker._model.return_value = MagicMock(logits=mock_logits)
        docs = ["bad", "good", "ok"]
        result = reranker.rerank("query", docs, top_k=3)
        indices = [i for i, _ in result]
        assert indices == [1, 2, 0], f"expected [1,2,0] got {indices}"

    def test_single_score_wrapped_to_list(self):
        reranker = BGEReranker()
        reranker._model = MagicMock()
        reranker._tokenizer = MagicMock()
        reranker._device = "cpu"
        reranker._tokenizer.return_value = {"input_ids": MagicMock(), "attention_mask": MagicMock()}
        mock_logits = MagicMock()
        mock_logits.squeeze.return_value.cpu.return_value.tolist.return_value = 0.42
        reranker._model.return_value = MagicMock(logits=mock_logits)
        docs = ["only"]
        result = reranker.rerank("query", docs)
        assert len(result) == 1
        assert result[0][1] == 0.42

    def test_top_k_limits_results(self):
        reranker = BGEReranker()
        reranker._model = MagicMock()
        reranker._tokenizer = MagicMock()
        reranker._device = "cpu"
        reranker._tokenizer.return_value = {"input_ids": MagicMock(), "attention_mask": MagicMock()}
        mock_logits = MagicMock()
        mock_logits.squeeze.return_value.cpu.return_value.tolist.return_value = [0.8, 0.6, 0.9, 0.7]
        reranker._model.return_value = MagicMock(logits=mock_logits)
        docs = ["a", "b", "c", "d"]
        result = reranker.rerank("query", docs, top_k=2)
        top_scores = [s for _, s in result]
        assert top_scores == [0.9, 0.8]
        assert len(result) == 2

    def test_instruction_param_ignored(self):
        reranker = BGEReranker()
        reranker._model = MagicMock()
        reranker._tokenizer = MagicMock()
        reranker._device = "cpu"
        reranker._tokenizer.return_value = {"input_ids": MagicMock(), "attention_mask": MagicMock()}
        mock_logits = MagicMock()
        mock_logits.squeeze.return_value.cpu.return_value.tolist.return_value = [0.5, 0.5]
        reranker._model.return_value = MagicMock(logits=mock_logits)
        result = reranker.rerank("query", ["a", "b"], instruction="irrelevant")
        assert len(result) == 2

    def test_exception_during_rerank_falls_back(self):
        reranker = BGEReranker()
        reranker._model = MagicMock()
        reranker._tokenizer = MagicMock()
        reranker._device = "cpu"
        reranker._tokenizer.side_effect = RuntimeError("OOM")
        docs = ["doc1", "doc2"]
        result = reranker.rerank("query", docs)
        assert all(score == 0.0 for _, score in result)


class TestBGERerankerClose:
    def test_close_sets_model_none(self):
        reranker = BGEReranker()
        reranker._model = MagicMock()
        reranker._tokenizer = MagicMock()
        reranker.close()
        assert reranker._model is None
        assert reranker._tokenizer is None


class TestBGERerankerIntegrationWithContextRetriever:
    """Verify duck-type compatibility with ContextRetriever.reranker slot."""

    def test_has_rerank_method(self):
        reranker = BGEReranker()
        assert hasattr(reranker, "rerank")
        assert callable(reranker.rerank)

    def test_rerank_signature_matches_qwen3_interface(self):
        import inspect
        sig = inspect.signature(BGEReranker.rerank)
        params = list(sig.parameters.keys())
        assert "query" in params
        assert "documents" in params
        assert "top_k" in params
        assert "instruction" in params

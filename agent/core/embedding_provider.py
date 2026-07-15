"""Embedding providers for knowledge vectorization.

The preferred provider calls the Kylin system embedding SDK
(`kysdk-coreai-embedding`) through ctypes.  Development machines that do not
have the SDK installed fall back to a deterministic local hashing embedder so
the knowledge base remains usable and testable.
"""

import ctypes
import ctypes.util
import hashlib
import math
import os
import re
from typing import Dict, List, Optional


class EmbeddingError(RuntimeError):
    """Raised when an embedding provider cannot produce a vector."""


class BaseEmbeddingProvider:
    """Common embedding provider interface."""

    name = "base"
    dimension = 0

    def embed(self, text: str) -> List[float]:
        """Return an embedding vector for text."""
        raise NotImplementedError

    def status(self) -> Dict[str, object]:
        """Return provider status for diagnostics and reports."""
        return {
            "provider": self.name,
            "dimension": self.dimension,
            "available": True,
        }


class HashEmbeddingProvider(BaseEmbeddingProvider):
    """Deterministic lightweight fallback embedder.

    This is not a semantic embedding model.  It keeps development and unit tests
    working when the Kylin runtime is unavailable, while preserving the same
    vector storage/search path used by the system SDK provider.
    """

    name = "hash-fallback"

    def __init__(self, dimension: int = 384, fallback_reason: str = ""):
        self.dimension = dimension
        self.fallback_reason = fallback_reason

    def status(self) -> Dict[str, object]:
        status = super().status()
        if self.fallback_reason:
            status["fallback_reason"] = self.fallback_reason
        return status

    def embed(self, text: str) -> List[float]:
        vector = [0.0] * self.dimension
        tokens = re.findall(r"[\w\u4e00-\u9fff]+", text.lower())
        if not tokens:
            tokens = [text.lower() or "empty"]

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for offset in range(0, min(len(digest), 24), 3):
                idx = int.from_bytes(digest[offset : offset + 2], "little") % self.dimension
                sign = 1.0 if digest[offset + 2] % 2 == 0 else -1.0
                vector[idx] += sign

        return _normalize(vector)


class KylinTextEmbeddingProvider(BaseEmbeddingProvider):
    """Text embedding provider backed by Kylin's core AI embedding SDK."""

    name = "kylin-coreai-embedding"
    REQUIRED_FUNCTIONS = (
        "text_embedding_create_session",
        "text_embedding_destroy_session",
        "text_embedding_init_session",
        "text_embedding",
        "embedding_result_get_vector_data",
        "embedding_result_get_vector_length",
        "embedding_result_get_error_code",
        "embedding_result_get_error_message",
        "embedding_result_destroy",
    )
    LIBRARY_CANDIDATES = (
        "kysdk-coreai-embedding",
        "libkysdk-coreai-embedding.so",
        "libkysdk-coreai-embedding.so.1",
    )

    def __init__(self, library_path: Optional[str] = None, model_name: Optional[str] = None):
        self.library_path = library_path or os.getenv("KYLIN_EMBEDDING_LIBRARY")
        self.model_name = model_name or os.getenv("KYLIN_EMBEDDING_MODEL")
        self.loaded_library = ""
        self._lib = self._load_library()
        self._session = None
        self.dimension = 0
        self._configure_functions()
        self._init_session()

    def _load_library(self):
        candidates = []
        if self.library_path:
            candidates.append(self.library_path)

        for name in self.LIBRARY_CANDIDATES:
            resolved = ctypes.util.find_library(name)
            if resolved:
                candidates.append(resolved)
            candidates.append(name)

        errors = []
        for candidate in candidates:
            try:
                lib = ctypes.CDLL(candidate)
                self.loaded_library = candidate
                return lib
            except OSError as exc:
                errors.append(f"{candidate}: {exc}")

        raise EmbeddingError("Kylin embedding SDK library not found: " + "; ".join(errors))

    def _configure_functions(self) -> None:
        lib = self._lib
        missing = [name for name in self.REQUIRED_FUNCTIONS if not hasattr(lib, name)]
        if missing:
            raise EmbeddingError(
                "Kylin embedding SDK missing required symbols: " + ", ".join(missing)
            )

        lib.text_embedding_create_session.argtypes = []
        lib.text_embedding_create_session.restype = ctypes.c_void_p

        lib.text_embedding_destroy_session.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
        lib.text_embedding_destroy_session.restype = None

        lib.text_embedding_init_session.argtypes = [ctypes.c_void_p]
        lib.text_embedding_init_session.restype = ctypes.c_int

        if hasattr(lib, "text_embedding_init_model"):
            lib.text_embedding_init_model.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
            lib.text_embedding_init_model.restype = ctypes.c_int

        lib.text_embedding.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        lib.text_embedding.restype = ctypes.c_bool

        lib.embedding_result_get_vector_data.argtypes = [ctypes.c_void_p]
        lib.embedding_result_get_vector_data.restype = ctypes.POINTER(ctypes.c_float)

        lib.embedding_result_get_vector_length.argtypes = [ctypes.c_void_p]
        lib.embedding_result_get_vector_length.restype = ctypes.c_int

        lib.embedding_result_get_error_code.argtypes = [ctypes.c_void_p]
        lib.embedding_result_get_error_code.restype = ctypes.c_int

        lib.embedding_result_get_error_message.argtypes = [ctypes.c_void_p]
        lib.embedding_result_get_error_message.restype = ctypes.c_char_p

        lib.embedding_result_destroy.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
        lib.embedding_result_destroy.restype = None

        if hasattr(lib, "text_embedding_enable_internal_event_loop"):
            lib.text_embedding_enable_internal_event_loop.argtypes = [
                ctypes.c_void_p,
                ctypes.c_bool,
            ]
            lib.text_embedding_enable_internal_event_loop.restype = None

        if hasattr(lib, "text_embedding_get_model_list"):
            lib.text_embedding_get_model_list.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_int),
            ]
            lib.text_embedding_get_model_list.restype = ctypes.c_void_p

            lib.embedding_model_list_get_count.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_int),
            ]
            lib.embedding_model_list_get_count.restype = ctypes.c_int

            lib.embedding_model_list_get_model.argtypes = [
                ctypes.c_void_p,
                ctypes.c_int,
                ctypes.POINTER(ctypes.c_int),
            ]
            lib.embedding_model_list_get_model.restype = ctypes.c_void_p

            lib.embedding_model_info_get_model_name.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_int),
            ]
            lib.embedding_model_info_get_model_name.restype = ctypes.c_char_p

            lib.embedding_model_info_get_model_dim.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_int),
            ]
            lib.embedding_model_info_get_model_dim.restype = ctypes.c_int

    def _init_session(self) -> None:
        session = self._lib.text_embedding_create_session()
        if not session:
            raise EmbeddingError("text_embedding_create_session returned null")
        self._session = ctypes.c_void_p(session)

        if hasattr(self._lib, "text_embedding_enable_internal_event_loop"):
            self._lib.text_embedding_enable_internal_event_loop(self._session, True)

        code = self._lib.text_embedding_init_session(self._session)
        if code != 0:
            self.close()
            raise EmbeddingError(f"text_embedding_init_session failed: {code}")

        if self.model_name and hasattr(self._lib, "text_embedding_init_model"):
            model_code = self._lib.text_embedding_init_model(
                self._session, self.model_name.encode("utf-8")
            )
            if model_code != 0:
                self.close()
                raise EmbeddingError(
                    f"text_embedding_init_model({self.model_name}) failed: {model_code}"
                )
        elif self.model_name:
            raise EmbeddingError(
                "KYLIN_EMBEDDING_MODEL is set, but SDK has no text_embedding_init_model symbol"
            )

        self.dimension = self._detect_dimension()

    def _detect_dimension(self) -> int:
        if not hasattr(self._lib, "text_embedding_get_model_list"):
            return 0

        error_code = ctypes.c_int(0)
        model_list = self._lib.text_embedding_get_model_list(
            self._session, ctypes.byref(error_code)
        )
        if not model_list or error_code.value != 0:
            return 0

        count = self._lib.embedding_model_list_get_count(
            model_list, ctypes.byref(error_code)
        )
        if count <= 0 or error_code.value != 0:
            return 0

        selected_name = self.model_name
        for index in range(count):
            model = self._lib.embedding_model_list_get_model(
                model_list, index, ctypes.byref(error_code)
            )
            if not model or error_code.value != 0:
                continue
            name_raw = self._lib.embedding_model_info_get_model_name(
                model, ctypes.byref(error_code)
            )
            name = name_raw.decode("utf-8") if name_raw else ""
            dim = self._lib.embedding_model_info_get_model_dim(
                model, ctypes.byref(error_code)
            )
            if selected_name is None or selected_name == name:
                if selected_name is None and name:
                    self.model_name = name
                return dim
        return 0

    def embed(self, text: str) -> List[float]:
        if not self._session:
            raise EmbeddingError("Kylin embedding session is not initialized")

        result = ctypes.c_void_p()
        ok = self._lib.text_embedding(
            self._session, text.encode("utf-8"), ctypes.byref(result)
        )
        if not ok or not result:
            raise EmbeddingError("text_embedding call failed")

        try:
            error_code = self._lib.embedding_result_get_error_code(result)
            if error_code != 0:
                message_raw = self._lib.embedding_result_get_error_message(result)
                message = message_raw.decode("utf-8") if message_raw else ""
                raise EmbeddingError(f"text_embedding returned {error_code}: {message}")

            length = self._lib.embedding_result_get_vector_length(result)
            data = self._lib.embedding_result_get_vector_data(result)
            if length <= 0 or not data:
                raise EmbeddingError("text_embedding returned an empty vector")

            vector = [float(data[index]) for index in range(length)]
            if not self.dimension:
                self.dimension = length
            return _normalize(vector)
        finally:
            self._lib.embedding_result_destroy(ctypes.byref(result))

    def status(self) -> Dict[str, object]:
        return {
            "provider": self.name,
            "dimension": self.dimension,
            "available": True,
            "library": self.loaded_library or self.library_path or "libkysdk-coreai-embedding.so",
            "model": self.model_name or "default",
        }

    def close(self) -> None:
        if self._session:
            self._lib.text_embedding_destroy_session(ctypes.byref(self._session))
            self._session = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


def create_embedding_provider() -> BaseEmbeddingProvider:
    """Create the best available embedding provider.

    Set MINIBOT_EMBEDDING_PROVIDER=hash to force the deterministic fallback.
    Set MINIBOT_EMBEDDING_PROVIDER=kylin to fail fast when the system SDK is unavailable.
    """
    provider_name = os.getenv("MINIBOT_EMBEDDING_PROVIDER", "auto").strip().lower()
    if provider_name == "hash":
        return HashEmbeddingProvider()

    try:
        return KylinTextEmbeddingProvider()
    except Exception as exc:
        if provider_name == "kylin":
            raise
        reason = str(exc).split("; ", 1)[0]
        if len(reason) > 180:
            reason = reason[:180] + "..."
        print(f"[Embedding] Kylin SDK unavailable, fallback to hash: {reason}")
        return HashEmbeddingProvider(fallback_reason=str(exc))


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity for two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def vector_hash(text: str) -> str:
    """Stable hash for vectorized text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize(vector: List[float]) -> List[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm <= 0:
        return vector
    return [value / norm for value in vector]

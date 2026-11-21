import hashlib
import math
import re
from collections import Counter

import httpx

from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError


LOCAL_MODEL = "dealerdesk-hash-v1"
LOCAL_DIMENSIONS = 384
WORD_PATTERN = re.compile(r"[a-z0-9]+")


def model_name() -> str:
    settings = get_settings()
    if settings.embedding_api_url:
        provider_id = hashlib.sha256(
            f"{settings.embedding_api_url}\0{settings.embedding_model}".encode("utf-8")
        ).hexdigest()[:24]
        return f"remote-{provider_id}"
    return LOCAL_MODEL


def embed_texts(texts: list[str]) -> list[list[float]]:
    settings = get_settings()
    if not settings.embedding_api_url:
        return [_local_embedding(text) for text in texts]

    payload: dict[str, object] = {
        "model": settings.embedding_model,
        "input": texts,
    }
    headers = {"Content-Type": "application/json"}
    if settings.embedding_api_key:
        headers["Authorization"] = (
            f"Bearer {settings.embedding_api_key.get_secret_value()}"
        )

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                settings.embedding_api_url,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            result = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ServiceUnavailableError("The embedding provider is unavailable") from exc

    try:
        items = result["data"]
        vectors = [item["embedding"] for item in items]
        if len(vectors) != len(texts) or any(
            not vector
            or any(
                not isinstance(value, (int, float)) or not math.isfinite(value)
                for value in vector
            )
            for vector in vectors
        ):
            raise ValueError("Invalid embedding response")
        return [[float(value) for value in vector] for vector in vectors]
    except (KeyError, TypeError, ValueError) as exc:
        raise ServiceUnavailableError(
            "The embedding provider returned an invalid response"
        ) from exc


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (
        left_norm * right_norm
    )


def _local_embedding(text: str) -> list[float]:
    words = WORD_PATTERN.findall(text.casefold())
    features = Counter(words)
    features.update(
        f"{left}_{right}" for left, right in zip(words, words[1:], strict=False)
    )
    vector = [0.0] * LOCAL_DIMENSIONS
    for feature, count in features.items():
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        hashed = int.from_bytes(digest, "big")
        index = hashed % LOCAL_DIMENSIONS
        sign = 1.0 if hashed & (1 << 63) else -1.0
        vector[index] += sign * (1.0 + math.log(count))
    return vector

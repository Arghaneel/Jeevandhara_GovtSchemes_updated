"""Password hashing with the standard library (PBKDF2-SHA256)."""

import hashlib
import hmac
import secrets

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 260_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), ITERATIONS
    ).hex()
    return f"{ALGORITHM}${ITERATIONS}${salt}${digest}"


def is_hashed(stored) -> bool:
    return isinstance(stored, str) and stored.startswith(ALGORITHM + "$")


def verify_password(password: str, stored) -> bool:
    if not stored:
        return False

    if not is_hashed(stored):
        # Account created before hashing was added (plain-text password).
        return hmac.compare_digest(password.encode("utf-8"), str(stored).encode("utf-8"))

    try:
        _, iterations, salt, digest = stored.split("$", 3)
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations)
        ).hex()
    except (ValueError, TypeError):
        return False

    return hmac.compare_digest(candidate, digest)

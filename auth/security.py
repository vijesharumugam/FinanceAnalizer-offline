"""Password and session helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Any, Dict, Optional

import streamlit as st


class SecurityManager:
    """Encapsulates password hashing and Streamlit session access."""

    SESSION_KEY = "current_user"
    PBKDF2_SCHEME = "pbkdf2_sha256"
    PBKDF2_ITERATIONS = 390000
    SALT_BYTES = 16

    def __init__(self) -> None:
        pass

    def _hash_password_pbkdf2(self, password: str) -> str:
        salt = os.urandom(self.SALT_BYTES)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            self.PBKDF2_ITERATIONS,
        )
        salt_b64 = base64.b64encode(salt).decode("ascii")
        digest_b64 = base64.b64encode(digest).decode("ascii")
        return f"{self.PBKDF2_SCHEME}${self.PBKDF2_ITERATIONS}${salt_b64}${digest_b64}"

    def _verify_password_pbkdf2(self, password: str, password_hash: str) -> bool:
        try:
            scheme, iterations_text, salt_b64, digest_b64 = password_hash.split("$", 3)
        except ValueError:
            return False

        if scheme != self.PBKDF2_SCHEME:
            return False

        try:
            iterations = int(iterations_text)
            salt = base64.b64decode(salt_b64.encode("ascii"))
            expected_digest = base64.b64decode(digest_b64.encode("ascii"))
        except (ValueError, TypeError):
            return False

        actual_digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations,
        )
        return hmac.compare_digest(actual_digest, expected_digest)

    def hash_password(self, password: str) -> str:
        return self._hash_password_pbkdf2(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        if password_hash.startswith(f"{self.PBKDF2_SCHEME}$"):
            return self._verify_password_pbkdf2(password, password_hash)
        return False

    def login_user(self, user: Dict[str, Any]) -> None:
        st.session_state[self.SESSION_KEY] = {
            "id": user["id"],
            "full_name": user["full_name"],
            "email": user["email"],
            "username": user["username"],
        }

    def logout_user(self) -> None:
        st.session_state.pop(self.SESSION_KEY, None)

    def get_current_user(self) -> Optional[Dict[str, Any]]:
        return st.session_state.get(self.SESSION_KEY)

    def is_authenticated(self) -> bool:
        return self.SESSION_KEY in st.session_state

from __future__ import annotations

import hashlib
import hmac
import secrets
import string
from typing import Any

import bcrypt
import phonenumbers
import streamlit as st
from phonenumbers import NumberParseException

from core.constants import (
    DEFAULT_PHONE_REGION,
    MAX_MOBILE_DIGITS,
    MINIMUM_PASSWORD_LENGTH,
    MIN_MOBILE_DIGITS,
    OTP_LENGTH,
)


# ============================================================
# PASSWORD HELPERS
# ============================================================

def validate_password(password: str) -> list[str]:
    """
    Return validation errors for a new password.
    """

    errors: list[str] = []

    if len(password) < MINIMUM_PASSWORD_LENGTH:
        errors.append(
            f"Password must contain at least "
            f"{MINIMUM_PASSWORD_LENGTH} characters."
        )

    if not any(character.isalpha() for character in password):
        errors.append(
            "Password must contain at least one letter."
        )

    if not any(character.isdigit() for character in password):
        errors.append(
            "Password must contain at least one number."
        )

    if len(password.encode("utf-8")) > 72:
        errors.append(
            "Password is too long. Use fewer than 72 UTF-8 bytes."
        )

    return errors


def hash_password(password: str) -> str:
    """
    Create a bcrypt password hash.
    """

    errors = validate_password(password)

    if errors:
        raise ValueError(" ".join(errors))

    password_bytes = password.encode("utf-8")

    return bcrypt.hashpw(
        password_bytes,
        bcrypt.gensalt(rounds=12),
    ).decode("utf-8")


def verify_password(
    password: str,
    stored_hash: str,
) -> bool:
    """
    Verify a plain password against a bcrypt hash.
    """

    if not password or not stored_hash:
        return False

    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            stored_hash.encode("utf-8"),
        )
    except (
        ValueError,
        TypeError,
        UnicodeEncodeError,
    ):
        return False


# ============================================================
# OTP HELPERS
# ============================================================

def generate_numeric_otp(
    length: int = OTP_LENGTH,
) -> str:
    """
    Generate a cryptographically secure numeric OTP.
    """

    if length < 4 or length > 10:
        raise ValueError(
            "OTP length must be between 4 and 10 digits."
        )

    return "".join(
        secrets.choice(string.digits)
        for _ in range(length)
    )


def get_otp_secret() -> bytes:
    """
    Get a private secret used to HMAC OTP values.

    OTP_PEPPER is recommended. The service-role key is used
    as a fallback so existing installations continue working.
    """

    secret_value = str(
        st.secrets.get(
            "OTP_PEPPER",
            st.secrets.get(
                "SUPABASE_SERVICE_ROLE_KEY",
                "",
            ),
        )
    ).strip()

    if not secret_value:
        raise RuntimeError(
            "OTP_PEPPER or SUPABASE_SERVICE_ROLE_KEY "
            "must be configured."
        )

    return secret_value.encode("utf-8")


def hash_otp(
    otp: str,
    registration_id: str,
) -> str:
    """
    Create a registration-bound HMAC hash for an OTP.
    """

    clean_otp = otp.strip()

    if not clean_otp.isdigit():
        raise ValueError(
            "OTP must contain only digits."
        )

    payload = (
        f"{registration_id}:{clean_otp}"
    ).encode("utf-8")

    return hmac.new(
        get_otp_secret(),
        payload,
        hashlib.sha256,
    ).hexdigest()


def verify_otp(
    otp: str,
    registration_id: str,
    stored_hash: str,
) -> bool:
    """
    Verify an OTP without exposing timing differences.
    """

    if not otp or not registration_id or not stored_hash:
        return False

    try:
        candidate_hash = hash_otp(
            otp,
            registration_id,
        )
    except ValueError:
        return False

    return hmac.compare_digest(
        candidate_hash,
        stored_hash,
    )


# ============================================================
# MOBILE NUMBER HELPERS
# ============================================================

def normalize_mobile_number(
    mobile_number: str,
    default_region: str = DEFAULT_PHONE_REGION,
) -> str:
    """
    Validate and return a mobile number in E.164 format.
    """

    clean_number = (
        mobile_number
        .strip()
        .replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )

    digits_only = "".join(
        character
        for character in clean_number
        if character.isdigit()
    )

    if not (
        MIN_MOBILE_DIGITS
        <= len(digits_only)
        <= MAX_MOBILE_DIGITS
    ):
        raise ValueError(
            "Enter a valid mobile number containing "
            f"{MIN_MOBILE_DIGITS} to {MAX_MOBILE_DIGITS} digits."
        )

    try:
        parsed_number = phonenumbers.parse(
            clean_number,
            default_region,
        )
    except NumberParseException as error:
        raise ValueError(
            "Enter a valid mobile number."
        ) from error

    if not phonenumbers.is_possible_number(
        parsed_number
    ):
        raise ValueError(
            "The mobile number is not possible."
        )

    if not phonenumbers.is_valid_number(
        parsed_number
    ):
        raise ValueError(
            "The mobile number is not valid."
        )

    return phonenumbers.format_number(
        parsed_number,
        phonenumbers.PhoneNumberFormat.E164,
    )


def mobile_number_is_valid(
    mobile_number: str,
    default_region: str = DEFAULT_PHONE_REGION,
) -> bool:
    try:
        normalize_mobile_number(
            mobile_number,
            default_region,
        )
        return True
    except ValueError:
        return False


def mask_mobile_number(
    mobile_number: str | None,
) -> str:
    """
    Mask a mobile number for password-reset confirmation.
    """

    if not mobile_number:
        return "Not available"

    clean_number = str(mobile_number).strip()

    if len(clean_number) <= 4:
        return "*" * len(clean_number)

    return (
        "*" * (len(clean_number) - 4)
        + clean_number[-4:]
    )


def mask_email(
    email: str | None,
) -> str:
    """
    Mask an email address while preserving recognition.
    """

    if not email or "@" not in email:
        return "Not available"

    local_part, domain = email.split(
        "@",
        maxsplit=1,
    )

    if len(local_part) <= 2:
        masked_local = (
            local_part[0]
            + "*"
            if local_part
            else "*"
        )
    else:
        masked_local = (
            local_part[0]
            + "*" * (len(local_part) - 2)
            + local_part[-1]
        )

    return f"{masked_local}@{domain}"


# ============================================================
# GENERAL SECURITY HELPERS
# ============================================================

def generate_secure_token(
    byte_length: int = 24,
) -> str:
    if byte_length < 16:
        raise ValueError(
            "Secure tokens must use at least 16 bytes."
        )

    return secrets.token_urlsafe(
        byte_length
    )


def secure_compare(
    first_value: Any,
    second_value: Any,
) -> bool:
    return hmac.compare_digest(
        str(first_value),
        str(second_value),
    )
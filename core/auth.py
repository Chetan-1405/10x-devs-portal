import bcrypt


def hash_password(password: str) -> str:
    """Create a secure bcrypt hash for a student password."""

    password_bytes = password.encode("utf-8")

    hashed_password = bcrypt.hashpw(
        password_bytes,
        bcrypt.gensalt(),
    )

    return hashed_password.decode("utf-8")


def verify_password(
    password: str,
    stored_hash: str,
) -> bool:
    """Compare the entered password with the stored bcrypt hash."""

    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            stored_hash.encode("utf-8"),
        )

    except (ValueError, TypeError, AttributeError):
        return False
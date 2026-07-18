from __future__ import annotations

from typing import Any

import streamlit as st
from supabase import Client, create_client


@st.cache_resource
def get_supabase() -> Client:
    """Create one reusable Supabase client."""

    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_SERVICE_ROLE_KEY"],
    )


def find_duplicate_registration(
    registration_number: str,
    email: str,
) -> str | None:
    database = get_supabase()

    registration_result = (
        database.table("registrations")
        .select("id")
        .eq(
            "registration_number",
            registration_number,
        )
        .limit(1)
        .execute()
    )

    if registration_result.data:
        return (
            "This registration number has already "
            "been registered."
        )

    email_result = (
        database.table("registrations")
        .select("id")
        .eq("email", email)
        .limit(1)
        .execute()
    )

    if email_result.data:
        return (
            "This email address has already been registered."
        )

    return None


def create_registration(
    registration_data: dict[str, Any],
) -> dict[str, Any]:
    result = (
        get_supabase()
        .table("registrations")
        .insert(registration_data)
        .execute()
    )

    if not result.data:
        raise RuntimeError(
            "The registration was not created."
        )

    return result.data[0]


def get_student(
    registration_number: str,
) -> dict[str, Any] | None:
    result = (
        get_supabase()
        .table("registrations")
        .select("*")
        .eq(
            "registration_number",
            registration_number,
        )
        .limit(1)
        .execute()
    )

    if not result.data:
        return None

    return result.data[0]


def update_registration(
    registration_id: str,
    values: dict[str, Any],
) -> None:
    (
        get_supabase()
        .table("registrations")
        .update(values)
        .eq("id", registration_id)
        .execute()
    )


def get_proof_submission(
    registration_id: str,
) -> dict[str, Any] | None:
    result = (
        get_supabase()
        .table("proof_submissions")
        .select("*")
        .eq(
            "registration_id",
            registration_id,
        )
        .limit(1)
        .execute()
    )

    if not result.data:
        return None

    return result.data[0]


def create_proof_submission(
    submission_data: dict[str, Any],
) -> dict[str, Any]:
    result = (
        get_supabase()
        .table("proof_submissions")
        .insert(submission_data)
        .execute()
    )

    if not result.data:
        raise RuntimeError(
            "The proof submission was not created."
        )

    return result.data[0]


def get_all_registrations() -> list[dict[str, Any]]:
    result = (
        get_supabase()
        .table("registrations")
        .select("*")
        .order(
            "created_at",
            desc=True,
        )
        .execute()
    )

    return result.data or []


def get_all_proof_submissions() -> list[dict[str, Any]]:
    result = (
        get_supabase()
        .table("proof_submissions")
        .select("*")
        .order(
            "submitted_at",
            desc=True,
        )
        .execute()
    )

    return result.data or []


def upload_storage_file(
    bucket_name: str,
    storage_path: str,
    file_bytes: bytes,
    content_type: str,
    replace_existing: bool = False,
) -> None:
    file_options = {
        "content-type": content_type,
        "upsert": (
            "true"
            if replace_existing
            else "false"
        ),
    }

    (
        get_supabase()
        .storage
        .from_(bucket_name)
        .upload(
            path=storage_path,
            file=file_bytes,
            file_options=file_options,
        )
    )


def download_storage_file(
    bucket_name: str,
    storage_path: str,
) -> bytes:
    return (
        get_supabase()
        .storage
        .from_(bucket_name)
        .download(storage_path)
    )


def delete_storage_file(
    bucket_name: str,
    storage_path: str,
) -> None:
    (
        get_supabase()
        .storage
        .from_(bucket_name)
        .remove(
            [storage_path]
        )
    )


def create_temporary_file_url(
    bucket_name: str,
    storage_path: str,
    expiry_seconds: int = 600,
) -> str | None:
    result = (
        get_supabase()
        .storage
        .from_(bucket_name)
        .create_signed_url(
            storage_path,
            expiry_seconds,
        )
    )

    if not isinstance(result, dict):
        return None

    return (
        result.get("signedURL")
        or result.get("signedUrl")
        or result.get("signed_url")
    )
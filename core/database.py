from __future__ import annotations

import json
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


# ============================================================
# REGISTRATION FUNCTIONS
# ============================================================

def find_duplicate_registration(
    registration_number: str,
    email: str,
) -> str | None:
    """Check whether the registration number or email already exists."""

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
    """Create one new student registration."""

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
    """Retrieve a student using their registration number."""

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


def get_registration_by_id(
    registration_id: str,
) -> dict[str, Any] | None:
    """Retrieve one registration using its UUID."""

    result = (
        get_supabase()
        .table("registrations")
        .select("*")
        .eq("id", registration_id)
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
    """Update selected fields of one registration."""

    (
        get_supabase()
        .table("registrations")
        .update(values)
        .eq("id", registration_id)
        .execute()
    )


def get_all_registrations() -> list[dict[str, Any]]:
    """Retrieve every student registration."""

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


# ============================================================
# PROOF-SUBMISSION FUNCTIONS
# ============================================================

def get_proof_submission(
    registration_id: str,
) -> dict[str, Any] | None:
    """Return the proof submission belonging to one registration."""

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
    """Create the student's one-time proof submission."""

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


def get_all_proof_submissions() -> list[dict[str, Any]]:
    """Retrieve every proof submission."""

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


# ============================================================
# STORAGE FUNCTIONS
# ============================================================

def upload_storage_file(
    bucket_name: str,
    storage_path: str,
    file_bytes: bytes,
    content_type: str,
    replace_existing: bool = False,
) -> None:
    """Upload or replace a file in Supabase Storage."""

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
    """Download a private file from Supabase Storage."""

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
    """Delete one file from Supabase Storage."""

    (
        get_supabase()
        .storage
        .from_(bucket_name)
        .remove([storage_path])
    )


def delete_multiple_storage_files(
    bucket_name: str,
    storage_paths: list[str],
) -> None:
    """Delete multiple files from one Supabase Storage bucket."""

    cleaned_paths = [
        path.strip()
        for path in storage_paths
        if path and path.strip()
    ]

    if not cleaned_paths:
        return

    (
        get_supabase()
        .storage
        .from_(bucket_name)
        .remove(cleaned_paths)
    )


def create_temporary_file_url(
    bucket_name: str,
    storage_path: str,
    expiry_seconds: int = 600,
) -> str | None:
    """Create a temporary URL for a private file."""

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


# ============================================================
# ADMIN DATA-DELETION FUNCTIONS
# ============================================================

def extract_proof_files(
    proof_submission: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """
    Convert proof_files into a list.

    Supabase normally returns JSONB as a Python list. This also
    handles cases where the value is returned as a JSON string.
    """

    if not proof_submission:
        return []

    proof_files = proof_submission.get(
        "proof_files",
        [],
    )

    if isinstance(proof_files, list):
        return [
            item
            for item in proof_files
            if isinstance(item, dict)
        ]

    if isinstance(proof_files, str):
        try:
            decoded_value = json.loads(
                proof_files
            )

        except json.JSONDecodeError:
            return []

        if isinstance(decoded_value, list):
            return [
                item
                for item in decoded_value
                if isinstance(item, dict)
            ]

    return []


def delete_registration_and_related_data(
    registration_id: str,
) -> dict[str, int]:
    """
    Permanently delete one student registration.

    This function:
    1. Finds the student's proof submission.
    2. Deletes associated proof files from Storage.
    3. Deletes the registration.
    4. The proof-submission row is deleted through ON DELETE CASCADE.
    """

    database = get_supabase()

    registration = get_registration_by_id(
        registration_id
    )

    if registration is None:
        raise RuntimeError(
            "The selected registration does not exist."
        )

    proof_submission = get_proof_submission(
        registration_id
    )

    proof_files = extract_proof_files(
        proof_submission
    )

    storage_paths = [
        str(
            proof_file.get(
                "path",
                "",
            )
        ).strip()
        for proof_file in proof_files
        if str(
            proof_file.get(
                "path",
                "",
            )
        ).strip()
    ]

    proof_files_deleted = 0
    proof_files_failed = 0

    if storage_paths:
        try:
            delete_multiple_storage_files(
                bucket_name="proof-submissions",
                storage_paths=storage_paths,
            )

            proof_files_deleted = len(
                storage_paths
            )

        except Exception:
            # The registration is still deleted even when an
            # older or missing Storage object cannot be removed.
            proof_files_failed = len(
                storage_paths
            )

    (
        database.table("registrations")
        .delete()
        .eq("id", registration_id)
        .execute()
    )

    remaining_registration = get_registration_by_id(
        registration_id
    )

    if remaining_registration is not None:
        raise RuntimeError(
            "The registration still exists after the deletion request."
        )

    return {
        "registrations_deleted": 1,
        "proof_submissions_deleted": (
            1
            if proof_submission
            else 0
        ),
        "proof_files_deleted": proof_files_deleted,
        "proof_files_failed": proof_files_failed,
    }


def delete_all_registration_data() -> dict[str, int]:
    """
    Permanently delete all registrations and related proof data.

    The official task documents are not deleted.
    """

    registrations = get_all_registrations()

    result_summary = {
        "registrations_deleted": 0,
        "registrations_failed": 0,
        "proof_submissions_deleted": 0,
        "proof_files_deleted": 0,
        "proof_files_failed": 0,
    }

    for registration in registrations:
        registration_id = str(
            registration.get(
                "id",
                "",
            )
        ).strip()

        if not registration_id:
            result_summary[
                "registrations_failed"
            ] += 1

            continue

        try:
            deletion_result = (
                delete_registration_and_related_data(
                    registration_id
                )
            )

            result_summary[
                "registrations_deleted"
            ] += deletion_result[
                "registrations_deleted"
            ]

            result_summary[
                "proof_submissions_deleted"
            ] += deletion_result[
                "proof_submissions_deleted"
            ]

            result_summary[
                "proof_files_deleted"
            ] += deletion_result[
                "proof_files_deleted"
            ]

            result_summary[
                "proof_files_failed"
            ] += deletion_result[
                "proof_files_failed"
            ]

        except Exception:
            result_summary[
                "registrations_failed"
            ] += 1

    return result_summary
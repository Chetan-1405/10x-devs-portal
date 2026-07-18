from __future__ import annotations

import json
from typing import Any

import streamlit as st
from supabase import Client, create_client


# ============================================================
# SUPABASE CLIENT
# ============================================================

@st.cache_resource
def get_supabase() -> Client:
    """
    Create and cache the Supabase client.

    The service-role key must exist only in Streamlit Secrets.
    """

    supabase_url = str(
        st.secrets["SUPABASE_URL"]
    ).strip()

    service_role_key = str(
        st.secrets[
            "SUPABASE_SERVICE_ROLE_KEY"
        ]
    ).strip()

    if not supabase_url:
        raise RuntimeError(
            "SUPABASE_URL is missing from Streamlit Secrets."
        )

    if not service_role_key:
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY is missing "
            "from Streamlit Secrets."
        )

    return create_client(
        supabase_url,
        service_role_key,
    )


# ============================================================
# GENERAL JSON HELPERS
# ============================================================

def parse_json_list(
    value: Any,
) -> list[Any]:
    """
    Convert JSON text or a Python list into a list.
    """

    if isinstance(value, list):
        return value

    if isinstance(value, str):
        try:
            decoded_value = json.loads(value)

            if isinstance(decoded_value, list):
                return decoded_value

        except json.JSONDecodeError:
            return []

    return []


def parse_json_dict(
    value: Any,
) -> dict[str, Any]:
    """
    Convert JSON text or a Python dictionary into a dictionary.
    """

    if isinstance(value, dict):
        return value

    if isinstance(value, str):
        try:
            decoded_value = json.loads(value)

            if isinstance(decoded_value, dict):
                return decoded_value

        except json.JSONDecodeError:
            return {}

    return {}


# ============================================================
# REGISTRATION OPERATIONS
# ============================================================

def find_duplicate_registration(
    registration_number: str,
    email: str,
) -> str | None:
    """
    Check whether the registration number or email already exists.
    """

    database = get_supabase()

    registration_response = (
        database.table(
            "registrations"
        )
        .select(
            "id, registration_number"
        )
        .eq(
            "registration_number",
            registration_number,
        )
        .limit(1)
        .execute()
    )

    if registration_response.data:
        return (
            "This registration number has already "
            "been registered."
        )

    email_response = (
        database.table(
            "registrations"
        )
        .select(
            "id, email"
        )
        .eq(
            "email",
            email,
        )
        .limit(1)
        .execute()
    )

    if email_response.data:
        return (
            "This email address has already been registered."
        )

    return None


def create_registration(
    registration_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Insert a new student registration and return the created row.
    """

    response = (
        get_supabase()
        .table(
            "registrations"
        )
        .insert(
            registration_data
        )
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            "Supabase did not return the created registration."
        )

    return dict(
        response.data[0]
    )


def get_student(
    registration_number: str,
) -> dict[str, Any] | None:
    """
    Get one student using their registration number.
    """

    response = (
        get_supabase()
        .table(
            "registrations"
        )
        .select("*")
        .eq(
            "registration_number",
            registration_number,
        )
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    return dict(
        response.data[0]
    )


def get_registration_by_id(
    registration_id: str,
) -> dict[str, Any] | None:
    """
    Get one registration using its UUID.
    """

    response = (
        get_supabase()
        .table(
            "registrations"
        )
        .select("*")
        .eq(
            "id",
            registration_id,
        )
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    return dict(
        response.data[0]
    )


def get_registration_by_reference(
    application_reference: str,
) -> dict[str, Any] | None:
    """
    Get one registration using the application reference.
    """

    response = (
        get_supabase()
        .table(
            "registrations"
        )
        .select("*")
        .eq(
            "application_reference",
            application_reference,
        )
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    return dict(
        response.data[0]
    )


def get_all_registrations() -> list[dict[str, Any]]:
    """
    Return all registrations, newest first.
    """

    response = (
        get_supabase()
        .table(
            "registrations"
        )
        .select("*")
        .order(
            "created_at",
            desc=True,
        )
        .execute()
    )

    return [
        dict(record)
        for record in (
            response.data or []
        )
    ]


def update_registration(
    registration_id: str,
    values: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Update a registration and return the updated row when available.
    """

    if not registration_id:
        raise ValueError(
            "registration_id is required."
        )

    if not values:
        raise ValueError(
            "At least one registration field must be provided."
        )

    response = (
        get_supabase()
        .table(
            "registrations"
        )
        .update(
            values
        )
        .eq(
            "id",
            registration_id,
        )
        .execute()
    )

    if not response.data:
        return None

    return dict(
        response.data[0]
    )


# ============================================================
# PROOF-SUBMISSION OPERATIONS
# ============================================================

def create_proof_submission(
    submission_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Insert the student's one-time final proof submission.
    """

    response = (
        get_supabase()
        .table(
            "proof_submissions"
        )
        .insert(
            submission_data
        )
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            "Supabase did not return the created proof submission."
        )

    return dict(
        response.data[0]
    )


def get_proof_submission(
    registration_id: str,
) -> dict[str, Any] | None:
    """
    Get the proof submission belonging to one registration.
    """

    response = (
        get_supabase()
        .table(
            "proof_submissions"
        )
        .select("*")
        .eq(
            "registration_id",
            registration_id,
        )
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    return dict(
        response.data[0]
    )


def get_proof_submission_by_id(
    submission_id: str,
) -> dict[str, Any] | None:
    """
    Get one proof submission using its UUID.
    """

    response = (
        get_supabase()
        .table(
            "proof_submissions"
        )
        .select("*")
        .eq(
            "id",
            submission_id,
        )
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    return dict(
        response.data[0]
    )


def get_all_proof_submissions() -> list[dict[str, Any]]:
    """
    Return all proof submissions, newest first.
    """

    response = (
        get_supabase()
        .table(
            "proof_submissions"
        )
        .select("*")
        .order(
            "submitted_at",
            desc=True,
        )
        .execute()
    )

    return [
        dict(record)
        for record in (
            response.data or []
        )
    ]


def update_proof_submission(
    submission_id: str,
    values: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Update evaluation or other proof-submission fields.
    """

    if not submission_id:
        raise ValueError(
            "submission_id is required."
        )

    if not values:
        raise ValueError(
            "At least one proof-submission field "
            "must be provided."
        )

    response = (
        get_supabase()
        .table(
            "proof_submissions"
        )
        .update(
            values
        )
        .eq(
            "id",
            submission_id,
        )
        .execute()
    )

    if not response.data:
        return None

    return dict(
        response.data[0]
    )


# ============================================================
# STORAGE OPERATIONS
# ============================================================

def upload_storage_file(
    bucket_name: str,
    storage_path: str,
    file_bytes: bytes,
    content_type: str = "application/octet-stream",
    replace_existing: bool = False,
) -> Any:
    """
    Upload a file to a Supabase Storage bucket.

    When replace_existing is True, the file is uploaded with
    the upsert option.
    """

    if not bucket_name:
        raise ValueError(
            "bucket_name is required."
        )

    if not storage_path:
        raise ValueError(
            "storage_path is required."
        )

    if not file_bytes:
        raise ValueError(
            "The uploaded file is empty."
        )

    file_options = {
        "content-type": content_type,
        "cache-control": "3600",
        "upsert": (
            "true"
            if replace_existing
            else "false"
        ),
    }

    return (
        get_supabase()
        .storage
        .from_(
            bucket_name
        )
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
    """
    Download a file from a private Supabase Storage bucket.
    """

    if not bucket_name:
        raise ValueError(
            "bucket_name is required."
        )

    if not storage_path:
        raise ValueError(
            "storage_path is required."
        )

    downloaded_file = (
        get_supabase()
        .storage
        .from_(
            bucket_name
        )
        .download(
            storage_path
        )
    )

    if downloaded_file is None:
        raise RuntimeError(
            "Supabase returned no file data."
        )

    return downloaded_file


def delete_storage_file(
    bucket_name: str,
    storage_path: str,
) -> None:
    """
    Delete one file from Supabase Storage.
    """

    if not bucket_name:
        raise ValueError(
            "bucket_name is required."
        )

    if not storage_path:
        raise ValueError(
            "storage_path is required."
        )

    (
        get_supabase()
        .storage
        .from_(
            bucket_name
        )
        .remove(
            [
                storage_path
            ]
        )
    )


def delete_storage_files(
    bucket_name: str,
    storage_paths: list[str],
) -> None:
    """
    Delete multiple files from one Supabase Storage bucket.
    """

    cleaned_paths = [
        str(path).strip()
        for path in storage_paths
        if str(path).strip()
    ]

    if not cleaned_paths:
        return

    (
        get_supabase()
        .storage
        .from_(
            bucket_name
        )
        .remove(
            cleaned_paths
        )
    )


def create_temporary_file_url(
    bucket_name: str,
    storage_path: str,
    expiry_seconds: int = 600,
) -> str | None:
    """
    Create a temporary signed URL for a private Storage file.
    """

    if not bucket_name:
        raise ValueError(
            "bucket_name is required."
        )

    if not storage_path:
        raise ValueError(
            "storage_path is required."
        )

    if expiry_seconds <= 0:
        raise ValueError(
            "expiry_seconds must be greater than zero."
        )

    response = (
        get_supabase()
        .storage
        .from_(
            bucket_name
        )
        .create_signed_url(
            storage_path,
            expiry_seconds,
        )
    )

    if isinstance(response, str):
        return response

    if not isinstance(response, dict):
        return None

    signed_url = (
        response.get(
            "signedURL"
        )
        or response.get(
            "signedUrl"
        )
        or response.get(
            "signed_url"
        )
    )

    if not signed_url:
        data = response.get(
            "data"
        )

        if isinstance(data, dict):
            signed_url = (
                data.get(
                    "signedURL"
                )
                or data.get(
                    "signedUrl"
                )
                or data.get(
                    "signed_url"
                )
            )

    if not signed_url:
        return None

    return str(
        signed_url
    )


# ============================================================
# SUBMISSION FILE EXTRACTION
# ============================================================

def extract_submission_files(
    submission: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """
    Extract mandatory-task and specific-task file records.
    """

    if not submission:
        return []

    extracted_files: list[
        dict[str, Any]
    ] = []

    mandatory_files = parse_json_list(
        submission.get(
            "proof_files",
            [],
        )
    )

    for file_record in mandatory_files:
        if isinstance(file_record, dict):
            extracted_files.append(
                file_record
            )

    task_evidence = parse_json_list(
        submission.get(
            "specific_task_evidence",
            [],
        )
    )

    for task_record in task_evidence:
        if not isinstance(
            task_record,
            dict,
        ):
            continue

        task_files = parse_json_list(
            task_record.get(
                "files",
                [],
            )
        )

        for file_record in task_files:
            if isinstance(
                file_record,
                dict,
            ):
                extracted_files.append(
                    file_record
                )

    return extracted_files


def extract_submission_storage_paths(
    submission: dict[str, Any] | None,
) -> list[str]:
    """
    Extract unique Supabase Storage paths from a submission.
    """

    unique_paths: set[str] = set()

    for file_record in extract_submission_files(
        submission
    ):
        path = str(
            file_record.get(
                "path",
                "",
            )
        ).strip()

        if path:
            unique_paths.add(
                path
            )

    return sorted(
        unique_paths
    )


# ============================================================
# REGISTRATION AND SUBMISSION DELETION
# ============================================================

def delete_registration_and_related_data(
    registration_id: str,
) -> dict[str, int]:
    """
    Delete one registration and its related submission data.

    The proof_submissions foreign key must use ON DELETE CASCADE.
    Storage files are deleted before the registration row.
    """

    registration = get_registration_by_id(
        registration_id
    )

    if not registration:
        raise RuntimeError(
            "The selected registration does not exist."
        )

    submission = get_proof_submission(
        registration_id
    )

    storage_paths = (
        extract_submission_storage_paths(
            submission
        )
    )

    proof_files_deleted = 0
    proof_files_failed = 0

    if storage_paths:
        try:
            delete_storage_files(
                bucket_name="proof-submissions",
                storage_paths=storage_paths,
            )

            proof_files_deleted = len(
                storage_paths
            )

        except Exception:
            proof_files_failed = len(
                storage_paths
            )

    response = (
        get_supabase()
        .table(
            "registrations"
        )
        .delete()
        .eq(
            "id",
            registration_id,
        )
        .execute()
    )

    remaining_registration = (
        get_registration_by_id(
            registration_id
        )
    )

    if remaining_registration is not None:
        raise RuntimeError(
            "The registration still exists after deletion."
        )

    return {
        "registrations_deleted": 1,
        "registrations_failed": 0,
        "proof_files_deleted": proof_files_deleted,
        "proof_files_failed": proof_files_failed,
    }


def delete_all_registration_data() -> dict[str, int]:
    """
    Delete every registration and related proof submission.

    Task documents are not deleted.
    """

    summary = {
        "registrations_deleted": 0,
        "registrations_failed": 0,
        "proof_files_deleted": 0,
        "proof_files_failed": 0,
    }

    registrations = get_all_registrations()

    for registration in registrations:
        registration_id = str(
            registration.get(
                "id",
                "",
            )
        ).strip()

        if not registration_id:
            summary[
                "registrations_failed"
            ] += 1

            continue

        try:
            result = (
                delete_registration_and_related_data(
                    registration_id
                )
            )

            summary[
                "registrations_deleted"
            ] += result.get(
                "registrations_deleted",
                0,
            )

            summary[
                "proof_files_deleted"
            ] += result.get(
                "proof_files_deleted",
                0,
            )

            summary[
                "proof_files_failed"
            ] += result.get(
                "proof_files_failed",
                0,
            )

        except Exception:
            summary[
                "registrations_failed"
            ] += 1

    return summary
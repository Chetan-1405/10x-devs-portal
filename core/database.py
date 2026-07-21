from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any, Iterable

import streamlit as st
from supabase import Client, create_client

from core.constants import (
    CLUB_PROJECT_MEDIA_BUCKET,
    GENERATED_DOCUMENT_BUCKET,
    PROOF_SUBMISSION_BUCKET,
    TASK_DOCUMENT_BUCKET,
)


# ============================================================
# SUPABASE CLIENT
# ============================================================

@st.cache_resource
def get_supabase() -> Client:
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
            "SUPABASE_URL is missing."
        )

    if not service_role_key:
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY is missing."
        )

    return create_client(
        supabase_url,
        service_role_key,
    )


# ============================================================
# GENERAL RESPONSE HELPERS
# ============================================================

def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(
        response,
        "data",
        None,
    )

    if not data:
        return []

    return [
        dict(record)
        for record in data
    ]


def _first(response: Any) -> dict[str, Any] | None:
    rows = _rows(response)

    return rows[0] if rows else None


def _require_created_row(
    response: Any,
    entity_name: str,
) -> dict[str, Any]:
    created_row = _first(response)

    if not created_row:
        raise RuntimeError(
            f"Supabase did not return the created {entity_name}."
        )

    return created_row


def _clean_values(
    values: dict[str, Any],
) -> dict[str, Any]:
    return {
        key: value
        for key, value in values.items()
        if value is not None
    }


def parse_json_list(
    value: Any,
) -> list[Any]:
    if isinstance(value, list):
        return value

    if isinstance(value, tuple):
        return list(value)

    if isinstance(value, str):
        try:
            decoded = json.loads(value)

            if isinstance(decoded, list):
                return decoded
        except json.JSONDecodeError:
            return []

    return []


def parse_json_dict(
    value: Any,
) -> dict[str, Any]:
    if isinstance(value, dict):
        return value

    if isinstance(value, str):
        try:
            decoded = json.loads(value)

            if isinstance(decoded, dict):
                return decoded
        except json.JSONDecodeError:
            return {}

    return {}


def utc_now_iso() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


# ============================================================
# REGISTRATIONS
# ============================================================

def find_duplicate_registration(
    registration_number: str,
    email: str,
    mobile_number: str | None = None,
    exclude_registration_id: str | None = None,
) -> str | None:
    registrations = get_all_registrations()

    normalized_registration = (
        registration_number
        .strip()
        .upper()
    )

    normalized_email = (
        email
        .strip()
        .lower()
    )

    normalized_mobile = (
        mobile_number.strip()
        if mobile_number
        else None
    )

    for registration in registrations:
        current_id = str(
            registration.get(
                "id",
                "",
            )
        )

        if (
            exclude_registration_id
            and current_id
            == str(exclude_registration_id)
        ):
            continue

        if (
            str(
                registration.get(
                    "registration_number",
                    "",
                )
            ).strip().upper()
            == normalized_registration
        ):
            return (
                "This registration number has already "
                "been registered."
            )

        if (
            str(
                registration.get(
                    "email",
                    "",
                )
            ).strip().lower()
            == normalized_email
        ):
            return (
                "This email address has already been registered."
            )

        if (
            normalized_mobile
            and str(
                registration.get(
                    "mobile_number",
                    "",
                )
            ).strip()
            == normalized_mobile
        ):
            return (
                "This mobile number has already been registered."
            )

    return None


def create_registration(
    registration_data: dict[str, Any],
) -> dict[str, Any]:
    response = (
        get_supabase()
        .table("registrations")
        .insert(registration_data)
        .execute()
    )

    registration = _require_created_row(
        response,
        "registration",
    )

    create_timeline_event(
        registration_id=str(
            registration["id"]
        ),
        event_type="Registration",
        title="Registration completed",
        description=(
            "Your 10x Devs registration was completed "
            "successfully."
        ),
        visible_to_student=True,
        created_by="System",
        ignore_duplicate=True,
    )

    return registration


def get_student(
    registration_number: str,
) -> dict[str, Any] | None:
    response = (
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

    return _first(response)


def get_registration_by_id(
    registration_id: str,
) -> dict[str, Any] | None:
    response = (
        get_supabase()
        .table("registrations")
        .select("*")
        .eq(
            "id",
            registration_id,
        )
        .limit(1)
        .execute()
    )

    return _first(response)


def get_registration_by_email(
    email: str,
) -> dict[str, Any] | None:
    response = (
        get_supabase()
        .table("registrations")
        .select("*")
        .eq(
            "email",
            email.strip().lower(),
        )
        .limit(1)
        .execute()
    )

    return _first(response)


def get_registration_by_reference(
    application_reference: str,
) -> dict[str, Any] | None:
    response = (
        get_supabase()
        .table("registrations")
        .select("*")
        .eq(
            "application_reference",
            application_reference,
        )
        .limit(1)
        .execute()
    )

    return _first(response)


def get_all_registrations() -> list[dict[str, Any]]:
    response = (
        get_supabase()
        .table("registrations")
        .select("*")
        .order(
            "created_at",
            desc=True,
        )
        .execute()
    )

    return _rows(response)


def update_registration(
    registration_id: str,
    values: dict[str, Any],
) -> dict[str, Any] | None:
    if not registration_id:
        raise ValueError(
            "registration_id is required."
        )

    clean_values = _clean_values(
        values
    )

    if not clean_values:
        raise ValueError(
            "At least one field must be provided."
        )

    response = (
        get_supabase()
        .table("registrations")
        .update(clean_values)
        .eq(
            "id",
            registration_id,
        )
        .execute()
    )

    return _first(response)


def update_student_last_login(
    registration_id: str,
) -> None:
    update_registration(
        registration_id,
        {
            "last_login_at": utc_now_iso(),
        },
    )


def update_student_profile(
    registration_id: str,
    profile_values: dict[str, Any],
) -> dict[str, Any] | None:
    allowed_fields = {
        "full_name",
        "email",
        "mobile_number",
        "preferred_contact_mode",
    }

    safe_values = {
        key: value
        for key, value in profile_values.items()
        if key in allowed_fields
    }

    result = update_registration(
        registration_id,
        safe_values,
    )

    create_timeline_event(
        registration_id=registration_id,
        event_type="Profile",
        title="Profile updated",
        description=(
            "Your contact information was updated."
        ),
        visible_to_student=True,
        created_by="Student",
    )

    return result


def extend_student_deadline(
    registration_id: str,
    new_deadline: date | str,
    reason: str,
    extended_by: str,
) -> dict[str, Any] | None:
    deadline_value = (
        new_deadline.isoformat()
        if isinstance(new_deadline, date)
        else str(new_deadline)
    )

    result = update_registration(
        registration_id,
        {
            "task_deadline": deadline_value,
            "deadline_extended": True,
            "deadline_extension_reason": reason,
            "deadline_extended_at": utc_now_iso(),
            "deadline_extended_by": extended_by,
        },
    )

    create_timeline_event(
        registration_id=registration_id,
        event_type="Deadline",
        title="Submission deadline extended",
        description=(
            f"Your submission deadline was extended "
            f"to {deadline_value}."
        ),
        visible_to_student=True,
        created_by=extended_by,
    )

    return result


def bulk_update_registration_status(
    registration_ids: list[str],
    status: str,
) -> int:
    updated_count = 0

    for registration_id in registration_ids:
        update_registration(
            registration_id,
            {
                "application_status": status,
            },
        )

        updated_count += 1

    return updated_count


# ============================================================
# PROOF SUBMISSIONS
# ============================================================

def create_proof_submission(
    submission_data: dict[str, Any],
) -> dict[str, Any]:
    response = (
        get_supabase()
        .table("proof_submissions")
        .insert(submission_data)
        .execute()
    )

    return _require_created_row(
        response,
        "proof submission",
    )


def get_proof_submission(
    registration_id: str,
) -> dict[str, Any] | None:
    response = (
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

    return _first(response)


def get_proof_submission_by_id(
    submission_id: str,
) -> dict[str, Any] | None:
    response = (
        get_supabase()
        .table("proof_submissions")
        .select("*")
        .eq(
            "id",
            submission_id,
        )
        .limit(1)
        .execute()
    )

    return _first(response)


def get_all_proof_submissions() -> list[dict[str, Any]]:
    response = (
        get_supabase()
        .table("proof_submissions")
        .select("*")
        .order(
            "updated_at",
            desc=True,
        )
        .execute()
    )

    return _rows(response)


def update_proof_submission(
    submission_id: str,
    values: dict[str, Any],
) -> dict[str, Any] | None:
    clean_values = _clean_values(
        values
    )

    if not clean_values:
        raise ValueError(
            "At least one proof-submission field is required."
        )

    response = (
        get_supabase()
        .table("proof_submissions")
        .update(clean_values)
        .eq(
            "id",
            submission_id,
        )
        .execute()
    )

    return _first(response)


def save_submission_draft(
    registration_id: str,
    submission_values: dict[str, Any],
) -> dict[str, Any]:
    existing_submission = get_proof_submission(
        registration_id
    )

    draft_values = {
        **submission_values,
        "registration_id": registration_id,
        "submission_state": "Draft",
        "draft_saved_at": utc_now_iso(),
        "last_edited_at": utc_now_iso(),
    }

    if existing_submission:
        updated = update_proof_submission(
            str(existing_submission["id"]),
            draft_values,
        )

        if not updated:
            raise RuntimeError(
                "The submission draft could not be updated."
            )

        return updated

    created = create_proof_submission(
        draft_values
    )

    create_timeline_event(
        registration_id=registration_id,
        event_type="Submission",
        title="Submission draft saved",
        description=(
            "Your proof-submission draft was saved."
        ),
        visible_to_student=True,
        created_by="Student",
    )

    return created


def finalize_submission(
    registration_id: str,
    submission_values: dict[str, Any],
) -> dict[str, Any]:
    existing_submission = get_proof_submission(
        registration_id
    )

    final_values = {
        **submission_values,
        "registration_id": registration_id,
        "submission_state": "Final",
        "final_submitted_at": utc_now_iso(),
        "last_edited_at": utc_now_iso(),
        "submitted_at": utc_now_iso(),
        "evaluation_progress": "Not Reviewed",
    }

    if existing_submission:
        submission = update_proof_submission(
            str(existing_submission["id"]),
            final_values,
        )

        if not submission:
            raise RuntimeError(
                "The final submission could not be updated."
            )
    else:
        submission = create_proof_submission(
            final_values
        )

    update_registration(
        registration_id,
        {
            "application_status": "Under Scrutiny",
            "submission_reopened": False,
        },
    )

    create_timeline_event(
        registration_id=registration_id,
        event_type="Submission",
        title="Final proof submitted",
        description=(
            "Your final proof was submitted and is now "
            "under scrutiny."
        ),
        visible_to_student=True,
        created_by="Student",
    )

    return submission


def reopen_submission(
    registration_id: str,
    reason: str,
    reopened_by: str,
) -> dict[str, Any]:
    submission = get_proof_submission(
        registration_id
    )

    if not submission:
        raise RuntimeError(
            "No proof submission exists for this student."
        )

    reopened_at = utc_now_iso()

    updated_submission = update_proof_submission(
        str(submission["id"]),
        {
            "submission_state": "Reopened",
            "reopened_at": reopened_at,
            "reopened_by": reopened_by,
            "reopened_reason": reason,
        },
    )

    update_registration(
        registration_id,
        {
            "submission_reopened": True,
            "submission_reopened_at": reopened_at,
            "submission_reopened_by": reopened_by,
            "submission_reopened_reason": reason,
        },
    )

    create_timeline_event(
        registration_id=registration_id,
        event_type="Submission",
        title="Submission reopened",
        description=reason,
        visible_to_student=True,
        created_by=reopened_by,
    )

    if not updated_submission:
        raise RuntimeError(
            "The submission could not be reopened."
        )

    return updated_submission


def source_url_already_exists(
    source_url: str,
    exclude_registration_id: str | None = None,
) -> bool:
    normalized_url = (
        source_url
        .strip()
        .rstrip("/")
        .lower()
    )

    if not normalized_url:
        return False

    for submission in get_all_proof_submissions():
        if (
            exclude_registration_id
            and str(
                submission.get(
                    "registration_id",
                    "",
                )
            )
            == str(exclude_registration_id)
        ):
            continue

        portfolio_url = str(
            submission.get(
                "portfolio_github_url",
                "",
            )
            or ""
        ).strip().rstrip("/").lower()

        if portfolio_url == normalized_url:
            return True

        evidence_items = parse_json_list(
            submission.get(
                "specific_task_evidence",
                [],
            )
        )

        for evidence in evidence_items:
            if not isinstance(evidence, dict):
                continue

            evidence_url = str(
                evidence.get(
                    "source_url",
                    "",
                )
                or ""
            ).strip().rstrip("/").lower()

            if evidence_url == normalized_url:
                return True

    return False


# ============================================================
# PASSWORD RESET OTP RECORDS
# ============================================================

def invalidate_password_reset_otps(
    registration_id: str,
) -> None:
    active_otps = (
        get_supabase()
        .table("password_reset_otps")
        .select("id")
        .eq(
            "registration_id",
            registration_id,
        )
        .eq(
            "is_used",
            False,
        )
        .execute()
    )

    for otp_record in _rows(active_otps):
        (
            get_supabase()
            .table("password_reset_otps")
            .update(
                {
                    "is_used": True,
                    "used_at": utc_now_iso(),
                }
            )
            .eq(
                "id",
                otp_record["id"],
            )
            .execute()
        )


def create_password_reset_otp(
    registration_id: str,
    otp_hash: str,
    expires_at: str,
    maximum_attempts: int,
) -> dict[str, Any]:
    invalidate_password_reset_otps(
        registration_id
    )

    response = (
        get_supabase()
        .table("password_reset_otps")
        .insert(
            {
                "registration_id": registration_id,
                "otp_hash": otp_hash,
                "expires_at": expires_at,
                "maximum_attempts": maximum_attempts,
            }
        )
        .execute()
    )

    return _require_created_row(
        response,
        "password reset OTP",
    )


def get_latest_password_reset_otp(
    registration_id: str,
) -> dict[str, Any] | None:
    response = (
        get_supabase()
        .table("password_reset_otps")
        .select("*")
        .eq(
            "registration_id",
            registration_id,
        )
        .eq(
            "is_used",
            False,
        )
        .order(
            "created_at",
            desc=True,
        )
        .limit(1)
        .execute()
    )

    return _first(response)


def increment_otp_attempt(
    otp_id: str,
    current_attempt_count: int,
) -> None:
    (
        get_supabase()
        .table("password_reset_otps")
        .update(
            {
                "attempt_count": (
                    current_attempt_count + 1
                ),
            }
        )
        .eq(
            "id",
            otp_id,
        )
        .execute()
    )


def mark_otp_used(
    otp_id: str,
) -> None:
    (
        get_supabase()
        .table("password_reset_otps")
        .update(
            {
                "is_used": True,
                "used_at": utc_now_iso(),
            }
        )
        .eq(
            "id",
            otp_id,
        )
        .execute()
    )


def delete_expired_otps() -> int:
    otp_rows = _rows(
        (
            get_supabase()
            .table("password_reset_otps")
            .select("id, expires_at")
            .execute()
        )
    )

    now = datetime.now(
        timezone.utc
    )

    expired_ids: list[str] = []

    for otp_record in otp_rows:
        try:
            expiry = datetime.fromisoformat(
                str(
                    otp_record["expires_at"]
                ).replace(
                    "Z",
                    "+00:00",
                )
            )

            if expiry <= now:
                expired_ids.append(
                    str(otp_record["id"])
                )
        except (
            ValueError,
            TypeError,
        ):
            continue

    for otp_id in expired_ids:
        (
            get_supabase()
            .table("password_reset_otps")
            .delete()
            .eq(
                "id",
                otp_id,
            )
            .execute()
        )

    return len(expired_ids)


# ============================================================
# ANNOUNCEMENTS
# ============================================================

def create_announcement(
    values: dict[str, Any],
) -> dict[str, Any]:
    response = (
        get_supabase()
        .table("announcements")
        .insert(values)
        .execute()
    )

    return _require_created_row(
        response,
        "announcement",
    )


def update_announcement(
    announcement_id: str,
    values: dict[str, Any],
) -> dict[str, Any] | None:
    response = (
        get_supabase()
        .table("announcements")
        .update(values)
        .eq(
            "id",
            announcement_id,
        )
        .execute()
    )

    return _first(response)


def delete_announcement(
    announcement_id: str,
) -> None:
    (
        get_supabase()
        .table("announcements")
        .delete()
        .eq(
            "id",
            announcement_id,
        )
        .execute()
    )


def get_all_announcements() -> list[dict[str, Any]]:
    response = (
        get_supabase()
        .table("announcements")
        .select("*")
        .order(
            "created_at",
            desc=True,
        )
        .execute()
    )

    return _rows(response)


def get_published_announcements(
    student: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    announcements = [
        announcement
        for announcement in get_all_announcements()
        if announcement.get(
            "is_published"
        )
    ]

    now = datetime.now(
        timezone.utc
    )

    visible: list[dict[str, Any]] = []

    for announcement in announcements:
        expires_at = announcement.get(
            "expires_at"
        )

        if expires_at:
            try:
                expiry = datetime.fromisoformat(
                    str(expires_at).replace(
                        "Z",
                        "+00:00",
                    )
                )

                if expiry <= now:
                    continue
            except ValueError:
                pass

        if student is None:
            if (
                announcement.get(
                    "target_audience"
                )
                == "All"
            ):
                visible.append(
                    announcement
                )

            continue

        audience = announcement.get(
            "target_audience",
            "All",
        )

        student_year = student.get(
            "study_year"
        )

        student_club = student.get(
            "club"
        )

        student_status = student.get(
            "application_status"
        )

        is_visible = (
            audience == "All"
            or (
                audience == "Year"
                and announcement.get(
                    "target_year"
                )
                == student_year
            )
            or (
                audience == "Club"
                and announcement.get(
                    "target_club"
                )
                == student_club
            )
            or (
                audience == "Year and Club"
                and announcement.get(
                    "target_year"
                )
                == student_year
                and announcement.get(
                    "target_club"
                )
                == student_club
            )
            or (
                audience
                == "Selected Students"
                and student_status
                == "Selected"
            )
            or (
                audience
                == "Shortlisted Students"
                and student_status
                == "Shortlisted"
            )
        )

        if is_visible:
            visible.append(
                announcement
            )

    return visible


def get_announcement_recipients(
    announcement: dict[str, Any],
) -> list[dict[str, Any]]:
    registrations = [
        registration
        for registration in get_all_registrations()
        if registration.get(
            "is_active",
            True,
        )
    ]

    recipients: list[dict[str, Any]] = []

    for student in registrations:
        audience = announcement.get(
            "target_audience",
            "All",
        )

        matches = (
            audience == "All"
            or (
                audience == "Year"
                and student.get(
                    "study_year"
                )
                == announcement.get(
                    "target_year"
                )
            )
            or (
                audience == "Club"
                and student.get(
                    "club"
                )
                == announcement.get(
                    "target_club"
                )
            )
            or (
                audience == "Year and Club"
                and student.get(
                    "study_year"
                )
                == announcement.get(
                    "target_year"
                )
                and student.get(
                    "club"
                )
                == announcement.get(
                    "target_club"
                )
            )
            or (
                audience
                == "Selected Students"
                and student.get(
                    "application_status"
                )
                == "Selected"
            )
            or (
                audience
                == "Shortlisted Students"
                and student.get(
                    "application_status"
                )
                == "Shortlisted"
            )
        )

        if matches:
            recipients.append(
                student
            )

    return recipients


def record_announcement_email(
    announcement_id: str,
    registration_id: str,
    delivery_status: str,
    message_id: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    response = (
        get_supabase()
        .table("announcement_email_logs")
        .upsert(
            {
                "announcement_id": announcement_id,
                "registration_id": registration_id,
                "delivery_status": delivery_status,
                "message_id": message_id,
                "error_message": error_message,
                "sent_at": (
                    utc_now_iso()
                    if delivery_status == "Sent"
                    else None
                ),
            },
            on_conflict=(
                "announcement_id,"
                "registration_id"
            ),
        )
        .execute()
    )

    return _require_created_row(
        response,
        "announcement email log",
    )


# ============================================================
# CLUB PROJECT SHOWCASE
# ============================================================

def create_club_project(
    values: dict[str, Any],
) -> dict[str, Any]:
    response = (
        get_supabase()
        .table("club_projects")
        .insert(values)
        .execute()
    )

    return _require_created_row(
        response,
        "club project",
    )


def update_club_project(
    project_id: str,
    values: dict[str, Any],
) -> dict[str, Any] | None:
    response = (
        get_supabase()
        .table("club_projects")
        .update(values)
        .eq(
            "id",
            project_id,
        )
        .execute()
    )

    return _first(response)


def delete_club_project(
    project_id: str,
) -> None:
    project = get_club_project_by_id(
        project_id
    )

    if (
        project
        and project.get(
            "thumbnail_storage_path"
        )
    ):
        try:
            delete_storage_file(
                CLUB_PROJECT_MEDIA_BUCKET,
                str(
                    project[
                        "thumbnail_storage_path"
                    ]
                ),
            )
        except Exception:
            pass

    (
        get_supabase()
        .table("club_projects")
        .delete()
        .eq(
            "id",
            project_id,
        )
        .execute()
    )


def get_club_project_by_id(
    project_id: str,
) -> dict[str, Any] | None:
    response = (
        get_supabase()
        .table("club_projects")
        .select("*")
        .eq(
            "id",
            project_id,
        )
        .limit(1)
        .execute()
    )

    return _first(response)


def get_all_club_projects() -> list[dict[str, Any]]:
    response = (
        get_supabase()
        .table("club_projects")
        .select("*")
        .order(
            "featured",
            desc=True,
        )
        .order(
            "display_order",
            desc=False,
        )
        .order(
            "created_at",
            desc=True,
        )
        .execute()
    )

    return _rows(response)


def get_published_club_projects(
    club: str | None = None,
) -> list[dict[str, Any]]:
    projects = [
        project
        for project in get_all_club_projects()
        if project.get(
            "project_status"
        )
        == "Published"
    ]

    if club:
        projects = [
            project
            for project in projects
            if project.get("club")
            == club
        ]

    return projects


# ============================================================
# EVALUATOR ACCOUNTS
# ============================================================

def create_evaluator_account(
    values: dict[str, Any],
) -> dict[str, Any]:
    response = (
        get_supabase()
        .table("evaluator_accounts")
        .insert(values)
        .execute()
    )

    return _require_created_row(
        response,
        "evaluator account",
    )


def get_evaluator_by_username(
    username: str,
) -> dict[str, Any] | None:
    response = (
        get_supabase()
        .table("evaluator_accounts")
        .select("*")
        .eq(
            "username",
            username.strip().lower(),
        )
        .limit(1)
        .execute()
    )

    return _first(response)


def get_evaluator_by_id(
    evaluator_id: str,
) -> dict[str, Any] | None:
    response = (
        get_supabase()
        .table("evaluator_accounts")
        .select("*")
        .eq(
            "id",
            evaluator_id,
        )
        .limit(1)
        .execute()
    )

    return _first(response)


def get_all_evaluators() -> list[dict[str, Any]]:
    response = (
        get_supabase()
        .table("evaluator_accounts")
        .select("*")
        .order(
            "created_at",
            desc=True,
        )
        .execute()
    )

    return _rows(response)


def update_evaluator_account(
    evaluator_id: str,
    values: dict[str, Any],
) -> dict[str, Any] | None:
    response = (
        get_supabase()
        .table("evaluator_accounts")
        .update(values)
        .eq(
            "id",
            evaluator_id,
        )
        .execute()
    )

    return _first(response)


def delete_evaluator_account(
    evaluator_id: str,
) -> None:
    (
        get_supabase()
        .table("evaluator_accounts")
        .delete()
        .eq(
            "id",
            evaluator_id,
        )
        .execute()
    )


# ============================================================
# INTERVIEW SCHEDULING
# ============================================================

def upsert_interview_schedule(
    values: dict[str, Any],
) -> dict[str, Any]:
    response = (
        get_supabase()
        .table("interview_schedules")
        .upsert(
            values,
            on_conflict="registration_id",
        )
        .execute()
    )

    return _require_created_row(
        response,
        "interview schedule",
    )


def get_interview_schedule(
    registration_id: str,
) -> dict[str, Any] | None:
    response = (
        get_supabase()
        .table("interview_schedules")
        .select("*")
        .eq(
            "registration_id",
            registration_id,
        )
        .limit(1)
        .execute()
    )

    return _first(response)


def get_all_interview_schedules() -> list[dict[str, Any]]:
    response = (
        get_supabase()
        .table("interview_schedules")
        .select("*")
        .order(
            "scheduled_at",
            desc=False,
        )
        .execute()
    )

    return _rows(response)


def delete_interview_schedule(
    schedule_id: str,
) -> None:
    (
        get_supabase()
        .table("interview_schedules")
        .delete()
        .eq(
            "id",
            schedule_id,
        )
        .execute()
    )


# ============================================================
# ONBOARDING ATTENDANCE
# ============================================================

def upsert_onboarding_attendance(
    values: dict[str, Any],
) -> dict[str, Any]:
    response = (
        get_supabase()
        .table("onboarding_attendance")
        .upsert(
            values,
            on_conflict="registration_id",
        )
        .execute()
    )

    return _require_created_row(
        response,
        "onboarding attendance record",
    )


def get_onboarding_attendance(
    registration_id: str,
) -> dict[str, Any] | None:
    response = (
        get_supabase()
        .table("onboarding_attendance")
        .select("*")
        .eq(
            "registration_id",
            registration_id,
        )
        .limit(1)
        .execute()
    )

    return _first(response)


def get_all_onboarding_attendance() -> list[dict[str, Any]]:
    response = (
        get_supabase()
        .table("onboarding_attendance")
        .select("*")
        .order(
            "updated_at",
            desc=True,
        )
        .execute()
    )

    return _rows(response)


# ============================================================
# APPLICATION TIMELINE
# ============================================================

def create_timeline_event(
    registration_id: str,
    event_type: str,
    title: str,
    description: str | None,
    visible_to_student: bool,
    created_by: str,
    ignore_duplicate: bool = False,
) -> dict[str, Any] | None:
    if ignore_duplicate:
        response = (
            get_supabase()
            .table("application_timeline")
            .select("id")
            .eq(
                "registration_id",
                registration_id,
            )
            .eq(
                "event_type",
                event_type,
            )
            .eq(
                "title",
                title,
            )
            .limit(1)
            .execute()
        )

        if _first(response):
            return None

    response = (
        get_supabase()
        .table("application_timeline")
        .insert(
            {
                "registration_id": registration_id,
                "event_type": event_type,
                "title": title,
                "description": description,
                "visible_to_student": (
                    visible_to_student
                ),
                "created_by": created_by,
            }
        )
        .execute()
    )

    return _require_created_row(
        response,
        "timeline event",
    )


def get_application_timeline(
    registration_id: str,
    student_visible_only: bool = False,
) -> list[dict[str, Any]]:
    query = (
        get_supabase()
        .table("application_timeline")
        .select("*")
        .eq(
            "registration_id",
            registration_id,
        )
    )

    if student_visible_only:
        query = query.eq(
            "visible_to_student",
            True,
        )

    response = (
        query
        .order(
            "created_at",
            desc=True,
        )
        .execute()
    )

    return _rows(response)


# ============================================================
# SUPPORT REQUESTS
# ============================================================

def create_support_request(
    values: dict[str, Any],
) -> dict[str, Any]:
    response = (
        get_supabase()
        .table("support_requests")
        .insert(values)
        .execute()
    )

    return _require_created_row(
        response,
        "support request",
    )


def get_all_support_requests() -> list[dict[str, Any]]:
    response = (
        get_supabase()
        .table("support_requests")
        .select("*")
        .order(
            "created_at",
            desc=True,
        )
        .execute()
    )

    return _rows(response)


def get_student_support_requests(
    registration_id: str,
) -> list[dict[str, Any]]:
    response = (
        get_supabase()
        .table("support_requests")
        .select("*")
        .eq(
            "registration_id",
            registration_id,
        )
        .order(
            "created_at",
            desc=True,
        )
        .execute()
    )

    return _rows(response)


def update_support_request(
    request_id: str,
    values: dict[str, Any],
) -> dict[str, Any] | None:
    response = (
        get_supabase()
        .table("support_requests")
        .update(values)
        .eq(
            "id",
            request_id,
        )
        .execute()
    )

    return _first(response)


def delete_support_request(
    request_id: str,
) -> None:
    (
        get_supabase()
        .table("support_requests")
        .delete()
        .eq(
            "id",
            request_id,
        )
        .execute()
    )


# ============================================================
# ACTIVITY LOGS
# ============================================================

def log_activity(
    actor_type: str,
    actor_identifier: str,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    description: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = (
        get_supabase()
        .table("activity_logs")
        .insert(
            {
                "actor_type": actor_type,
                "actor_identifier": actor_identifier,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "description": description,
                "details": details or {},
            }
        )
        .execute()
    )

    return _require_created_row(
        response,
        "activity log",
    )


def get_activity_logs(
    limit: int = 500,
) -> list[dict[str, Any]]:
    response = (
        get_supabase()
        .table("activity_logs")
        .select("*")
        .order(
            "created_at",
            desc=True,
        )
        .limit(limit)
        .execute()
    )

    return _rows(response)


# ============================================================
# DEADLINE REMINDERS
# ============================================================

def get_deadline_reminder_log(
    registration_id: str,
    deadline_date: str,
    reminder_type: str,
) -> dict[str, Any] | None:
    response = (
        get_supabase()
        .table("deadline_reminder_logs")
        .select("*")
        .eq(
            "registration_id",
            registration_id,
        )
        .eq(
            "deadline_date",
            deadline_date,
        )
        .eq(
            "reminder_type",
            reminder_type,
        )
        .limit(1)
        .execute()
    )

    return _first(response)


def record_deadline_reminder(
    registration_id: str,
    deadline_date: str,
    reminder_type: str,
    delivery_status: str,
    message_id: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    response = (
        get_supabase()
        .table("deadline_reminder_logs")
        .upsert(
            {
                "registration_id": registration_id,
                "deadline_date": deadline_date,
                "reminder_type": reminder_type,
                "delivery_status": delivery_status,
                "message_id": message_id,
                "error_message": error_message,
                "sent_at": (
                    utc_now_iso()
                    if delivery_status == "Sent"
                    else None
                ),
            },
            on_conflict=(
                "registration_id,"
                "deadline_date,"
                "reminder_type"
            ),
        )
        .execute()
    )

    return _require_created_row(
        response,
        "deadline reminder log",
    )


# ============================================================
# GENERATED DOCUMENTS
# ============================================================

def create_generated_document_record(
    values: dict[str, Any],
) -> dict[str, Any]:
    response = (
        get_supabase()
        .table("generated_documents")
        .insert(values)
        .execute()
    )

    return _require_created_row(
        response,
        "generated document record",
    )


def update_generated_document_record(
    document_id: str,
    values: dict[str, Any],
) -> dict[str, Any] | None:
    response = (
        get_supabase()
        .table("generated_documents")
        .update(values)
        .eq(
            "id",
            document_id,
        )
        .execute()
    )

    return _first(response)


def get_generated_documents(
    registration_id: str | None = None,
) -> list[dict[str, Any]]:
    query = (
        get_supabase()
        .table("generated_documents")
        .select("*")
    )

    if registration_id:
        query = query.eq(
            "registration_id",
            registration_id,
        )

    response = (
        query
        .order(
            "generated_at",
            desc=True,
        )
        .execute()
    )

    return _rows(response)


# ============================================================
# PORTAL SETTINGS
# ============================================================

def get_all_portal_settings() -> dict[str, dict[str, Any]]:
    response = (
        get_supabase()
        .table("portal_settings")
        .select("*")
        .execute()
    )

    return {
        str(record["setting_key"]): (
            parse_json_dict(
                record.get(
                    "setting_value",
                    {},
                )
            )
        )
        for record in _rows(response)
    }


def get_portal_setting(
    setting_key: str,
    default: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = (
        get_supabase()
        .table("portal_settings")
        .select("setting_value")
        .eq(
            "setting_key",
            setting_key,
        )
        .limit(1)
        .execute()
    )

    record = _first(response)

    if not record:
        return default or {}

    return parse_json_dict(
        record.get(
            "setting_value",
            {},
        )
    )


def update_portal_setting(
    setting_key: str,
    setting_value: dict[str, Any],
    updated_by: str,
    description: str | None = None,
) -> dict[str, Any]:
    response = (
        get_supabase()
        .table("portal_settings")
        .upsert(
            {
                "setting_key": setting_key,
                "setting_value": setting_value,
                "description": description,
                "updated_by": updated_by,
            },
            on_conflict="setting_key",
        )
        .execute()
    )

    return _require_created_row(
        response,
        "portal setting",
    )


# ============================================================
# STORAGE
# ============================================================

def upload_storage_file(
    bucket_name: str,
    storage_path: str,
    file_bytes: bytes,
    content_type: str = "application/octet-stream",
    replace_existing: bool = False,
) -> Any:
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
    downloaded_file = (
        get_supabase()
        .storage
        .from_(bucket_name)
        .download(storage_path)
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
    (
        get_supabase()
        .storage
        .from_(bucket_name)
        .remove([storage_path])
    )


def delete_storage_files(
    bucket_name: str,
    storage_paths: Iterable[str],
) -> None:
    clean_paths = [
        str(path).strip()
        for path in storage_paths
        if str(path).strip()
    ]

    if not clean_paths:
        return

    (
        get_supabase()
        .storage
        .from_(bucket_name)
        .remove(clean_paths)
    )


def create_temporary_file_url(
    bucket_name: str,
    storage_path: str,
    expiry_seconds: int = 600,
) -> str | None:
    response = (
        get_supabase()
        .storage
        .from_(bucket_name)
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
        response.get("signedURL")
        or response.get("signedUrl")
        or response.get("signed_url")
    )

    if not signed_url:
        data = response.get("data")

        if isinstance(data, dict):
            signed_url = (
                data.get("signedURL")
                or data.get("signedUrl")
                or data.get("signed_url")
            )

    return (
        str(signed_url)
        if signed_url
        else None
    )


# ============================================================
# SUBMISSION FILE EXTRACTION AND DELETION
# ============================================================

def extract_submission_files(
    submission: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not submission:
        return []

    files: list[dict[str, Any]] = []

    for file_record in parse_json_list(
        submission.get(
            "proof_files",
            [],
        )
    ):
        if isinstance(file_record, dict):
            files.append(file_record)

    for task_record in parse_json_list(
        submission.get(
            "specific_task_evidence",
            [],
        )
    ):
        if not isinstance(task_record, dict):
            continue

        for file_record in parse_json_list(
            task_record.get(
                "files",
                [],
            )
        ):
            if isinstance(file_record, dict):
                files.append(file_record)

    return files


def extract_submission_storage_paths(
    submission: dict[str, Any] | None,
) -> list[str]:
    return sorted(
        {
            str(
                file_record.get(
                    "path",
                    "",
                )
            ).strip()
            for file_record in extract_submission_files(
                submission
            )
            if str(
                file_record.get(
                    "path",
                    "",
                )
            ).strip()
        }
    )


def delete_registration_and_related_data(
    registration_id: str,
) -> dict[str, int]:
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

    files_deleted = 0
    files_failed = 0

    if storage_paths:
        try:
            delete_storage_files(
                PROOF_SUBMISSION_BUCKET,
                storage_paths,
            )

            files_deleted = len(
                storage_paths
            )
        except Exception:
            files_failed = len(
                storage_paths
            )

    generated_documents = get_generated_documents(
        registration_id
    )

    generated_paths = [
        str(document.get("storage_path"))
        for document in generated_documents
        if document.get("storage_path")
    ]

    if generated_paths:
        try:
            delete_storage_files(
                GENERATED_DOCUMENT_BUCKET,
                generated_paths,
            )
        except Exception:
            pass

    (
        get_supabase()
        .table("registrations")
        .delete()
        .eq(
            "id",
            registration_id,
        )
        .execute()
    )

    if get_registration_by_id(
        registration_id
    ):
        raise RuntimeError(
            "The registration still exists after deletion."
        )

    return {
        "registrations_deleted": 1,
        "registrations_failed": 0,
        "proof_files_deleted": files_deleted,
        "proof_files_failed": files_failed,
    }


def delete_all_registration_data() -> dict[str, int]:
    summary = {
        "registrations_deleted": 0,
        "registrations_failed": 0,
        "proof_files_deleted": 0,
        "proof_files_failed": 0,
    }

    for registration in get_all_registrations():
        registration_id = str(
            registration.get(
                "id",
                "",
            )
        )

        try:
            result = (
                delete_registration_and_related_data(
                    registration_id
                )
            )

            summary[
                "registrations_deleted"
            ] += result[
                "registrations_deleted"
            ]

            summary[
                "proof_files_deleted"
            ] += result[
                "proof_files_deleted"
            ]

            summary[
                "proof_files_failed"
            ] += result[
                "proof_files_failed"
            ]
        except Exception:
            summary[
                "registrations_failed"
            ] += 1

    return summary
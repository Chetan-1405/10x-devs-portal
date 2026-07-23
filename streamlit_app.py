from __future__ import annotations

import hmac
import json
import mimetypes
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from textwrap import dedent
from typing import Any
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

from core.auth import (
    generate_numeric_otp,
    hash_otp,
    hash_password,
    mask_email,
    normalize_mobile_number,
    secure_compare,
    validate_password,
    verify_otp,
    verify_password,
)
from core.constants import (
    ACTIVITY_ACTIONS,
    ALLOWED_OFFER_TEMPLATE_EXTENSIONS,
    ALLOWED_PROJECT_IMAGE_EXTENSIONS,
    ALLOWED_PROOF_EXTENSIONS,
    ANNOUNCEMENT_AUDIENCES,
    ANNOUNCEMENT_PRIORITIES,
    APPLICATION_STATUSES,
    ATTENDANCE_STATUSES,
    CLUB_DOMAIN_NAMES,
    CLUB_INFORMATION,
    CLUB_PROJECT_MEDIA_BUCKET,
    CLUBS,
    DEFAULT_EVALUATOR_PERMISSIONS,
    DEFAULT_PHONE_REGION,
    DEFAULT_PROJECTS_PER_CLUB,
    DOCX_MIME_TYPE,
    EVALUATION_CRITERIA,
    EVALUATION_PROGRESS_OPTIONS,
    GENERATED_DOCUMENT_BUCKET,
    INTERVIEW_MODES,
    INTERVIEW_SCHEDULE_STATUSES,
    LEADERSHIP,
    MANDATORY_TASKS,
    MAX_OFFER_TEMPLATE_SIZE,
    MAX_PROOF_FILES,
    MAX_PROJECT_IMAGE_SIZE,
    MAX_TOTAL_PROOF_SIZE,
    OFFER_LETTER_TEMPLATE_BUCKET,
    OFFER_LETTER_TEMPLATE_PATH,
    ONBOARDING_STATUSES,
    OTP_MAXIMUM_ATTEMPTS,
    OTP_VALIDITY_MINUTES,
    PREFERRED_CONTACT_MODES,
    PROJECT_STATUSES,
    PROOF_SUBMISSION_BUCKET,
    REQUIRED_OFFER_TEMPLATE_PLACEHOLDERS,
    SECOND_YEAR_TASKS,
    SUBMISSION_STATES,
    SUPPORT_REQUEST_STATUSES,
    TASK_DOCUMENT_BUCKET,
    TASK_DOCUMENTS,
    THIRD_YEAR_TASKS,
    YEARS,
)
from core.database import (
    create_registration,
    bulk_update_registration_status,
    create_announcement,
    create_club_project,
    create_evaluator_account,
    create_generated_document_record,
    create_password_reset_otp,
    create_support_request,
    create_temporary_file_url,
    delete_all_registration_data,
    delete_announcement,
    delete_club_project,
    delete_evaluator_account,
    delete_interview_schedule,
    delete_registration_and_related_data,
    delete_storage_file,
    delete_support_request,
    download_storage_file,
    extend_student_deadline,
    finalize_submission,
    find_duplicate_registration,
    get_activity_logs,
    get_all_announcements,
    get_all_club_projects,
    get_all_evaluators,
    get_all_interview_schedules,
    get_all_onboarding_attendance,
    get_all_portal_settings,
    get_all_proof_submissions,
    get_all_registrations,
    get_announcement_recipients,
    get_application_timeline,
    get_evaluator_by_username,
    get_generated_documents,
    get_interview_schedule,
    get_latest_password_reset_otp,
    get_onboarding_attendance,
    get_portal_setting,
    get_proof_submission,
    get_published_announcements,
    get_published_club_projects,
    get_registration_by_email,
    get_registration_by_id,
    get_student,
    get_student_support_requests,
    get_all_support_requests,
    invalidate_password_reset_otps,
    log_activity,
    mark_otp_used,
    increment_otp_attempt,
    record_announcement_email,
    record_deadline_reminder,
    reopen_submission,
    save_submission_draft,
    source_url_already_exists,
    update_announcement,
    update_club_project,
    update_evaluator_account,
    update_generated_document_record,
    update_portal_setting,
    update_proof_submission,
    update_registration,
    update_student_last_login,
    update_student_profile,
    update_support_request,
    upload_storage_file,
    upsert_interview_schedule,
    upsert_onboarding_attendance,
)
from core.email_service import (
    email_is_configured,
    send_announcement_email,
    send_deadline_reminder_email,
    send_interview_schedule_email,
    send_offer_letter_email,
    send_onboarding_email,
    send_password_reset_otp_email,
    send_registration_email,
    send_status_email,
    send_submission_under_scrutiny_email,
    send_support_response_email,
)
from core.project_catalog import DEFAULT_CLUB_PROJECTS, merge_project_catalogues
from core.pdf_service import (
    generate_selection_certificate_pdf,
    generate_submission_receipt_pdf,
    validate_offer_letter_template,
)


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="10x Devs",
    page_icon="10x",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CSS
# ============================================================

CSS_PATH = Path("assets/style.css")

if CSS_PATH.exists():
    st.html(
        f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>"
    )
else:
    st.warning(
        "The portal stylesheet could not be found."
    )


# ============================================================
# SESSION STATE
# ============================================================

SESSION_DEFAULTS: dict[str, Any] = {
    "page": "landing",
    "student_authenticated": False,
    "admin_authenticated": False,
    "evaluator_authenticated": False,
    "student_registration_number": None,
    "evaluator_id": None,
    "evaluator_username": None,
    "project_club_filter": "All Clubs",
    "password_reset_stage": "request",
    "password_reset_registration_id": None,
    "password_reset_email": None,
    "password_reset_registration_number": None,
    "submission_success_notice": None,
    "registration_processing": False,
    "registration_success": None,
    "password_reset_completed": False,
}

for session_key, default_value in SESSION_DEFAULTS.items():
    if session_key not in st.session_state:
        st.session_state[session_key] = default_value


# ============================================================
# BASIC HELPERS
# ============================================================

def render_html(
    html_content: str,
) -> None:
    st.html(
        dedent(
            html_content
        ).strip()
    )


def configuration_is_valid() -> bool:
    required_settings = [
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "ADMIN_USERNAME",
        "ADMIN_PASSWORD",
    ]

    missing_settings = [
        setting
        for setting in required_settings
        if not str(
            st.secrets.get(
                setting,
                "",
            )
        ).strip()
    ]

    if missing_settings:
        st.error(
            "Application configuration is incomplete."
        )

        st.write(
            "Missing settings: "
            + ", ".join(
                missing_settings
            )
        )

        return False

    return True


def normalize_registration_number(
    value: str,
) -> str:
    return (
        value
        .strip()
        .upper()
        .replace(" ", "")
    )


def normalize_name(
    value: str,
) -> str:
    return " ".join(
        value.strip().split()
    )


def is_valid_email(
    value: str,
) -> bool:
    value = value.strip()

    email_pattern = (
        r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+"
        r"@[A-Za-z0-9-]+"
        r"(?:\.[A-Za-z0-9-]+)+$"
    )

    return bool(
        re.fullmatch(
            email_pattern,
            value,
        )
    )


def is_valid_url(
    value: str,
) -> bool:
    if not value.strip():
        return True

    parsed_url = urlparse(
        value.strip()
    )

    return (
        parsed_url.scheme
        in {
            "http",
            "https",
        }
        and bool(
            parsed_url.netloc
        )
    )


def clean_filename(
    filename: str,
) -> str:
    return (
        Path(filename)
        .name
        .replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
    )


def safe_widget_key(
    value: str,
) -> str:
    return re.sub(
        r"[^A-Za-z0-9]+",
        "_",
        value,
    ).strip("_").lower()


def value_is_present(
    value: Any,
) -> bool:
    if value is None:
        return False

    try:
        if pd.isna(value):
            return False
    except (
        TypeError,
        ValueError,
    ):
        pass

    return bool(
        str(value).strip()
    )


def parse_json_list(
    value: Any,
) -> list[Any]:
    if isinstance(
        value,
        list,
    ):
        return value

    if isinstance(
        value,
        tuple,
    ):
        return list(value)

    if isinstance(
        value,
        str,
    ):
        try:
            decoded_value = json.loads(
                value
            )

            if isinstance(
                decoded_value,
                list,
            ):
                return decoded_value
        except json.JSONDecodeError:
            return []

    return []


def parse_json_dict(
    value: Any,
) -> dict[str, Any]:
    if isinstance(
        value,
        dict,
    ):
        return value

    if isinstance(
        value,
        str,
    ):
        try:
            decoded_value = json.loads(
                value
            )

            if isinstance(
                decoded_value,
                dict,
            ):
                return decoded_value
        except json.JSONDecodeError:
            return {}

    return {}


def utc_now_iso() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def parse_database_datetime(
    value: Any,
) -> datetime | None:
    if value is None:
        return None

    if isinstance(
        value,
        datetime,
    ):
        return value

    try:
        return datetime.fromisoformat(
            str(value).replace(
                "Z",
                "+00:00",
            )
        )
    except ValueError:
        return None


def format_database_datetime(
    value: Any,
) -> str:
    parsed_value = parse_database_datetime(
        value
    )

    if parsed_value is None:
        return (
            str(value)
            if value
            else "Not available"
        )

    return parsed_value.strftime(
        "%d %B %Y, %I:%M %p"
    )


def mandatory_task_for_student(
    student: dict[str, Any],
) -> str:
    return MANDATORY_TASKS.get(
        str(
            student.get(
                "study_year",
                "",
            )
        ),
        "Mandatory Portfolio",
    )


def allowed_specific_tasks(
    student: dict[str, Any],
) -> list[str]:
    study_year = str(
        student.get(
            "study_year",
            "",
        )
    )

    club = str(
        student.get(
            "club",
            "",
        )
    )

    if study_year == "2nd Year":
        return list(
            SECOND_YEAR_TASKS
        )

    if study_year == "3rd Year":
        return list(
            THIRD_YEAR_TASKS.get(
                club,
                [],
            )
        )

    return []


def load_task_document(
    study_year: str,
) -> bytes | None:
    filename = TASK_DOCUMENTS.get(
        study_year
    )

    if not filename:
        return None

    try:
        return download_storage_file(
            bucket_name=TASK_DOCUMENT_BUCKET,
            storage_path=filename,
        )
    except Exception:
        return None


def load_offer_letter_template() -> bytes | None:
    try:
        return download_storage_file(
            bucket_name=OFFER_LETTER_TEMPLATE_BUCKET,
            storage_path=OFFER_LETTER_TEMPLATE_PATH,
        )
    except Exception:
        return None


def get_portal_settings_safe() -> dict[str, dict[str, Any]]:
    try:
        return get_all_portal_settings()
    except Exception:
        return {}


def get_setting_safe(
    setting_key: str,
    default: dict[str, Any],
) -> dict[str, Any]:
    try:
        return get_portal_setting(
            setting_key,
            default,
        )
    except Exception:
        return default


def registration_is_open() -> bool:
    settings = get_setting_safe(
        "registration_settings",
        {
            "open": True,
            "allowed_years": YEARS,
        },
    )

    return bool(
        settings.get(
            "open",
            True,
        )
    )


def submission_is_open() -> bool:
    settings = get_setting_safe(
        "submission_settings",
        {
            "open": True,
        },
    )

    return bool(
        settings.get(
            "open",
            True,
        )
    )


def maintenance_mode_settings() -> dict[str, Any]:
    return get_setting_safe(
        "maintenance_mode",
        {
            "enabled": False,
            "message": (
                "The portal is temporarily under maintenance."
            ),
        },
    )


def student_deadline_has_passed(
    student: dict[str, Any],
) -> bool:
    task_deadline = student.get(
        "task_deadline"
    )

    if not task_deadline:
        return False

    try:
        deadline_date = date.fromisoformat(
            str(task_deadline)
        )
    except ValueError:
        return False

    return date.today() > deadline_date


def is_reserved_admin_value(
    value: str,
) -> bool:
    normalized_value = (
        value
        .strip()
        .casefold()
    )

    configured_admin = str(
        st.secrets.get(
            "ADMIN_USERNAME",
            "admin",
        )
    ).strip().casefold()

    return normalized_value in {
        "admin",
        "administrator",
        configured_admin,
    }


# ============================================================
# SESSION AND NAVIGATION
# ============================================================

def logout_everyone() -> None:
    st.session_state[
        "student_authenticated"
    ] = False

    st.session_state[
        "admin_authenticated"
    ] = False

    st.session_state[
        "evaluator_authenticated"
    ] = False

    st.session_state[
        "student_registration_number"
    ] = None

    st.session_state[
        "evaluator_id"
    ] = None

    st.session_state[
        "evaluator_username"
    ] = None


def navigate_to(
    page_name: str,
    *,
    logout: bool = False,
) -> None:
    if logout:
        logout_everyone()

    st.session_state[
        "page"
    ] = page_name

    st.rerun()


def reset_password_reset_state() -> None:
    st.session_state[
        "password_reset_stage"
    ] = "request"

    st.session_state[
        "password_reset_registration_id"
    ] = None

    st.session_state[
        "password_reset_email"
    ] = None

    st.session_state[
        "password_reset_registration_number"
    ] = None

    st.session_state[
        "password_reset_completed"
    ] = False


# ============================================================
# ACTIVITY LOG SAFE WRAPPER
# ============================================================

def log_activity_safe(
    *,
    actor_type: str,
    actor_identifier: str,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    description: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    try:
        log_activity(
            actor_type=actor_type,
            actor_identifier=actor_identifier,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            details=details,
        )
    except Exception:
        pass


# ============================================================
# EMAIL RESULT TRACKING
# ============================================================

def update_email_tracking_safe(
    registration_id: str,
    values: dict[str, Any],
) -> None:
    try:
        update_registration(
            registration_id,
            values,
        )
    except Exception:
        pass


def record_registration_email_result(
    registration_id: str,
    *,
    success: bool,
    message_id: str | None = None,
    error_message: str | None = None,
) -> None:
    update_email_tracking_safe(
        registration_id,
        {
            "email_status": (
                "Sent"
                if success
                else "Failed"
            ),
            "email_message_id": (
                message_id
                if success
                else None
            ),
            "email_error": (
                None
                if success
                else str(
                    error_message
                    or "Unknown registration-email error"
                )[:1000]
            ),
        },
    )


def record_submission_email_result(
    registration_id: str,
    *,
    success: bool,
    message_id: str | None = None,
    error_message: str | None = None,
) -> None:
    update_email_tracking_safe(
        registration_id,
        {
            "submission_email_status": (
                "Sent"
                if success
                else "Failed"
            ),
            "submission_email_sent_at": (
                utc_now_iso()
                if success
                else None
            ),
            "submission_email_message_id": (
                message_id
                if success
                else None
            ),
            "submission_email_error": (
                None
                if success
                else str(
                    error_message
                    or "Unknown submission-email error"
                )[:1000]
            ),
        },
    )


def record_status_email_result(
    student: dict[str, Any],
    *,
    success: bool,
    message_id: str | None = None,
    error_message: str | None = None,
) -> None:
    update_email_tracking_safe(
        str(
            student["id"]
        ),
        {
            "status_email_status": (
                "Sent"
                if success
                else "Failed"
            ),
            "status_email_sent_at": (
                utc_now_iso()
                if success
                else None
            ),
            "status_email_message_id": (
                message_id
                if success
                else None
            ),
            "status_email_error": (
                None
                if success
                else str(
                    error_message
                    or "Unknown status-email error"
                )[:1000]
            ),
        },
    )


def record_offer_email_result(
    student: dict[str, Any],
    *,
    success: bool,
    message_id: str | None = None,
    error_message: str | None = None,
) -> None:
    update_email_tracking_safe(
        str(
            student["id"]
        ),
        {
            "offer_email_status": (
                "Sent"
                if success
                else "Failed"
            ),
            "offer_email_sent_at": (
                utc_now_iso()
                if success
                else None
            ),
            "offer_email_message_id": (
                message_id
                if success
                else None
            ),
            "offer_email_error": (
                None
                if success
                else str(
                    error_message
                    or "Unknown offer-email error"
                )[:1000]
            ),
        },
    )


# ============================================================
# SIDEBAR
# ============================================================

def render_sidebar() -> None:
    with st.sidebar:
        render_html(
            """
            <div class="sidebar-brand-wrapper">
                <a
                    class="sidebar-brand-link"
                    href="?home=1"
                    target="_self"
                    aria-label="Return to 10x Devs home"
                >
                    <div class="sidebar-logo-box">
                        10x
                    </div>

                    <div class="sidebar-brand-content">
                        <div class="sidebar-brand-text">
                            <span>10x</span> Devs
                        </div>

                        <div class="sidebar-brand-caption">
                            Student Technical Community
                        </div>
                    </div>
                </a>
            </div>

            <div class="sidebar-subtitle">
                Student Club Registration Portal
            </div>
            """
        )

        st.divider()

        render_html(
            """
            <div class="sidebar-section-title">
                Technical Clubs
            </div>

            <div class="sidebar-club-list">
                <div class="sidebar-club-item">
                    <span class="sidebar-club-dot"></span>
                    <span class="sidebar-club-name">
                        Computer Vision Club
                    </span>
                </div>

                <div class="sidebar-club-item">
                    <span class="sidebar-club-dot"></span>
                    <span class="sidebar-club-name">
                        Web Development Club
                    </span>
                </div>

                <div class="sidebar-club-item">
                    <span class="sidebar-club-dot"></span>
                    <span class="sidebar-club-name">
                        ML Club
                    </span>
                </div>
            </div>
            """
        )


# ============================================================
# PUBLIC ANNOUNCEMENTS
# ============================================================

def render_public_announcements() -> None:
    try:
        announcements = get_published_announcements(
            None
        )
    except Exception:
        announcements = []

    if not announcements:
        return

    st.markdown(
        "### Latest Announcements"
    )

    for announcement in announcements[:3]:
        priority = str(
            announcement.get(
                "priority",
                "Normal",
            )
        )

        if priority == "Urgent":
            st.error(
                f"**{announcement['title']}**\n\n"
                f"{announcement['body']}"
            )
        elif priority == "Important":
            st.warning(
                f"**{announcement['title']}**\n\n"
                f"{announcement['body']}"
            )
        else:
            st.info(
                f"**{announcement['title']}**\n\n"
                f"{announcement['body']}"
            )


# ============================================================
# SHARED LOGIN PROCESSOR
# ============================================================

def process_login_credentials(
    identifier: str,
    password: str,
) -> None:
    clean_identifier = identifier.strip()

    if not clean_identifier or not password:
        st.error(
            "Enter your account ID and password."
        )
        return

    admin_username = str(
        st.secrets[
            "ADMIN_USERNAME"
        ]
    ).strip()

    admin_password = str(
        st.secrets[
            "ADMIN_PASSWORD"
        ]
    )

    if secure_compare(
        clean_identifier.casefold(),
        admin_username.casefold(),
    ):
        if secure_compare(
            password,
            admin_password,
        ):
            logout_everyone()

            st.session_state[
                "admin_authenticated"
            ] = True

            st.rerun()

        st.error(
            "Incorrect credentials."
        )
        return

    try:
        evaluator = get_evaluator_by_username(
            clean_identifier.lower()
        )
    except Exception:
        evaluator = None

    if evaluator:
        if not evaluator.get(
            "is_active",
            True,
        ):
            st.error(
                "This evaluator account is inactive."
            )
            return

        if verify_password(
            password,
            str(
                evaluator[
                    "password_hash"
                ]
            ),
        ):
            logout_everyone()

            st.session_state[
                "evaluator_authenticated"
            ] = True

            st.session_state[
                "evaluator_id"
            ] = str(
                evaluator["id"]
            )

            st.session_state[
                "evaluator_username"
            ] = str(
                evaluator["username"]
            )

            try:
                update_evaluator_account(
                    str(
                        evaluator["id"]
                    ),
                    {
                        "last_login_at": utc_now_iso(),
                    },
                )
            except Exception:
                pass

            st.rerun()

        st.error(
            "Incorrect credentials."
        )
        return

    try:
        student = get_student(
            normalize_registration_number(
                clean_identifier
            )
        )
    except Exception as error:
        st.error(
            "The login service is unavailable."
        )

        st.code(
            str(error)
        )
        return

    if not student:
        st.error(
            "Incorrect credentials."
        )
        return

    if not student.get(
        "is_active",
        True,
    ):
        st.error(
            "This account is inactive. Contact the administrator."
        )
        return

    if verify_password(
        password,
        str(
            student[
                "password_hash"
            ]
        ),
    ):
        logout_everyone()

        st.session_state[
            "student_authenticated"
        ] = True

        st.session_state[
            "student_registration_number"
        ] = str(
            student[
                "registration_number"
            ]
        )

        try:
            update_student_last_login(
                str(
                    student["id"]
                )
            )
        except Exception:
            pass

        st.rerun()

    st.error(
        "Incorrect credentials."
    )


# ============================================================
# LANDING PAGE
# ============================================================

def render_landing_page() -> None:
    render_html(
        """
        <div class="home-page-anchor"></div>
        """
    )

    hero_left, hero_right = st.columns(
        [1.08, 0.92],
        gap="large",
        vertical_alignment="center",
    )

    with hero_left:
        render_html(
            """
            <section class="split-home-intro">
                <div class="split-brand-row">
                    <div class="split-brand-logo">10x</div>

                    <div>
                        <div class="split-brand-name">
                            <span>10x</span> Devs
                        </div>

                        <div class="split-brand-caption">
                            Student Technical Community
                        </div>
                    </div>
                </div>

                <div class="split-trust-badge">
                    STUDENT PROJECT CLUB PLATFORM
                </div>

                <h1 class="split-home-title">
                    Build Faster.<br>
                    Grow at <span>10x.</span>
                </h1>

                <p class="split-home-description">
                    Join the Computer Vision, Web Development or
                    Machine Learning Club. Complete practical tasks,
                    build real projects and strengthen your technical
                    portfolio with a focused student community.
                </p>

                <div class="split-feature-grid">
                    <article class="split-feature-card">
                        <div class="split-feature-title">
                            Practical by default
                        </div>

                        <div class="split-feature-description">
                            Learn through working applications,
                            deployment and technical demonstrations.
                        </div>
                    </article>

                    <article class="split-feature-card">
                        <div class="split-feature-title">
                            Built for collaboration
                        </div>

                        <div class="split-feature-description">
                            Work with club members, exchange ideas and
                            contribute to meaningful technical projects.
                        </div>
                    </article>
                </div>
            </section>
            """
        )

    with hero_right:
        with st.container(
            border=True
        ):
            render_html(
                """
                <div class="home-login-card-marker"></div>

                <div class="home-login-heading">
                    Sign In
                </div>

                <div class="home-login-subheading">
                    Access your student, evaluator or administrator
                    account.
                </div>
                """
            )

            with st.form(
                "home_login_form",
                clear_on_submit=False,
            ):
                identifier = st.text_input(
                    "Account ID",
                    placeholder=(
                        "Registration number or username"
                    ),
                )

                password = st.text_input(
                    "Password",
                    type="password",
                    placeholder="Enter your password",
                )

                submitted = st.form_submit_button(
                    "Access Account",
                    type="primary",
                    use_container_width=True,
                )

            if submitted:
                process_login_credentials(
                    identifier,
                    password,
                )

            account_column, password_column = st.columns(
                2,
                gap="small",
            )

            with account_column:
                if st.button(
                    "Create Account",
                    key="home_create_account",
                    use_container_width=True,
                ):
                    navigate_to(
                        "register",
                        logout=True,
                    )

            with password_column:
                if st.button(
                    "Forgot Password",
                    key="home_forgot_password",
                    use_container_width=True,
                ):
                    reset_password_reset_state()

                    navigate_to(
                        "forgot_password"
                    )

            render_html(
                """
                <div class="home-login-security">
                    STUDENT CLUB PLATFORM
                </div>
                """
            )

    render_html(
        """
        <section class="landing-section home-about-section">
            <div class="section-label">
                ABOUT THE COMMUNITY
            </div>

            <h2 class="section-title">
                Learn, build and contribute
            </h2>

            <p class="section-description">
                10x Devs is a student technical community focused on
                practical implementation, peer learning and
                project-based development. The community was officially
                inaugurated on 25 January 2025.
            </p>

            <div class="information-grid">
                <article class="information-card interactive-card">
                    <div class="information-number">01</div>

                    <h3 class="information-title">
                        Practical learning
                    </h3>

                    <p class="information-description">
                        Complete working applications and learn through
                        real implementation.
                    </p>
                </article>

                <article class="information-card interactive-card">
                    <div class="information-number">02</div>

                    <h3 class="information-title">
                        Team collaboration
                    </h3>

                    <p class="information-description">
                        Share knowledge, review implementations and
                        contribute to collaborative projects.
                    </p>
                </article>

                <article class="information-card interactive-card">
                    <div class="information-number">03</div>

                    <h3 class="information-title">
                        Professional growth
                    </h3>

                    <p class="information-description">
                        Practise GitHub, deployment, documentation and
                        technical demonstrations.
                    </p>
                </article>
            </div>
        </section>
        """
    )

    render_public_announcements()

    st.markdown(
        "## Explore the Technical Clubs"
    )

    st.caption(
        "View each club’s focus areas and published student projects."
    )

    club_columns = st.columns(
        3
    )

    for column, club_name in zip(
        club_columns,
        CLUBS,
    ):
        club_information = CLUB_INFORMATION[
            club_name
        ]

        with column:
            with st.container(
                border=True
            ):
                st.caption(
                    str(
                        club_information[
                            "code"
                        ]
                    )
                )

                st.subheader(
                    club_name
                )

                st.write(
                    str(
                        club_information[
                            "description"
                        ]
                    )
                )

                technologies = club_information[
                    "technologies"
                ]

                st.caption(
                    " • ".join(
                        str(item)
                        for item in technologies
                    )
                )

                if st.button(
                    "View Club Projects",
                    key=(
                        "landing_projects_"
                        + safe_widget_key(
                            club_name
                        )
                    ),
                    use_container_width=True,
                ):
                    st.session_state[
                        "project_club_filter"
                    ] = club_name

                    navigate_to(
                        "projects"
                    )

    st.markdown(
        "## Featured Projects"
    )

    st.caption(
        "Selected projects completed through the 10x Devs community."
    )

    render_project_showcase(
        featured_only=True,
        maximum_projects=6,
    )

    render_html(
        """
        <section class="landing-section">
            <div class="section-label">
                COMMUNITY LEADERSHIP
            </div>

            <h2 class="section-title">
                Leadership
            </h2>

            <div class="leadership-grid">
                <article class="leadership-card interactive-card">
                    <div class="leadership-role">
                        INAUGURATED BY
                    </div>

                    <h3 class="leadership-name">
                        Dr. Ravi Kadiyala
                    </h3>

                    <p class="leadership-position">
                        Principal
                    </p>
                </article>

                <article class="leadership-card interactive-card">
                    <div class="leadership-role">
                        PRESIDENT
                    </div>

                    <h3 class="leadership-name">
                        Dr. Ch. Suresh Babu
                    </h3>

                    <p class="leadership-position">
                        HOD, CSE (AI &amp; ML)
                    </p>
                </article>

                <article class="leadership-card interactive-card">
                    <div class="leadership-role">
                        SECRETARY
                    </div>

                    <h3 class="leadership-name">
                        A. Sri Chaitanya
                    </h3>

                    <p class="leadership-position">
                        (Ph.D)
                    </p>
                </article>

                <article class="leadership-card interactive-card">
                    <div class="leadership-role">
                        COORDINATOR
                    </div>

                    <h3 class="leadership-name">
                        Chetan Ventrapragada & Mahani Koushal
                    </h3>

                    <p class="leadership-position">
                        Final-Year Students
                    </p>
                </article>
            </div>
        </section>

        <footer class="landing-footer">
            <div>
                <div class="footer-title">
                    10x Devs Student Club Registration Portal
                </div>

                <div class="footer-description">
                    Register, complete practical tasks and submit your
                    technical work for evaluation.
                </div>
            </div>

            <div class="footer-badge">
                Inaugurated 25 January 2025
            </div>
        </footer>
        """
    )


# ============================================================
# PUBLIC PROJECT SHOWCASE
# ============================================================

def render_project_showcase(
    *,
    featured_only: bool = False,
    maximum_projects: int | None = None,
    club_filter: str | None = None,
) -> None:
    try:
        database_projects = get_published_club_projects(
            club_filter
        )
    except Exception:
        database_projects = []

    projects = merge_project_catalogues(
        database_projects
    )

    if club_filter:
        projects = [
            project
            for project in projects
            if project.get("club")
            == club_filter
        ]

    if featured_only:
        projects = [
            project
            for project in projects
            if project.get("featured")
        ]

    if maximum_projects is not None:
        projects = projects[:maximum_projects]

    if not projects:
        st.info(
            "No published projects are available in this section yet."
        )
        return

    for project_index in range(
        0,
        len(projects),
        3,
    ):
        row_projects = projects[
            project_index:
            project_index + 3
        ]

        columns = st.columns(3)

        for column, project in zip(
            columns,
            row_projects,
        ):
            with column:
                with st.container(border=True):
                    thumbnail_path = project.get(
                        "thumbnail_storage_path"
                    )

                    local_thumbnail = project.get(
                        "local_thumbnail"
                    )

                    if thumbnail_path:
                        try:
                            image_url = create_temporary_file_url(
                                bucket_name=CLUB_PROJECT_MEDIA_BUCKET,
                                storage_path=str(
                                    thumbnail_path
                                ),
                                expiry_seconds=600,
                            )

                            if image_url:
                                st.image(
                                    image_url,
                                    use_container_width=True,
                                )
                        except Exception:
                            pass

                    elif (
                        local_thumbnail
                        and Path(
                            str(local_thumbnail)
                        ).exists()
                    ):
                        st.image(
                            str(local_thumbnail),
                            use_container_width=True,
                        )

                    badge_text = (
                        "FEATURED PROJECT"
                        if project.get("featured")
                        else str(
                            project.get(
                                "club",
                                "CLUB PROJECT",
                            )
                        ).upper()
                    )

                    st.caption(badge_text)

                    st.subheader(
                        str(
                            project.get(
                                "title",
                                "Untitled Project",
                            )
                        )
                    )

                    st.write(
                        str(
                            project.get(
                                "short_description",
                                "",
                            )
                        )
                    )

                    technologies = project.get(
                        "technologies",
                        [],
                    )

                    if isinstance(
                        technologies,
                        list,
                    ) and technologies:
                        st.caption(
                            " • ".join(
                                str(item)
                                for item in technologies
                            )
                        )

                    student_names = project.get(
                        "student_names",
                        [],
                    )

                    if (
                        isinstance(
                            student_names,
                            list,
                        )
                        and student_names
                    ):
                        st.write(
                            "**Contributors:** "
                            + ", ".join(
                                str(name)
                                for name in student_names
                                if str(name).strip()
                            )
                        )

                    link_values = [
                        (
                            "Code",
                            project.get(
                                "github_url"
                            ),
                        ),
                        (
                            "Live",
                            project.get(
                                "live_url"
                            ),
                        ),
                        (
                            "Demo",
                            project.get(
                                "demo_url"
                            ),
                        ),
                    ]

                    available_links = [
                        item
                        for item in link_values
                        if item[1]
                    ]

                    if available_links:
                        link_columns = st.columns(
                            len(available_links)
                        )

                        for link_column, (
                            link_label,
                            link_url,
                        ) in zip(
                            link_columns,
                            available_links,
                        ):
                            with link_column:
                                st.link_button(
                                    link_label,
                                    str(link_url),
                                    use_container_width=True,
                                )
                    else:
                        st.caption(
                            "Repository and demo links can be added "
                            "from the administrator project manager."
                        )

                    detailed_description = project.get(
                        "detailed_description"
                    )

                    if detailed_description:
                        with st.expander(
                            "Project Details"
                        ):
                            st.write(
                                str(
                                    detailed_description
                                )
                            )

                            academic_year = project.get(
                                "academic_year"
                            )

                            if academic_year:
                                st.caption(
                                    f"Academic year: {academic_year}"
                                )


def render_projects_page() -> None:
    st.title(
        "Club Project Showcase"
    )

    st.write(
        "Explore projects completed and published by the "
        "technical clubs."
    )

    try:
        database_projects = get_published_club_projects()
    except Exception:
        database_projects = []

    complete_catalogue = merge_project_catalogues(
        database_projects
    )

    summary_columns = st.columns(4)

    summary_columns[0].metric(
        "Completed Projects",
        len(complete_catalogue),
    )

    summary_columns[1].metric(
        "Machine Learning",
        sum(
            1
            for project in complete_catalogue
            if project.get("club") == "ML Club"
        ),
    )

    summary_columns[2].metric(
        "Computer Vision",
        sum(
            1
            for project in complete_catalogue
            if project.get("club") == "Computer Vision Club"
        ),
    )

    summary_columns[3].metric(
        "Web Development",
        sum(
            1
            for project in complete_catalogue
            if project.get("club") == "Web Development Club"
        ),
    )

    filter_options = [
        "All Clubs",
        *CLUBS,
    ]

    current_filter = st.session_state.get(
        "project_club_filter",
        "All Clubs",
    )

    selected_index = (
        filter_options.index(
            current_filter
        )
        if current_filter in filter_options
        else 0
    )

    selected_club = st.selectbox(
        "Filter projects by club",
        filter_options,
        index=selected_index,
    )

    st.session_state[
        "project_club_filter"
    ] = selected_club

    render_project_showcase(
        club_filter=(
            None
            if selected_club
            == "All Clubs"
            else selected_club
        )
    )

    if st.button(
        "Return to Home",
        use_container_width=True,
    ):
        navigate_to(
            "landing"
        )


# ============================================================
# REGISTRATION PAGE
# ============================================================

def render_registration_page() -> None:
    st.title("Create Your Student Account")

    success_data = st.session_state.get("registration_success")
    if success_data:
        st.success(
            "Account created successfully. Your registration is safely stored."
        )
        st.write(f"**Application reference:** {success_data.get('application_reference', 'Generated')}")
        st.write(f"**Registration number:** {success_data.get('registration_number', '')}")
        email_status = success_data.get("email_status", "Pending")
        if email_status == "Sent":
            st.info("The confirmation email and task document were sent.")
        else:
            st.warning(
                "Your account is active, but the confirmation email may be delayed. "
                "You can continue to login."
            )
        if st.button("Continue to Login", type="primary", use_container_width=True):
            st.session_state["registration_success"] = None
            st.session_state["registration_processing"] = False
            navigate_to("login", logout=True)
        return

    if not registration_is_open():
        st.warning("New registration is currently closed.")
        return

    st.info(
        "Register for one technical club. Your registered club "
        "cannot be changed by the student after registration."
    )

    processing = bool(st.session_state.get("registration_processing", False))

    with st.form("registration_form", clear_on_submit=False):
        full_name = st.text_input("Full name")
        registration_number = st.text_input("Registration number")

        first_row_one, first_row_two = st.columns(2)
        with first_row_one:
            study_year = st.selectbox("Current academic year", YEARS)
        with first_row_two:
            email = st.text_input("Email address")

        second_row_one, second_row_two = st.columns(2)
        with second_row_one:
            mobile_number = st.text_input(
                "Mobile number",
                placeholder="+91XXXXXXXXXX",
                help=(
                    "Enter a valid mobile number. Indian numbers "
                    "may be entered with or without +91."
                ),
            )
        with second_row_two:
            preferred_contact_mode = st.selectbox(
                "Preferred contact mode", PREFERRED_CONTACT_MODES
            )

        password_column, confirmation_column = st.columns(2)
        with password_column:
            password = st.text_input("Create password", type="password")
        with confirmation_column:
            confirm_password = st.text_input("Confirm password", type="password")

        club = st.selectbox("Select one club", CLUBS)
        declaration = st.checkbox(
            "I confirm that the provided details are accurate and understand "
            "that my registered club cannot be changed through the student dashboard."
        )

        submitted = st.form_submit_button(
            "Creating Account..." if processing else "Create Account",
            type="primary",
            use_container_width=True,
            disabled=processing,
        )

    if not submitted or processing:
        return

    st.session_state["registration_processing"] = True

    clean_name = normalize_name(full_name)
    clean_registration_number = normalize_registration_number(registration_number)
    clean_email = email.strip().lower()
    errors: list[str] = []

    if len(clean_name) < 3:
        errors.append("Enter your complete name.")
    if is_reserved_admin_value(clean_name) or is_reserved_admin_value(clean_registration_number):
        errors.append("Admin-related account values are reserved.")
    if len(clean_registration_number) < 5:
        errors.append("Enter a valid registration number.")
    if not is_valid_email(clean_email):
        errors.append("Enter a valid email address.")

    try:
        normalized_mobile = normalize_mobile_number(mobile_number, DEFAULT_PHONE_REGION)
    except ValueError as error:
        normalized_mobile = ""
        errors.append(str(error))

    errors.extend(validate_password(password))
    if password != confirm_password:
        errors.append("Passwords do not match.")
    if not declaration:
        errors.append("Accept the registration declaration.")

    if errors:
        st.session_state["registration_processing"] = False
        for error_message in errors:
            st.error(error_message)
        return

    try:
        duplicate_message = find_duplicate_registration(
            registration_number=clean_registration_number,
            email=clean_email,
            mobile_number=normalized_mobile,
        )
        if duplicate_message:
            st.session_state["registration_processing"] = False
            st.error(duplicate_message)
            return

        task_document = load_task_document(study_year)
        if task_document is None:
            st.session_state["registration_processing"] = False
            st.error(
                f"The {study_year} task document is currently unavailable. "
                "Contact the administrator."
            )
            return

        deadline_settings = get_setting_safe(
            "deadline_settings",
            {"default_days": int(st.secrets.get("TASK_DEADLINE_DAYS", 2))},
        )
        deadline_days = int(
            deadline_settings.get(
                "default_days", st.secrets.get("TASK_DEADLINE_DAYS", 2)
            )
        )
        task_deadline = date.today() + timedelta(days=deadline_days)

        # Database insert happens before email. Database uniqueness constraints
        # are the final protection against simultaneous duplicate submissions.
        student = create_registration(
            {
                "full_name": clean_name,
                "registration_number": clean_registration_number,
                "study_year": study_year,
                "email": clean_email,
                "mobile_number": normalized_mobile,
                "preferred_contact_mode": preferred_contact_mode,
                "password_hash": hash_password(password),
                "club": club,
                "task_deadline": task_deadline.isoformat(),
                "email_status": "Pending",
                "application_status": "Registered",
                "is_active": True,
            }
        )
    except Exception as error:
        st.session_state["registration_processing"] = False
        error_text = str(error).lower()
        if "duplicate" in error_text or "unique" in error_text or "23505" in error_text:
            st.error(
                "An account already exists with this registration number, "
                "email address, mobile number, or application reference."
            )
        else:
            st.error("The student account could not be created.")
            st.code(str(error))
        return

    email_status = "Pending"
    if email_is_configured():
        try:
            message_id = send_registration_email(student, task_document)
            record_registration_email_result(
                str(student["id"]), success=True, message_id=message_id
            )
            email_status = "Sent"
        except Exception as email_error:
            record_registration_email_result(
                str(student["id"]),
                success=False,
                error_message=str(email_error),
            )
            email_status = "Failed"

    log_activity_safe(
        actor_type="Student",
        actor_identifier=clean_registration_number,
        action=ACTIVITY_ACTIONS.get(
            "registration_created",
            "Registration Created",
        ),
        entity_type="Registration",
        entity_id=str(student["id"]),
    )

    st.session_state["registration_processing"] = False
    st.session_state["registration_success"] = {
        "registration_number": clean_registration_number,
        "application_reference": student.get("application_reference"),
        "email_status": email_status,
    }
    st.rerun()


# ============================================================
# FORGOT PASSWORD
# ============================================================

def render_forgot_password_page() -> None:
    st.title(
        "Reset Student Password"
    )

    if st.session_state.get(
        "password_reset_completed",
        False,
    ):
        st.success(
            "Password reset completed successfully."
        )
        st.info(
            "Use your registration number and new password "
            "to sign in from the home-page login panel."
        )

        if st.button(
            "Continue to Login",
            type="primary",
            use_container_width=True,
            key="password_reset_continue_to_login",
        ):
            reset_password_reset_state()
            navigate_to(
                "landing",
                logout=True,
            )

        return

    if st.session_state[
        "password_reset_stage"
    ] == "request":
        render_password_reset_request()
    else:
        render_password_reset_verification()


def render_password_reset_request() -> None:
    st.info(
        "Enter the registration number and registered email "
        "address. A six-digit OTP will be sent by email."
    )

    with st.form(
        "password_reset_request_form"
    ):
        registration_number = st.text_input(
            "Registration number"
        )

        email = st.text_input(
            "Registered email address"
        )

        submitted = st.form_submit_button(
            "Send Password Reset OTP",
            type="primary",
            use_container_width=True,
        )

    if not submitted:
        return

    clean_registration_number = normalize_registration_number(
        registration_number
    )

    clean_email = email.strip().lower()

    try:
        student = get_student(
            clean_registration_number
        )
    except Exception as error:
        st.error(
            "The password-reset service is unavailable."
        )

        st.code(
            str(error)
        )

        return

    if (
        not student
        or str(
            student.get(
                "email",
                "",
            )
        ).strip().lower()
        != clean_email
    ):
        st.error(
            "The registration number and email address do not match."
        )
        return

    if not student.get(
        "is_active",
        True,
    ):
        st.error(
            "This account is inactive. Contact the administrator."
        )
        return

    if not email_is_configured():
        st.error(
            "Password-reset email is not configured."
        )
        return

    otp = generate_numeric_otp()

    expires_at = (
        datetime.now(
            timezone.utc
        )
        + timedelta(
            minutes=OTP_VALIDITY_MINUTES
        )
    )

    try:
        create_password_reset_otp(
            registration_id=str(
                student["id"]
            ),
            otp_hash=hash_otp(
                otp,
                str(
                    student["id"]
                ),
            ),
            expires_at=(
                expires_at.isoformat()
            ),
            maximum_attempts=(
                OTP_MAXIMUM_ATTEMPTS
            ),
        )

        send_password_reset_otp_email(
            student=student,
            otp=otp,
            validity_minutes=(
                OTP_VALIDITY_MINUTES
            ),
        )

    except Exception as error:
        st.error(
            "The password-reset OTP could not be sent."
        )

        st.code(
            str(error)
        )

        return

    st.session_state[
        "password_reset_stage"
    ] = "verify"

    st.session_state[
        "password_reset_registration_id"
    ] = str(
        student["id"]
    )

    st.session_state[
        "password_reset_email"
    ] = str(
        student["email"]
    )

    st.session_state[
        "password_reset_registration_number"
    ] = str(
        student["registration_number"]
    )

    log_activity_safe(
        actor_type="Student",
        actor_identifier=str(
            student[
                "registration_number"
            ]
        ),
        action=ACTIVITY_ACTIONS[
            "password_reset_requested"
        ],
        entity_type="Registration",
        entity_id=str(
            student["id"]
        ),
    )

    st.rerun()


def render_password_reset_verification() -> None:
    registration_id = st.session_state[
        "password_reset_registration_id"
    ]

    registered_email = st.session_state[
        "password_reset_email"
    ]

    registration_number = st.session_state[
        "password_reset_registration_number"
    ]

    if not registration_id:
        reset_password_reset_state()
        st.rerun()

    st.success(
        "An OTP was sent to "
        f"{mask_email(registered_email)}."
    )

    with st.form(
        "password_reset_verification_form"
    ):
        otp = st.text_input(
            "Six-digit OTP",
            max_chars=6,
        )

        new_password = st.text_input(
            "New password",
            type="password",
        )

        confirm_password = st.text_input(
            "Confirm new password",
            type="password",
        )

        submitted = st.form_submit_button(
            "Reset Password",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        errors = validate_password(
            new_password
        )

        if new_password != confirm_password:
            errors.append(
                "Passwords do not match."
            )

        if not otp.isdigit() or len(
            otp
        ) != 6:
            errors.append(
                "Enter the complete six-digit OTP."
            )

        if errors:
            for error_message in errors:
                st.error(
                    error_message
                )

            return

        try:
            otp_record = get_latest_password_reset_otp(
                registration_id
            )
        except Exception as error:
            st.error(
                "The OTP could not be verified."
            )

            st.code(
                str(error)
            )

            return

        if not otp_record:
            st.error(
                "No active password-reset OTP was found."
            )
            return

        expiry = parse_database_datetime(
            otp_record.get(
                "expires_at"
            )
        )

        if (
            expiry is None
            or expiry
            <= datetime.now(
                timezone.utc
            )
        ):
            mark_otp_used(
                str(
                    otp_record["id"]
                )
            )

            st.error(
                "The OTP has expired. Request a new OTP."
            )
            return

        attempt_count = int(
            otp_record.get(
                "attempt_count",
                0,
            )
        )

        maximum_attempts = int(
            otp_record.get(
                "maximum_attempts",
                OTP_MAXIMUM_ATTEMPTS,
            )
        )

        if attempt_count >= maximum_attempts:
            mark_otp_used(
                str(
                    otp_record["id"]
                )
            )

            st.error(
                "Maximum OTP attempts exceeded. Request a new OTP."
            )
            return

        if not verify_otp(
            otp=otp,
            registration_id=registration_id,
            stored_hash=str(
                otp_record["otp_hash"]
            ),
        ):
            increment_otp_attempt(
                otp_id=str(
                    otp_record["id"]
                ),
                current_attempt_count=(
                    attempt_count
                ),
            )

            st.error(
                "Incorrect OTP."
            )
            return

        try:
            update_registration(
                registration_id,
                {
                    "password_hash": hash_password(
                        new_password
                    ),
                },
            )

            mark_otp_used(
                str(
                    otp_record["id"]
                )
            )

            invalidate_password_reset_otps(
                registration_id
            )

        except Exception as error:
            st.error(
                "The password could not be reset."
            )

            st.code(
                str(error)
            )

            return

        log_activity_safe(
            actor_type="Student",
            actor_identifier=str(
                registration_number
            ),
            action=ACTIVITY_ACTIONS[
                "password_reset_completed"
            ],
            entity_type="Registration",
            entity_id=registration_id,
        )

        st.session_state[
            "password_reset_completed"
        ] = True

        st.session_state[
            "password_reset_stage"
        ] = "complete"

        st.session_state[
            "password_reset_registration_id"
        ] = None

        st.session_state[
            "password_reset_email"
        ] = None

        st.session_state[
            "password_reset_registration_number"
        ] = None

        st.rerun()

    if st.button(
        "Cancel Password Reset",
        use_container_width=True,
    ):
        reset_password_reset_state()
        navigate_to(
            "login"
        )


# ============================================================
# LOGIN PAGE
# ============================================================

def render_login_page() -> None:
    render_landing_page()


# ============================================================
# PUBLIC SUPPORT PAGE
# ============================================================

def render_public_support_page() -> None:
    st.title(
        "Contact 10x Devs Support"
    )

    support_settings = get_setting_safe(
        "support_settings",
        {
            "enabled": True,
        },
    )

    if not support_settings.get(
        "enabled",
        True,
    ):
        st.warning(
            "Support requests are currently disabled."
        )
        return

    with st.form(
        "public_support_form"
    ):
        full_name = st.text_input(
            "Full name"
        )

        email = st.text_input(
            "Email address"
        )

        mobile_number = st.text_input(
            "Mobile number",
            placeholder="+91XXXXXXXXXX",
        )

        subject = st.text_input(
            "Subject"
        )

        message = st.text_area(
            "Describe your issue",
            height=160,
        )

        submitted = st.form_submit_button(
            "Submit Support Request",
            type="primary",
            use_container_width=True,
        )

    if not submitted:
        return

    errors: list[str] = []

    clean_name = normalize_name(
        full_name
    )

    clean_email = email.strip().lower()

    if len(clean_name) < 3:
        errors.append(
            "Enter your complete name."
        )

    if not is_valid_email(
        clean_email
    ):
        errors.append(
            "Enter a valid email address."
        )

    try:
        normalized_mobile = normalize_mobile_number(
            mobile_number,
            DEFAULT_PHONE_REGION,
        )
    except ValueError as error:
        normalized_mobile = ""
        errors.append(
            str(error)
        )

    if len(subject.strip()) < 4:
        errors.append(
            "Enter a clear support subject."
        )

    if len(message.strip()) < 15:
        errors.append(
            "Describe the issue in at least 15 characters."
        )

    if errors:
        for error_message in errors:
            st.error(
                error_message
            )

        return

    try:
        support_request = create_support_request(
            {
                "registration_id": None,
                "full_name": clean_name,
                "email": clean_email,
                "mobile_number": normalized_mobile,
                "subject": subject.strip(),
                "message": message.strip(),
                "request_status": "Open",
            }
        )

        st.success(
            "Your support request was submitted successfully."
        )

        st.write(
            f"**Support request reference:** "
            f"{support_request['id']}"
        )

    except Exception as error:
        st.error(
            "The support request could not be submitted."
        )

        st.code(
            str(error)
        )


# ============================================================
# STUDENT DASHBOARD
# ============================================================

def render_student_dashboard() -> None:
    registration_number = st.session_state[
        "student_registration_number"
    ]

    try:
        student = get_student(
            registration_number
        )
    except Exception as error:
        st.error(
            "The student dashboard could not be loaded."
        )

        st.code(
            str(error)
        )

        return

    if not student:
        logout_everyone()
        navigate_to(
            "login"
        )

    title_column, logout_column = st.columns(
        [
            5,
            1,
        ]
    )

    with title_column:
        st.title(
            f"Welcome, {student['full_name']}"
        )

    with logout_column:
        if st.button(
            "Logout",
            key="student_logout",
            use_container_width=True,
        ):
            logout_everyone()
            navigate_to(
                "login"
            )

    dashboard_card_values = [
        (
            "Academic Year",
            student.get(
                "study_year",
                "Not available",
            ),
        ),
        (
            "Application Status",
            student.get(
                "application_status",
                "Registered",
            ),
        ),
        (
            "Task Deadline",
            student.get(
                "task_deadline",
                "Not available",
            ),
        ),
        (
            "Club",
            student.get(
                "club",
                "Not available",
            ),
        ),
    ]

    dashboard_columns = st.columns(
        4,
        gap="medium",
    )

    for dashboard_column, (card_label, card_value) in zip(
        dashboard_columns,
        dashboard_card_values,
    ):
        with dashboard_column:
            render_html(
                f"""
                <article class="student-summary-card">
                    <div class="student-summary-label">
                        {card_label}
                    </div>
                    <div class="student-summary-value">
                        {card_value}
                    </div>
                </article>
                """
            )

    (
        overview_tab,
        submission_tab,
        profile_tab,
        timeline_tab,
        announcements_tab,
        interview_tab,
        support_tab,
    ) = st.tabs(
        [
            "Overview",
            "Submission",
            "Profile",
            "Timeline",
            "Announcements",
            "Interview & Onboarding",
            "Support",
        ]
    )

    with overview_tab:
        render_student_overview(
            student
        )

    with submission_tab:
        render_student_submission_tab(
            student
        )

    with profile_tab:
        render_student_profile_tab(
            student
        )

    with timeline_tab:
        render_student_timeline_tab(
            student
        )

    with announcements_tab:
        render_student_announcements_tab(
            student
        )

    with interview_tab:
        render_student_interview_onboarding_tab(
            student
        )

    with support_tab:
        render_student_support_tab(
            student
        )


def render_student_overview(
    student: dict[str, Any],
) -> None:
    st.subheader(
        "Application Information"
    )

    information_one, information_two = st.columns(
        2
    )

    with information_one:
        st.write(
            f"**Application reference:** "
            f"{student.get('application_reference', 'Not available')}"
        )

        st.write(
            f"**Candidate number:** "
            f"{student.get('candidate_number', 'Not available')}"
        )

        st.write(
            f"**Registration number:** "
            f"{student.get('registration_number', 'Not available')}"
        )

        st.write(
            f"**Mandatory task:** "
            f"{mandatory_task_for_student(student)}"
        )

    with information_two:
        st.write(
            f"**Email:** "
            f"{student.get('email', 'Not available')}"
        )

        st.write(
            f"**Mobile number:** "
            f"{student.get('mobile_number', 'Not available')}"
        )

        st.write(
            f"**Preferred contact:** "
            f"{student.get('preferred_contact_mode', 'Email')}"
        )

        st.write(
            f"**Submission reopened:** "
            f"{'Yes' if student.get('submission_reopened') else 'No'}"
        )

    task_document = load_task_document(
        str(
            student.get(
                "study_year",
                "",
            )
        )
    )

    if task_document:
        st.download_button(
            "Download Official Task Document",
            data=task_document,
            file_name=TASK_DOCUMENTS[
                student["study_year"]
            ],
            mime=DOCX_MIME_TYPE,
            use_container_width=True,
        )

    if student_deadline_has_passed(
        student
    ):
        st.error(
            "Your task deadline has passed. Final submission is "
            "disabled unless the administrator extends the deadline "
            "or reopens your submission."
        )
    else:
        st.success(
            "Your submission deadline is active."
        )

    if student.get(
        "deadline_extended"
    ):
        st.info(
            "Your deadline was extended. "
            f"Reason: {student.get('deadline_extension_reason', 'Not provided')}"
        )

    st.subheader(
        "Eligible Specific Tasks"
    )

    for task_number, task_name in enumerate(
        allowed_specific_tasks(
            student
        ),
        start=1,
    ):
        st.write(
            f"{task_number}. {task_name}"
        )


def render_student_profile_tab(
    student: dict[str, Any],
) -> None:
    st.subheader(
        "Update Contact Information"
    )

    st.caption(
        "The registration number, academic year and club cannot "
        "be changed through this page."
    )

    with st.form(
        "student_profile_form"
    ):
        full_name = st.text_input(
            "Full name",
            value=str(
                student.get(
                    "full_name",
                    "",
                )
            ),
        )

        email = st.text_input(
            "Email address",
            value=str(
                student.get(
                    "email",
                    "",
                )
            ),
        )

        mobile_number = st.text_input(
            "Mobile number",
            value=str(
                student.get(
                    "mobile_number",
                    "",
                )
            ),
        )

        current_contact_mode = str(
            student.get(
                "preferred_contact_mode",
                "Email",
            )
        )

        contact_mode_index = (
            PREFERRED_CONTACT_MODES.index(
                current_contact_mode
            )
            if current_contact_mode
            in PREFERRED_CONTACT_MODES
            else 0
        )

        preferred_contact_mode = st.selectbox(
            "Preferred contact mode",
            PREFERRED_CONTACT_MODES,
            index=contact_mode_index,
        )

        submitted = st.form_submit_button(
            "Save Profile Changes",
            type="primary",
            use_container_width=True,
        )

    if not submitted:
        return

    clean_name = normalize_name(
        full_name
    )

    clean_email = email.strip().lower()

    errors: list[str] = []

    if len(clean_name) < 3:
        errors.append(
            "Enter your complete name."
        )

    if not is_valid_email(
        clean_email
    ):
        errors.append(
            "Enter a valid email address."
        )

    try:
        normalized_mobile = normalize_mobile_number(
            mobile_number,
            DEFAULT_PHONE_REGION,
        )
    except ValueError as error:
        normalized_mobile = ""
        errors.append(
            str(error)
        )

    if errors:
        for error_message in errors:
            st.error(
                error_message
            )

        return

    duplicate_message = find_duplicate_registration(
        registration_number=str(
            student[
                "registration_number"
            ]
        ),
        email=clean_email,
        mobile_number=normalized_mobile,
        exclude_registration_id=str(
            student["id"]
        ),
    )

    if duplicate_message:
        st.error(
            duplicate_message
        )
        return

    try:
        update_student_profile(
            registration_id=str(
                student["id"]
            ),
            profile_values={
                "full_name": clean_name,
                "email": clean_email,
                "mobile_number": normalized_mobile,
                "preferred_contact_mode": (
                    preferred_contact_mode
                ),
            },
        )

        log_activity_safe(
            actor_type="Student",
            actor_identifier=str(
                student[
                    "registration_number"
                ]
            ),
            action=ACTIVITY_ACTIONS[
                "student_updated"
            ],
            entity_type="Registration",
            entity_id=str(
                student["id"]
            ),
            description=(
                "Student updated contact information."
            ),
        )

        st.success(
            "Profile information updated successfully."
        )

        st.rerun()

    except Exception as error:
        st.error(
            "The profile could not be updated."
        )

        st.code(
            str(error)
        )


def render_student_timeline_tab(
    student: dict[str, Any],
) -> None:
    st.subheader(
        "Application Timeline"
    )

    try:
        timeline_events = get_application_timeline(
            registration_id=str(
                student["id"]
            ),
            student_visible_only=True,
        )
    except Exception as error:
        st.error(
            "The application timeline could not be loaded."
        )

        st.code(
            str(error)
        )

        return

    if not timeline_events:
        st.info(
            "No timeline events are available."
        )
        return

    for event in timeline_events:
        with st.container(
            border=True
        ):
            st.caption(
                format_database_datetime(
                    event.get(
                        "created_at"
                    )
                )
            )

            st.markdown(
                f"### {event.get('title', 'Application Update')}"
            )

            if event.get(
                "description"
            ):
                st.write(
                    str(
                        event[
                            "description"
                        ]
                    )
                )


def render_student_announcements_tab(
    student: dict[str, Any],
) -> None:
    st.subheader(
        "Announcements"
    )

    try:
        announcements = get_published_announcements(
            student
        )
    except Exception as error:
        st.error(
            "Announcements could not be loaded."
        )

        st.code(
            str(error)
        )

        return

    if not announcements:
        st.info(
            "No announcements are currently available."
        )
        return

    for announcement in announcements:
        priority = str(
            announcement.get(
                "priority",
                "Normal",
            )
        )

        with st.container(
            border=True
        ):
            st.caption(
                f"{priority.upper()} • "
                f"{format_database_datetime(announcement.get('published_at') or announcement.get('created_at'))}"
            )

            st.subheader(
                str(
                    announcement.get(
                        "title",
                        "Announcement",
                    )
                )
            )

            st.write(
                str(
                    announcement.get(
                        "body",
                        "",
                    )
                )
            )


def render_student_interview_onboarding_tab(
    student: dict[str, Any],
) -> None:
    st.subheader(
        "Interview"
    )

    try:
        interview = get_interview_schedule(
            str(
                student["id"]
            )
        )
    except Exception:
        interview = None

    if interview:
        interview_one, interview_two = st.columns(
            2
        )

        with interview_one:
            st.write(
                f"**Interview status:** "
                f"{interview.get('interview_status', 'Scheduled')}"
            )

            st.write(
                f"**Date and time:** "
                f"{format_database_datetime(interview.get('scheduled_at'))}"
            )

            st.write(
                f"**Mode:** "
                f"{interview.get('interview_mode', 'Not available')}"
            )

        with interview_two:
            st.write(
                f"**Duration:** "
                f"{interview.get('duration_minutes', 20)} minutes"
            )

            st.write(
                f"**Venue or link:** "
                f"{interview.get('venue_or_link', 'Not available')}"
            )

        if interview.get(
            "instructions"
        ):
            st.info(
                str(
                    interview[
                        "instructions"
                    ]
                )
            )
    else:
        st.info(
            "No interview has been scheduled."
        )

    st.divider()
    st.subheader(
        "Onboarding"
    )

    if student.get(
        "application_status"
    ) != "Selected":
        st.info(
            "Onboarding information becomes available after selection."
        )
        return

    try:
        onboarding = get_onboarding_attendance(
            str(
                student["id"]
            )
        )
    except Exception:
        onboarding = None

    if not onboarding:
        st.info(
            "Onboarding has not yet been initiated."
        )
        return

    current_status = str(
        onboarding.get(
            "attendance_status",
            "Pending",
        )
    )

    st.write(
        f"**Current onboarding status:** "
        f"{current_status}"
    )

    if onboarding.get(
        "notes"
    ):
        st.info(
            str(
                onboarding[
                    "notes"
                ]
            )
        )

    if current_status in {
        "Invited",
        "Pending",
    }:
        confirmation = st.checkbox(
            "I confirm that I will attend the onboarding session."
        )

        if st.button(
            "Confirm Onboarding Attendance",
            type="primary",
            disabled=not confirmation,
            use_container_width=True,
        ):
            try:
                upsert_onboarding_attendance(
                    {
                        "registration_id": str(
                            student["id"]
                        ),
                        "attendance_status": "Confirmed",
                        "student_response_at": utc_now_iso(),
                        "updated_by": str(
                            student[
                                "registration_number"
                            ]
                        ),
                    }
                )

                update_registration(
                    str(
                        student["id"]
                    ),
                    {
                        "onboarding_status": "Confirmed",
                    },
                )

                st.success(
                    "Onboarding attendance confirmed."
                )

                st.rerun()

            except Exception as error:
                st.error(
                    "Attendance confirmation could not be saved."
                )

                st.code(
                    str(error)
                )


def render_student_support_tab(
    student: dict[str, Any],
) -> None:
    st.subheader(
        "Submit a Support Request"
    )

    with st.form(
        "student_support_form"
    ):
        subject = st.text_input(
            "Subject"
        )

        message = st.text_area(
            "Describe the issue",
            height=140,
        )

        submitted = st.form_submit_button(
            "Submit Support Request",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if len(
            subject.strip()
        ) < 4:
            st.error(
                "Enter a clear subject."
            )
        elif len(
            message.strip()
        ) < 15:
            st.error(
                "Describe the issue in at least 15 characters."
            )
        else:
            try:
                create_support_request(
                    {
                        "registration_id": str(
                            student["id"]
                        ),
                        "full_name": str(
                            student[
                                "full_name"
                            ]
                        ),
                        "email": str(
                            student[
                                "email"
                            ]
                        ),
                        "mobile_number": (
                            student.get(
                                "mobile_number"
                            )
                        ),
                        "subject": subject.strip(),
                        "message": message.strip(),
                        "request_status": "Open",
                    }
                )

                st.success(
                    "Support request submitted successfully."
                )

                st.rerun()

            except Exception as error:
                st.error(
                    "The support request could not be submitted."
                )

                st.code(
                    str(error)
                )

    st.divider()
    st.subheader(
        "Previous Support Requests"
    )

    try:
        requests = get_student_support_requests(
            str(
                student["id"]
            )
        )
    except Exception:
        requests = []

    if not requests:
        st.info(
            "No previous support requests are available."
        )
        return

    for request in requests:
        with st.expander(
            (
                f"{request.get('subject', 'Support Request')} "
                f"— {request.get('request_status', 'Open')}"
            )
        ):
            st.caption(
                format_database_datetime(
                    request.get(
                        "created_at"
                    )
                )
            )

            st.write(
                str(
                    request.get(
                        "message",
                        "",
                    )
                )
            )

            if request.get(
                "admin_response"
            ):
                st.markdown(
                    "**Administrator response**"
                )

                st.write(
                    str(
                        request[
                            "admin_response"
                        ]
                    )
                )


# ============================================================
# PART A ENDS HERE
# APPEND PART 4 DIRECTLY BELOW THIS LINE
# ============================================================

# ============================================================
# PART 4 — STUDENT SUBMISSION, ADMIN, EVALUATOR AND ROUTER
# Append this directly below the Part A marker.
# ============================================================

from io import BytesIO
import zipfile

from core.database import (
    create_timeline_event,
    get_deadline_reminder_log,
)
from core.pdf_service import generate_offer_letter_docx


# ============================================================
# SHARED PART 4 HELPERS
# ============================================================

def get_existing_task_evidence_map(
    submission: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    if not submission:
        return {}

    evidence_map: dict[str, dict[str, Any]] = {}

    for record in parse_json_list(
        submission.get(
            "specific_task_evidence",
            [],
        )
    ):
        if not isinstance(record, dict):
            continue

        task_name = str(
            record.get(
                "task_name",
                "",
            )
        ).strip()

        if task_name:
            evidence_map[task_name] = record

    return evidence_map


def render_private_storage_files(
    file_records: list[Any],
    *,
    bucket_name: str,
    key_prefix: str,
) -> None:
    valid_records = [
        record
        for record in file_records
        if isinstance(record, dict)
        and str(record.get("path", "")).strip()
    ]

    if not valid_records:
        st.caption("No stored files are available.")
        return

    for index, record in enumerate(
        valid_records,
        start=1,
    ):
        filename = str(
            record.get(
                "name",
                f"Evidence {index}",
            )
        )

        storage_path = str(
            record["path"]
        )

        try:
            signed_url = create_temporary_file_url(
                bucket_name=bucket_name,
                storage_path=storage_path,
                expiry_seconds=600,
            )

            if signed_url:
                st.link_button(
                    f"Open {filename}",
                    signed_url,
                    key=(
                        f"{key_prefix}_"
                        f"{index}_"
                        f"{safe_widget_key(storage_path)}"
                    ),
                    use_container_width=True,
                )
        except Exception as error:
            st.warning(
                f"{filename} could not be opened."
            )

            with st.expander(
                f"Technical details for {filename}"
            ):
                st.code(str(error))


def upload_student_files(
    *,
    student: dict[str, Any],
    category_path: str,
    uploaded_files: list[Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    stored_records: list[dict[str, Any]] = []
    uploaded_paths: list[str] = []

    unique_stamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%d%H%M%S%f")

    for index, uploaded_file in enumerate(
        uploaded_files,
        start=1,
    ):
        filename = clean_filename(
            uploaded_file.name
        )

        storage_path = (
            f"{student['application_reference']}/"
            f"{category_path}/"
            f"{unique_stamp}_{index}_{filename}"
        )

        content_type = (
            uploaded_file.type
            or mimetypes.guess_type(
                filename
            )[0]
            or "application/octet-stream"
        )

        upload_storage_file(
            bucket_name=PROOF_SUBMISSION_BUCKET,
            storage_path=storage_path,
            file_bytes=uploaded_file.getvalue(),
            content_type=content_type,
            replace_existing=False,
        )

        uploaded_paths.append(
            storage_path
        )

        stored_records.append(
            {
                "name": filename,
                "path": storage_path,
                "content_type": content_type,
                "size": uploaded_file.size,
                "category": category_path,
            }
        )

    return (
        stored_records,
        uploaded_paths,
    )


def delete_uploaded_paths_safely(
    storage_paths: list[str],
) -> None:
    for storage_path in storage_paths:
        try:
            delete_storage_file(
                bucket_name=PROOF_SUBMISSION_BUCKET,
                storage_path=storage_path,
            )
        except Exception:
            pass


def selected_submission_tasks(
    submission: dict[str, Any] | None,
) -> list[str]:
    if not submission:
        return []

    selected_tasks = parse_json_list(
        submission.get(
            "selected_tasks",
            [],
        )
    )

    if not selected_tasks:
        old_selected_task = submission.get(
            "selected_task"
        )

        if value_is_present(
            old_selected_task
        ):
            selected_tasks = [
                str(old_selected_task)
            ]

    return [
        str(task)
        for task in selected_tasks
    ]


def submission_is_editable(
    student: dict[str, Any],
    submission: dict[str, Any] | None,
) -> bool:
    if not submission:
        return True

    state = str(
        submission.get(
            "submission_state",
            "Draft",
        )
    )

    return (
        state in {
            "Draft",
            "Reopened",
        }
        or bool(
            student.get(
                "submission_reopened"
            )
        )
    )


def render_final_submission_summary(
    student: dict[str, Any],
    submission: dict[str, Any],
) -> None:
    st.success(
        "Your final proof submission has been recorded."
    )

    summary_one, summary_two, summary_three = st.columns(
        3
    )

    summary_one.metric(
        "Submission State",
        submission.get(
            "submission_state",
            "Final",
        ),
    )

    summary_two.metric(
        "Evaluation Progress",
        submission.get(
            "evaluation_progress",
            "Not Reviewed",
        ),
    )

    summary_three.metric(
        "Application Status",
        student.get(
            "application_status",
            "Under Scrutiny",
        ),
    )

    st.write(
        f"**Mandatory task:** "
        f"{submission.get('mandatory_task_name', 'Not available')}"
    )

    st.markdown(
        "### Submitted Specific Tasks"
    )

    for index, task_name in enumerate(
        selected_submission_tasks(
            submission
        ),
        start=1,
    ):
        st.write(
            f"{index}. {task_name}"
        )

    st.write(
        f"**Submitted at:** "
        f"{format_database_datetime(submission.get('final_submitted_at') or submission.get('submitted_at'))}"
    )

    if value_is_present(
        submission.get(
            "evaluation_total"
        )
    ):
        st.info(
            f"Evaluation score: "
            f"{submission['evaluation_total']}/100"
        )

    receipt_storage_path = submission.get(
        "receipt_storage_path"
    )

    if receipt_storage_path:
        try:
            receipt_bytes = download_storage_file(
                bucket_name=GENERATED_DOCUMENT_BUCKET,
                storage_path=str(
                    receipt_storage_path
                ),
            )

            st.download_button(
                "Download Submission Receipt",
                data=receipt_bytes,
                file_name=(
                    f"Submission_Receipt_"
                    f"{student['registration_number']}.pdf"
                ),
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception:
            st.warning(
                "The submission receipt is currently unavailable."
            )


# ============================================================
# STUDENT DRAFT AND FINAL SUBMISSION
# ============================================================

def render_student_submission_tab(
    student: dict[str, Any],
) -> None:
    st.subheader(
        "Task Proof Submission"
    )

    if not submission_is_open():
        st.warning(
            "Proof submission is currently disabled by the administrator."
        )
        return

    try:
        submission = get_proof_submission(
            str(
                student["id"]
            )
        )
    except Exception as error:
        st.error(
            "Submission information could not be loaded."
        )
        st.code(
            str(error)
        )
        return

    notice = st.session_state.pop(
        "submission_success_notice",
        None,
    )

    if notice:
        st.success(
            notice
        )

    if (
        submission
        and not submission_is_editable(
            student,
            submission,
        )
    ):
        render_final_submission_summary(
            student,
            submission,
        )
        return

    deadline_settings = get_setting_safe(
        "submission_settings",
        {
            "allow_drafts": True,
            "enforce_deadline": True,
        },
    )

    allow_drafts = bool(
        deadline_settings.get(
            "allow_drafts",
            True,
        )
    )

    enforce_deadline = bool(
        deadline_settings.get(
            "enforce_deadline",
            True,
        )
    )

    deadline_passed = (
        enforce_deadline
        and student_deadline_has_passed(
            student
        )
        and not student.get(
            "submission_reopened"
        )
    )

    if deadline_passed:
        st.error(
            "Your deadline has passed. You may review your draft, "
            "but final submission requires an extension or reopening "
            "from the administrator."
        )

    existing_selected_tasks = selected_submission_tasks(
        submission
    )

    existing_evidence_map = get_existing_task_evidence_map(
        submission
    )

    existing_mandatory_files = parse_json_list(
        submission.get(
            "proof_files",
            [],
        )
        if submission
        else []
    )

    eligible_tasks = allowed_specific_tasks(
        student
    )

    default_selected_tasks = [
        task
        for task in existing_selected_tasks
        if task in eligible_tasks
    ]

    st.markdown(
        "### 1. Mandatory Portfolio"
    )

    st.text_input(
        "Mandatory task",
        value=mandatory_task_for_student(
            student
        ),
        disabled=True,
        key="student_mandatory_task_name",
    )

    default_run_mode = (
        str(
            submission.get(
                "portfolio_run_mode",
                "",
            )
        )
        if submission
        else ""
    )

    run_mode_options = [
        "Localhost",
        "Public Deployment",
    ]

    if student["study_year"] == "3rd Year":
        portfolio_run_mode = "Public Deployment"

        st.info(
            "Third-year students must provide a publicly deployed "
            "full-stack portfolio."
        )
    else:
        portfolio_run_mode = st.selectbox(
            "Portfolio run mode",
            run_mode_options,
            index=(
                run_mode_options.index(
                    default_run_mode
                )
                if default_run_mode
                in run_mode_options
                else 0
            ),
            key="student_portfolio_run_mode",
        )

    portfolio_github_url = st.text_input(
        "Portfolio GitHub or source URL",
        value=(
            str(
                submission.get(
                    "portfolio_github_url",
                    "",
                )
                or ""
            )
            if submission
            else ""
        ),
        key="student_portfolio_github_url",
    )

    portfolio_deployment_url = st.text_input(
        "Portfolio deployment URL",
        value=(
            str(
                submission.get(
                    "portfolio_deployment_url",
                    "",
                )
                or ""
            )
            if submission
            else ""
        ),
        key="student_portfolio_deployment_url",
    )

    if existing_mandatory_files:
        with st.expander(
            "Previously saved mandatory-task files",
            expanded=False,
        ):
            render_private_storage_files(
                existing_mandatory_files,
                bucket_name=PROOF_SUBMISSION_BUCKET,
                key_prefix="student_existing_mandatory",
            )

    mandatory_uploads = st.file_uploader(
        "Add mandatory-task screenshots, ZIP or documents",
        type=ALLOWED_PROOF_EXTENSIONS,
        accept_multiple_files=True,
        key="student_mandatory_uploads_v2",
    ) or []

    st.markdown(
        "### 2. Specific Technical Tasks"
    )

    selected_tasks = st.multiselect(
        "Select every specific task completed",
        eligible_tasks,
        default=default_selected_tasks,
        key="student_selected_tasks_v2",
    )

    current_task_inputs: dict[str, dict[str, Any]] = {}

    for task_index, task_name in enumerate(
        selected_tasks,
        start=1,
    ):
        existing_evidence = existing_evidence_map.get(
            task_name,
            {},
        )

        existing_files = parse_json_list(
            existing_evidence.get(
                "files",
                [],
            )
        )

        with st.expander(
            f"Task {task_index}: {task_name}",
            expanded=True,
        ):
            source_url = st.text_input(
                "Source or GitHub URL",
                value=str(
                    existing_evidence.get(
                        "source_url",
                        "",
                    )
                    or ""
                ),
                key=(
                    f"student_task_source_"
                    f"{safe_widget_key(task_name)}"
                ),
            )

            deployment_url = st.text_input(
                "Deployment URL",
                value=str(
                    existing_evidence.get(
                        "deployment_url",
                        "",
                    )
                    or ""
                ),
                key=(
                    f"student_task_deploy_"
                    f"{safe_widget_key(task_name)}"
                ),
            )

            demo_url = st.text_input(
                "Demo video URL",
                value=str(
                    existing_evidence.get(
                        "demo_url",
                        "",
                    )
                    or ""
                ),
                key=(
                    f"student_task_demo_"
                    f"{safe_widget_key(task_name)}"
                ),
            )

            notes = st.text_area(
                "Task explanation",
                value=str(
                    existing_evidence.get(
                        "notes",
                        "",
                    )
                    or ""
                ),
                key=(
                    f"student_task_notes_"
                    f"{safe_widget_key(task_name)}"
                ),
            )

            if existing_files:
                st.caption(
                    "Previously saved evidence"
                )

                render_private_storage_files(
                    existing_files,
                    bucket_name=PROOF_SUBMISSION_BUCKET,
                    key_prefix=(
                        "student_existing_task_"
                        f"{safe_widget_key(task_name)}"
                    ),
                )

            new_files = st.file_uploader(
                "Add screenshots, ZIP or supporting files",
                type=ALLOWED_PROOF_EXTENSIONS,
                accept_multiple_files=True,
                key=(
                    f"student_task_files_"
                    f"{safe_widget_key(task_name)}"
                ),
            ) or []

            current_task_inputs[
                task_name
            ] = {
                "source_url": source_url.strip(),
                "deployment_url": deployment_url.strip(),
                "demo_url": demo_url.strip(),
                "notes": notes.strip(),
                "existing_files": existing_files,
                "new_files": new_files,
            }

    st.markdown(
        "### 3. Confirmation"
    )

    readme_confirmed = st.checkbox(
        "README or setup instructions are included.",
        value=bool(
            submission.get(
                "readme_confirmed"
            )
            if submission
            else False
        ),
        key="student_readme_confirmed_v2",
    )

    originality_confirmed = st.checkbox(
        "I confirm that all submitted source links and files belong "
        "to projects completed by me or my declared team.",
        key="student_originality_confirmed_v2",
    )

    final_confirmation = st.checkbox(
        "I have reviewed every field and understand that final "
        "submission becomes locked unless reopened by an administrator.",
        key="student_final_confirmation_v2",
    )

    button_one, button_two = st.columns(
        2
    )

    with button_one:
        save_draft_clicked = st.button(
            "Save Draft",
            disabled=not allow_drafts,
            use_container_width=True,
            key="student_save_draft_v2",
        )

    with button_two:
        final_submit_clicked = st.button(
            "Submit Final Proof",
            type="primary",
            disabled=deadline_passed,
            use_container_width=True,
            key="student_final_submit_v2",
        )

    if not (
        save_draft_clicked
        or final_submit_clicked
    ):
        return

    validation_errors: list[str] = []

    if portfolio_github_url and not is_valid_url(
        portfolio_github_url
    ):
        validation_errors.append(
            "Enter a valid portfolio source URL."
        )

    if portfolio_deployment_url and not is_valid_url(
        portfolio_deployment_url
    ):
        validation_errors.append(
            "Enter a valid portfolio deployment URL."
        )

    if final_submit_clicked:
        if not selected_tasks:
            validation_errors.append(
                "Select at least one specific task."
            )

        if student["study_year"] == "3rd Year":
            if not portfolio_github_url:
                validation_errors.append(
                    "The mandatory portfolio GitHub URL is required."
                )

            if not portfolio_deployment_url:
                validation_errors.append(
                    "The mandatory portfolio deployment URL is required."
                )

        if (
            student["study_year"] == "2nd Year"
            and not portfolio_github_url
            and not existing_mandatory_files
            and not mandatory_uploads
        ):
            validation_errors.append(
                "Provide a portfolio source URL or mandatory-task files."
            )

        if (
            portfolio_run_mode
            == "Public Deployment"
            and not portfolio_deployment_url
        ):
            validation_errors.append(
                "Enter the mandatory portfolio deployment URL."
            )

        if not (
            existing_mandatory_files
            or mandatory_uploads
        ):
            validation_errors.append(
                "Upload at least one mandatory-task evidence file."
            )

        for task_name in selected_tasks:
            task_record = current_task_inputs[
                task_name
            ]

            for url_field in [
                "source_url",
                "deployment_url",
                "demo_url",
            ]:
                field_value = task_record[
                    url_field
                ]

                if (
                    field_value
                    and not is_valid_url(
                        field_value
                    )
                ):
                    validation_errors.append(
                        f"Enter a valid {url_field.replace('_', ' ')} "
                        f"for {task_name}."
                    )

            if not (
                task_record["source_url"]
                or task_record["existing_files"]
                or task_record["new_files"]
            ):
                validation_errors.append(
                    f"Provide a source URL or evidence for {task_name}."
                )

            if student["study_year"] == "3rd Year":
                if not task_record["source_url"]:
                    validation_errors.append(
                        f"A source URL is required for {task_name}."
                    )

                if not task_record["demo_url"]:
                    validation_errors.append(
                        f"A demo video URL is required for {task_name}."
                    )

                if not (
                    task_record["existing_files"]
                    or task_record["new_files"]
                ):
                    validation_errors.append(
                        f"Upload evidence for {task_name}."
                    )

        if not readme_confirmed:
            validation_errors.append(
                "Confirm the README or setup instructions."
            )

        if not originality_confirmed:
            validation_errors.append(
                "Confirm project-source ownership."
            )

        if not final_confirmation:
            validation_errors.append(
                "Accept the final-submission confirmation."
            )

    all_new_uploads = list(
        mandatory_uploads
    )

    for task_record in current_task_inputs.values():
        all_new_uploads.extend(
            task_record[
                "new_files"
            ]
        )

    if len(
        all_new_uploads
    ) > MAX_PROOF_FILES:
        validation_errors.append(
            f"Upload no more than {MAX_PROOF_FILES} new files at once."
        )

    total_new_size = sum(
        uploaded_file.size
        for uploaded_file in all_new_uploads
    )

    if total_new_size > MAX_TOTAL_PROOF_SIZE:
        validation_errors.append(
            "The combined new upload size exceeds the allowed limit."
        )

    if validation_errors:
        for error_message in validation_errors:
            st.error(
                error_message
            )

        return

    duplicate_warning = False

    candidate_source_urls = [
        portfolio_github_url,
        *[
            current_task_inputs[
                task_name
            ]["source_url"]
            for task_name in selected_tasks
        ],
    ]

    for candidate_url in candidate_source_urls:
        if not candidate_url:
            continue

        try:
            if source_url_already_exists(
                candidate_url,
                exclude_registration_id=str(
                    student["id"]
                ),
            ):
                duplicate_warning = True
        except Exception:
            pass

    if duplicate_warning:
        st.warning(
            "A submitted source URL also appears in another student "
            "record. The submission will be flagged for evaluator review."
        )

    uploaded_paths: list[str] = []

    try:
        newly_stored_mandatory, mandatory_paths = (
            upload_student_files(
                student=student,
                category_path="mandatory",
                uploaded_files=mandatory_uploads,
            )
        )

        uploaded_paths.extend(
            mandatory_paths
        )

        merged_mandatory_files = [
            *existing_mandatory_files,
            *newly_stored_mandatory,
        ]

        specific_task_evidence: list[
            dict[str, Any]
        ] = []

        for task_index, task_name in enumerate(
            selected_tasks,
            start=1,
        ):
            task_record = current_task_inputs[
                task_name
            ]

            newly_stored_task_files, task_paths = (
                upload_student_files(
                    student=student,
                    category_path=(
                        "specific_tasks/"
                        f"{task_index}_"
                        f"{safe_widget_key(task_name)}"
                    ),
                    uploaded_files=task_record[
                        "new_files"
                    ],
                )
            )

            uploaded_paths.extend(
                task_paths
            )

            specific_task_evidence.append(
                {
                    "task_name": task_name,
                    "source_url": (
                        task_record[
                            "source_url"
                        ]
                        or None
                    ),
                    "deployment_url": (
                        task_record[
                            "deployment_url"
                        ]
                        or None
                    ),
                    "demo_url": (
                        task_record[
                            "demo_url"
                        ]
                        or None
                    ),
                    "notes": (
                        task_record[
                            "notes"
                        ]
                        or None
                    ),
                    "files": [
                        *task_record[
                            "existing_files"
                        ],
                        *newly_stored_task_files,
                    ],
                }
            )

        submission_values = {
            "mandatory_task_name": mandatory_task_for_student(
                student
            ),
            "mandatory_task_confirmed": (
                final_submit_clicked
            ),
            "selected_task": (
                selected_tasks[0]
                if selected_tasks
                else None
            ),
            "selected_tasks": selected_tasks,
            "specific_task_evidence": (
                specific_task_evidence
            ),
            "portfolio_run_mode": (
                portfolio_run_mode
            ),
            "portfolio_github_url": (
                portfolio_github_url
                or None
            ),
            "portfolio_deployment_url": (
                portfolio_deployment_url
                or None
            ),
            "github_url": (
                portfolio_github_url
                or None
            ),
            "deployment_url": (
                portfolio_deployment_url
                or None
            ),
            "readme_confirmed": (
                readme_confirmed
            ),
            "proof_files": (
                merged_mandatory_files
            ),
            "duplicate_source_warning": (
                duplicate_warning
            ),
            "notes": (
                f"Mandatory task plus "
                f"{len(selected_tasks)} specific task(s)."
            ),
        }

        if save_draft_clicked:
            saved_submission = save_submission_draft(
                registration_id=str(
                    student["id"]
                ),
                submission_values=submission_values,
            )

            log_activity_safe(
                actor_type="Student",
                actor_identifier=str(
                    student[
                        "registration_number"
                    ]
                ),
                action=ACTIVITY_ACTIONS[
                    "draft_saved"
                ],
                entity_type="Proof Submission",
                entity_id=str(
                    saved_submission["id"]
                ),
            )

            st.session_state[
                "submission_success_notice"
            ] = (
                "Your draft was saved successfully."
            )

            st.rerun()

        final_submission = finalize_submission(
            registration_id=str(
                student["id"]
            ),
            submission_values=submission_values,
        )

    except Exception as error:
        delete_uploaded_paths_safely(
            uploaded_paths
        )

        st.error(
            "The submission could not be saved."
        )

        st.code(
            str(error)
        )

        return

    receipt_pdf: bytes | None = None
    receipt_filename: str | None = None

    try:
        updated_student = get_registration_by_id(
            str(
                student["id"]
            )
        ) or student

        receipt_pdf, receipt_number = (
            generate_submission_receipt_pdf(
                updated_student,
                final_submission,
            )
        )

        receipt_filename = (
            f"Submission_Receipt_"
            f"{student['registration_number']}.pdf"
        )

        receipt_storage_path = (
            f"receipts/"
            f"{student['application_reference']}/"
            f"{receipt_filename}"
        )

        upload_storage_file(
            bucket_name=GENERATED_DOCUMENT_BUCKET,
            storage_path=receipt_storage_path,
            file_bytes=receipt_pdf,
            content_type="application/pdf",
            replace_existing=True,
        )

        create_generated_document_record(
            {
                "registration_id": str(
                    student["id"]
                ),
                "document_type": (
                    "Submission Receipt"
                ),
                "document_number": (
                    receipt_number
                ),
                "storage_path": (
                    receipt_storage_path
                ),
                "generated_by": (
                    student[
                        "registration_number"
                    ]
                ),
            }
        )

        update_proof_submission(
            str(
                final_submission["id"]
            ),
            {
                "receipt_number": (
                    receipt_number
                ),
                "receipt_storage_path": (
                    receipt_storage_path
                ),
            },
        )

    except Exception:
        receipt_pdf = None
        receipt_filename = None

    email_sent = False

    if email_is_configured():
        try:
            updated_student = get_registration_by_id(
                str(
                    student["id"]
                )
            ) or student

            message_id = (
                send_submission_under_scrutiny_email(
                    student=updated_student,
                    mandatory_task=mandatory_task_for_student(
                        student
                    ),
                    selected_tasks=selected_tasks,
                    receipt_pdf=receipt_pdf,
                    receipt_filename=receipt_filename,
                )
            )

            record_submission_email_result(
                str(
                    student["id"]
                ),
                success=True,
                message_id=message_id,
            )

            email_sent = True

        except Exception as email_error:
            record_submission_email_result(
                str(
                    student["id"]
                ),
                success=False,
                error_message=str(
                    email_error
                ),
            )

    log_activity_safe(
        actor_type="Student",
        actor_identifier=str(
            student[
                "registration_number"
            ]
        ),
        action=ACTIVITY_ACTIONS[
            "proof_finalized"
        ],
        entity_type="Proof Submission",
        entity_id=str(
            final_submission["id"]
        ),
        details={
            "specific_task_count": len(
                selected_tasks
            ),
            "duplicate_source_warning": (
                duplicate_warning
            ),
        },
    )

    st.session_state[
        "submission_success_notice"
    ] = (
        "Final proof submitted successfully. "
        + (
            "A confirmation email was sent."
            if email_sent
            else (
                "The submission was saved, but the "
                "confirmation email could not be sent."
            )
        )
    )

    st.rerun()


# ============================================================
# ADMIN DATAFRAME HELPERS
# ============================================================

SENSITIVE_REGISTRATION_COLUMNS = {
    "id",
    "password_hash",
    "email_error",
    "submission_email_error",
    "status_email_error",
    "offer_email_error",
    "email_message_id",
    "submission_email_message_id",
    "status_email_message_id",
    "offer_email_message_id",
}


def safe_registration_frame(
    registrations: list[dict[str, Any]],
) -> pd.DataFrame:
    frame = pd.DataFrame(
        registrations
    )

    if frame.empty:
        return frame

    visible_columns = [
        column
        for column in frame.columns
        if column
        not in SENSITIVE_REGISTRATION_COLUMNS
    ]

    return frame[
        visible_columns
    ].copy()


def registration_option_map(
    registrations: list[dict[str, Any]],
    *,
    status_filter: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    options: dict[
        str,
        dict[str, Any],
    ] = {}

    for student in registrations:
        if (
            status_filter
            and student.get(
                "application_status"
            )
            not in status_filter
        ):
            continue

        label = (
            f"{student.get('application_reference', 'No Reference')} | "
            f"{student.get('full_name', 'Unknown Student')} | "
            f"{student.get('registration_number', 'No Number')}"
        )

        options[label] = student

    return options


# ============================================================
# ADMIN ANALYTICS
# ============================================================

def render_admin_analytics(
    registrations: list[dict[str, Any]],
    submissions: list[dict[str, Any]],
) -> None:
    registration_frame = pd.DataFrame(
        registrations
    )

    submission_frame = pd.DataFrame(
        submissions
    )

    metric_columns = st.columns(
        6
    )

    metric_columns[0].metric(
        "Registrations",
        len(registrations),
    )

    metric_columns[1].metric(
        "Final Submissions",
        sum(
            1
            for submission in submissions
            if submission.get(
                "submission_state"
            )
            == "Final"
        ),
    )

    metric_columns[2].metric(
        "Drafts",
        sum(
            1
            for submission in submissions
            if submission.get(
                "submission_state"
            )
            == "Draft"
        ),
    )

    metric_columns[3].metric(
        "Under Scrutiny",
        sum(
            1
            for student in registrations
            if student.get(
                "application_status"
            )
            == "Under Scrutiny"
        ),
    )

    metric_columns[4].metric(
        "Shortlisted",
        sum(
            1
            for student in registrations
            if student.get(
                "application_status"
            )
            == "Shortlisted"
        ),
    )

    metric_columns[5].metric(
        "Selected",
        sum(
            1
            for student in registrations
            if student.get(
                "application_status"
            )
            == "Selected"
        ),
    )

    if registration_frame.empty:
        st.info(
            "No registration data is available."
        )
        return

    chart_one, chart_two = st.columns(
        2
    )

    with chart_one:
        st.subheader(
            "Registrations by Club"
        )

        if "club" in registration_frame.columns:
            st.bar_chart(
                registration_frame[
                    "club"
                ].value_counts()
            )

    with chart_two:
        st.subheader(
            "Application Status Distribution"
        )

        if (
            "application_status"
            in registration_frame.columns
        ):
            st.bar_chart(
                registration_frame[
                    "application_status"
                ].value_counts()
            )

    chart_three, chart_four = st.columns(
        2
    )

    with chart_three:
        st.subheader(
            "Registrations by Academic Year"
        )

        if (
            "study_year"
            in registration_frame.columns
        ):
            st.bar_chart(
                registration_frame[
                    "study_year"
                ].value_counts()
            )

    with chart_four:
        st.subheader(
            "Submission States"
        )

        if (
            not submission_frame.empty
            and "submission_state"
            in submission_frame.columns
        ):
            st.bar_chart(
                submission_frame[
                    "submission_state"
                ].value_counts()
            )
        else:
            st.info(
                "No submission-state data is available."
            )


# ============================================================
# ADMIN STUDENT MANAGEMENT
# ============================================================

def render_admin_students(
    registrations: list[dict[str, Any]],
) -> None:
    if not registrations:
        st.info(
            "No student registrations are available."
        )
        return

    st.subheader(
        "Search and Filter Students"
    )

    search_column, club_column, status_column = st.columns(
        3
    )

    with search_column:
        search_text = st.text_input(
            "Search name, registration number, email or reference",
            key="admin_student_search",
        ).strip().lower()

    with club_column:
        club_filter = st.selectbox(
            "Club",
            [
                "All",
                *CLUBS,
            ],
            key="admin_student_club_filter",
        )

    with status_column:
        status_filter = st.selectbox(
            "Status",
            [
                "All",
                *APPLICATION_STATUSES,
            ],
            key="admin_student_status_filter",
        )

    filtered_students = []

    for student in registrations:
        searchable_text = " ".join(
            str(
                student.get(
                    field,
                    "",
                )
            )
            for field in [
                "full_name",
                "registration_number",
                "email",
                "application_reference",
                "candidate_number",
            ]
        ).lower()

        if (
            search_text
            and search_text
            not in searchable_text
        ):
            continue

        if (
            club_filter != "All"
            and student.get(
                "club"
            )
            != club_filter
        ):
            continue

        if (
            status_filter != "All"
            and student.get(
                "application_status"
            )
            != status_filter
        ):
            continue

        filtered_students.append(
            student
        )

    st.dataframe(
        safe_registration_frame(
            filtered_students
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    st.subheader(
        "Edit One Student"
    )

    options = registration_option_map(
        registrations
    )

    selected_label = st.selectbox(
        "Select student",
        list(
            options.keys()
        ),
        key="admin_edit_student_selection",
    )

    student = options[
        selected_label
    ]

    with st.form(
        "admin_edit_student_form"
    ):
        full_name = st.text_input(
            "Full name",
            value=str(
                student.get(
                    "full_name",
                    "",
                )
            ),
        )

        email = st.text_input(
            "Email",
            value=str(
                student.get(
                    "email",
                    "",
                )
            ),
        )

        mobile_number = st.text_input(
            "Mobile number",
            value=str(
                student.get(
                    "mobile_number",
                    "",
                )
            ),
        )

        row_one, row_two = st.columns(
            2
        )

        with row_one:
            study_year = st.selectbox(
                "Academic year",
                YEARS,
                index=(
                    YEARS.index(
                        student.get(
                            "study_year"
                        )
                    )
                    if student.get(
                        "study_year"
                    )
                    in YEARS
                    else 0
                ),
            )

        with row_two:
            club = st.selectbox(
                "Club",
                CLUBS,
                index=(
                    CLUBS.index(
                        student.get(
                            "club"
                        )
                    )
                    if student.get(
                        "club"
                    )
                    in CLUBS
                    else 0
                ),
            )

        row_three, row_four = st.columns(
            2
        )

        with row_three:
            application_status = st.selectbox(
                "Application status",
                APPLICATION_STATUSES,
                index=(
                    APPLICATION_STATUSES.index(
                        student.get(
                            "application_status"
                        )
                    )
                    if student.get(
                        "application_status"
                    )
                    in APPLICATION_STATUSES
                    else 0
                ),
            )

        with row_four:
            preferred_contact_mode = st.selectbox(
                "Preferred contact mode",
                PREFERRED_CONTACT_MODES,
                index=(
                    PREFERRED_CONTACT_MODES.index(
                        student.get(
                            "preferred_contact_mode"
                        )
                    )
                    if student.get(
                        "preferred_contact_mode"
                    )
                    in PREFERRED_CONTACT_MODES
                    else 0
                ),
            )

        current_deadline = (
            date.fromisoformat(
                str(
                    student.get(
                        "task_deadline"
                    )
                )
            )
            if student.get(
                "task_deadline"
            )
            else date.today()
        )

        task_deadline = st.date_input(
            "Task deadline",
            value=current_deadline,
        )

        is_active = st.checkbox(
            "Account is active",
            value=bool(
                student.get(
                    "is_active",
                    True,
                )
            ),
        )

        submitted = st.form_submit_button(
            "Save Student Changes",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        errors: list[str] = []

        clean_name = normalize_name(
            full_name
        )

        clean_email = email.strip().lower()

        if len(clean_name) < 3:
            errors.append(
                "Enter a valid full name."
            )

        if not is_valid_email(
            clean_email
        ):
            errors.append(
                "Enter a valid email address."
            )

        try:
            normalized_mobile = normalize_mobile_number(
                mobile_number,
                DEFAULT_PHONE_REGION,
            )
        except ValueError as error:
            normalized_mobile = ""
            errors.append(
                str(error)
            )

        if errors:
            for error_message in errors:
                st.error(
                    error_message
                )
        else:
            duplicate_message = find_duplicate_registration(
                registration_number=str(
                    student[
                        "registration_number"
                    ]
                ),
                email=clean_email,
                mobile_number=normalized_mobile,
                exclude_registration_id=str(
                    student["id"]
                ),
            )

            if duplicate_message:
                st.error(
                    duplicate_message
                )
            else:
                try:
                    update_registration(
                        str(
                            student["id"]
                        ),
                        {
                            "full_name": (
                                clean_name
                            ),
                            "email": clean_email,
                            "mobile_number": (
                                normalized_mobile
                            ),
                            "study_year": (
                                study_year
                            ),
                            "club": club,
                            "application_status": (
                                application_status
                            ),
                            "preferred_contact_mode": (
                                preferred_contact_mode
                            ),
                            "task_deadline": (
                                task_deadline.isoformat()
                            ),
                            "is_active": (
                                is_active
                            ),
                        },
                    )

                    log_activity_safe(
                        actor_type="Admin",
                        actor_identifier=str(
                            st.secrets[
                                "ADMIN_USERNAME"
                            ]
                        ),
                        action=ACTIVITY_ACTIONS[
                            "student_updated"
                        ],
                        entity_type="Registration",
                        entity_id=str(
                            student["id"]
                        ),
                        description=(
                            "Administrator edited student details."
                        ),
                    )

                    st.success(
                        "Student information updated."
                    )

                    st.rerun()

                except Exception as error:
                    st.error(
                        "Student information could not be updated."
                    )

                    st.code(
                        str(error)
                    )

    st.divider()
    st.subheader(
        "Deadline Extension and Submission Reopening"
    )

    extension_reason = st.text_area(
        "Extension or reopening reason",
        key="admin_extension_reason",
    )

    new_deadline = st.date_input(
        "New deadline",
        value=max(
            date.today(),
            current_deadline,
        ),
        key="admin_new_deadline",
    )

    action_one, action_two = st.columns(
        2
    )

    with action_one:
        if st.button(
            "Extend Student Deadline",
            type="primary",
            use_container_width=True,
            key="admin_extend_deadline",
        ):
            if len(
                extension_reason.strip()
            ) < 5:
                st.error(
                    "Provide a clear extension reason."
                )
            else:
                try:
                    extend_student_deadline(
                        registration_id=str(
                            student["id"]
                        ),
                        new_deadline=(
                            new_deadline
                        ),
                        reason=(
                            extension_reason.strip()
                        ),
                        extended_by=str(
                            st.secrets[
                                "ADMIN_USERNAME"
                            ]
                        ),
                    )

                    st.success(
                        "Deadline extended."
                    )

                    st.rerun()

                except Exception as error:
                    st.error(
                        "The deadline could not be extended."
                    )
                    st.code(
                        str(error)
                    )

    with action_two:
        if st.button(
            "Reopen Student Submission",
            use_container_width=True,
            key="admin_reopen_submission",
        ):
            if len(
                extension_reason.strip()
            ) < 5:
                st.error(
                    "Provide a clear reopening reason."
                )
            else:
                try:
                    reopened_submission = reopen_submission(
                        registration_id=str(
                            student["id"]
                        ),
                        reason=(
                            extension_reason.strip()
                        ),
                        reopened_by=str(
                            st.secrets[
                                "ADMIN_USERNAME"
                            ]
                        ),
                    )

                    log_activity_safe(
                        actor_type="Admin",
                        actor_identifier=str(
                            st.secrets[
                                "ADMIN_USERNAME"
                            ]
                        ),
                        action=ACTIVITY_ACTIONS[
                            "submission_reopened"
                        ],
                        entity_type="Proof Submission",
                        entity_id=str(
                            reopened_submission["id"]
                        ),
                    )

                    st.success(
                        "Submission reopened."
                    )

                    st.rerun()

                except Exception as error:
                    st.error(
                        "The submission could not be reopened."
                    )
                    st.code(
                        str(error)
                    )

    st.divider()
    st.subheader(
        "Bulk Status Update"
    )

    bulk_options = registration_option_map(
        registrations
    )

    selected_labels = st.multiselect(
        "Select students",
        list(
            bulk_options.keys()
        ),
        key="admin_bulk_status_students",
    )

    new_bulk_status = st.selectbox(
        "New status",
        APPLICATION_STATUSES,
        key="admin_bulk_status_value",
    )

    send_bulk_email = st.checkbox(
        "Send the updated status by email",
        key="admin_bulk_status_email",
    )

    if st.button(
        "Apply Bulk Status Update",
        type="primary",
        disabled=not selected_labels,
        use_container_width=True,
        key="admin_apply_bulk_status",
    ):
        selected_students = [
            bulk_options[
                label
            ]
            for label in selected_labels
        ]

        try:
            bulk_update_registration_status(
                [
                    str(
                        selected_student[
                            "id"
                        ]
                    )
                    for selected_student
                    in selected_students
                ],
                new_bulk_status,
            )

            sent_count = 0

            if (
                send_bulk_email
                and email_is_configured()
            ):
                for selected_student in selected_students:
                    selected_student = dict(
                        selected_student
                    )

                    selected_student[
                        "application_status"
                    ] = new_bulk_status

                    try:
                        message_id = send_status_email(
                            selected_student
                        )

                        record_status_email_result(
                            selected_student,
                            success=True,
                            message_id=message_id,
                        )

                        sent_count += 1

                    except Exception as email_error:
                        record_status_email_result(
                            selected_student,
                            success=False,
                            error_message=str(
                                email_error
                            ),
                        )

            st.success(
                f"Updated {len(selected_students)} students. "
                f"Status emails sent: {sent_count}."
            )

            st.rerun()

        except Exception as error:
            st.error(
                "Bulk status update failed."
            )
            st.code(
                str(error)
            )


# ============================================================
# SUBMISSION REVIEW WORKSPACE
# ============================================================

def render_submission_review_workspace(
    registrations: list[dict[str, Any]],
    submissions: list[dict[str, Any]],
    *,
    actor_type: str,
    actor_identifier: str,
    evaluator: dict[str, Any] | None = None,
) -> None:
    if not submissions:
        st.info(
            "No proof submissions are available."
        )
        return

    student_by_id = {
        str(
            student["id"]
        ): student
        for student in registrations
    }

    visible_submissions: list[
        dict[str, Any]
    ] = []

    assigned_clubs = set(
        evaluator.get(
            "assigned_clubs",
            [],
        )
        if evaluator
        else CLUBS
    )

    for submission in submissions:
        student = student_by_id.get(
            str(
                submission.get(
                    "registration_id"
                )
            )
        )

        if not student:
            continue

        if (
            evaluator
            and assigned_clubs
            and student.get(
                "club"
            )
            not in assigned_clubs
        ):
            continue

        visible_submissions.append(
            submission
        )

    if not visible_submissions:
        st.info(
            "No submissions are available for the assigned clubs."
        )
        return

    option_map: dict[
        str,
        tuple[
            dict[str, Any],
            dict[str, Any],
        ],
    ] = {}

    for submission in visible_submissions:
        student = student_by_id[
            str(
                submission[
                    "registration_id"
                ]
            )
        ]

        label = (
            f"{student['application_reference']} | "
            f"{student['full_name']} | "
            f"{submission.get('submission_state', 'Draft')}"
        )

        option_map[
            label
        ] = (
            student,
            submission,
        )

    selected_label = st.selectbox(
        "Select submission",
        list(
            option_map.keys()
        ),
        key=(
            f"{actor_type.lower()}_"
            "submission_review_selection"
        ),
    )

    student, submission = option_map[
        selected_label
    ]

    metric_one, metric_two, metric_three, metric_four = st.columns(
        4
    )

    metric_one.metric(
        "Student",
        student["full_name"],
    )

    metric_two.metric(
        "Club",
        student["club"],
    )

    metric_three.metric(
        "Submission State",
        submission.get(
            "submission_state",
            "Draft",
        ),
    )

    metric_four.metric(
        "Evaluation Progress",
        submission.get(
            "evaluation_progress",
            "Not Reviewed",
        ),
    )

    st.write(
        f"**Registration number:** "
        f"{student['registration_number']}"
    )

    st.write(
        f"**Application status:** "
        f"{student['application_status']}"
    )

    if submission.get(
        "duplicate_source_warning"
    ):
        st.error(
            "Duplicate source-link warning: one or more submitted "
            "source URLs also appear in another student record."
        )

    st.markdown(
        "### Mandatory Portfolio"
    )

    link_columns = st.columns(
        2
    )

    with link_columns[0]:
        if submission.get(
            "portfolio_github_url"
        ):
            st.link_button(
                "Open Portfolio Source",
                str(
                    submission[
                        "portfolio_github_url"
                    ]
                ),
                use_container_width=True,
            )

    with link_columns[1]:
        if submission.get(
            "portfolio_deployment_url"
        ):
            st.link_button(
                "Open Portfolio Deployment",
                str(
                    submission[
                        "portfolio_deployment_url"
                    ]
                ),
                use_container_width=True,
            )

    render_private_storage_files(
        parse_json_list(
            submission.get(
                "proof_files",
                [],
            )
        ),
        bucket_name=PROOF_SUBMISSION_BUCKET,
        key_prefix=(
            f"{actor_type}_review_mandatory"
        ),
    )

    st.markdown(
        "### Specific Tasks"
    )

    for task_index, evidence in enumerate(
        parse_json_list(
            submission.get(
                "specific_task_evidence",
                [],
            )
        ),
        start=1,
    ):
        if not isinstance(
            evidence,
            dict,
        ):
            continue

        task_name = str(
            evidence.get(
                "task_name",
                f"Task {task_index}",
            )
        )

        with st.expander(
            f"Task {task_index}: {task_name}",
            expanded=True,
        ):
            task_links = st.columns(
                3
            )

            with task_links[0]:
                if evidence.get(
                    "source_url"
                ):
                    st.link_button(
                        "Source",
                        str(
                            evidence[
                                "source_url"
                            ]
                        ),
                        use_container_width=True,
                    )

            with task_links[1]:
                if evidence.get(
                    "deployment_url"
                ):
                    st.link_button(
                        "Deployment",
                        str(
                            evidence[
                                "deployment_url"
                            ]
                        ),
                        use_container_width=True,
                    )

            with task_links[2]:
                if evidence.get(
                    "demo_url"
                ):
                    st.link_button(
                        "Demo",
                        str(
                            evidence[
                                "demo_url"
                            ]
                        ),
                        use_container_width=True,
                    )

            if evidence.get(
                "notes"
            ):
                st.write(
                    str(
                        evidence[
                            "notes"
                        ]
                    )
                )

            render_private_storage_files(
                parse_json_list(
                    evidence.get(
                        "files",
                        [],
                    )
                ),
                bucket_name=PROOF_SUBMISSION_BUCKET,
                key_prefix=(
                    f"{actor_type}_review_"
                    f"{safe_widget_key(task_name)}"
                ),
            )

    st.divider()
    st.subheader(
        "Evaluation"
    )

    criteria = EVALUATION_CRITERIA.get(
        student["study_year"],
        {},
    )

    existing_scores = parse_json_dict(
        submission.get(
            "evaluation_scores",
            {},
        )
    )

    permissions = (
        parse_json_dict(
            evaluator.get(
                "permissions",
                {},
            )
        )
        if evaluator
        else {
            "change_application_status": True,
        }
    )

    evaluator_options = get_all_evaluators()

    with st.form(
        f"{actor_type}_evaluation_form_"
        f"{submission['id']}"
    ):
        score_values: dict[
            str,
            float,
        ] = {}

        for criterion_name, maximum_score in criteria.items():
            score_values[
                criterion_name
            ] = st.number_input(
                f"{criterion_name} (0–{maximum_score})",
                min_value=0.0,
                max_value=float(
                    maximum_score
                ),
                value=min(
                    float(
                        existing_scores.get(
                            criterion_name,
                            0,
                        )
                    ),
                    float(
                        maximum_score
                    ),
                ),
                step=1.0,
                key=(
                    f"{actor_type}_score_"
                    f"{submission['id']}_"
                    f"{safe_widget_key(criterion_name)}"
                ),
            )

        progress = st.selectbox(
            "Evaluation progress",
            EVALUATION_PROGRESS_OPTIONS,
            index=(
                EVALUATION_PROGRESS_OPTIONS.index(
                    submission.get(
                        "evaluation_progress"
                    )
                )
                if submission.get(
                    "evaluation_progress"
                )
                in EVALUATION_PROGRESS_OPTIONS
                else 0
            ),
        )

        evaluation_notes = st.text_area(
            "Student-visible evaluation notes",
            value=str(
                submission.get(
                    "evaluation_notes",
                    "",
                )
                or ""
            ),
        )

        private_notes = st.text_area(
            "Private evaluator/admin notes",
            value=str(
                submission.get(
                    "admin_private_notes",
                    "",
                )
                or ""
            ),
        )

        assigned_evaluator_id = submission.get(
            "evaluator_id"
        )

        if actor_type == "Admin":
            evaluator_labels = [
                "Unassigned",
                *[
                    (
                        f"{record['full_name']} "
                        f"({record['username']})"
                    )
                    for record in evaluator_options
                ],
            ]

            evaluator_id_map = {
                (
                    f"{record['full_name']} "
                    f"({record['username']})"
                ): str(
                    record["id"]
                )
                for record in evaluator_options
            }

            current_label = "Unassigned"

            for label, evaluator_id in evaluator_id_map.items():
                if str(
                    assigned_evaluator_id
                ) == evaluator_id:
                    current_label = label
                    break

            assigned_evaluator_label = st.selectbox(
                "Assigned evaluator",
                evaluator_labels,
                index=evaluator_labels.index(
                    current_label
                ),
            )
        else:
            assigned_evaluator_label = None

        if permissions.get(
            "change_application_status",
            False,
        ):
            new_application_status = st.selectbox(
                "Application status",
                APPLICATION_STATUSES,
                index=(
                    APPLICATION_STATUSES.index(
                        student.get(
                            "application_status"
                        )
                    )
                    if student.get(
                        "application_status"
                    )
                    in APPLICATION_STATUSES
                    else 0
                ),
            )
        else:
            new_application_status = (
                student.get(
                    "application_status"
                )
            )

        total_score = sum(
            score_values.values()
        )

        st.metric(
            "Calculated Total",
            f"{total_score:.0f}/100",
        )

        saved = st.form_submit_button(
            "Save Evaluation",
            type="primary",
            use_container_width=True,
        )

    if saved:
        update_values = {
            "evaluation_scores": (
                score_values
            ),
            "evaluation_total": (
                total_score
            ),
            "evaluation_notes": (
                evaluation_notes.strip()
                or None
            ),
            "admin_private_notes": (
                private_notes.strip()
                or None
            ),
            "evaluation_progress": (
                progress
            ),
            "evaluated_at": (
                utc_now_iso()
                if progress
                == "Completed"
                else submission.get(
                    "evaluated_at"
                )
            ),
        }

        if actor_type == "Admin":
            update_values[
                "evaluator_id"
            ] = (
                evaluator_id_map.get(
                    assigned_evaluator_label
                )
                if assigned_evaluator_label
                != "Unassigned"
                else None
            )
        elif evaluator:
            update_values[
                "evaluator_id"
            ] = str(
                evaluator["id"]
            )

        try:
            update_proof_submission(
                str(
                    submission["id"]
                ),
                update_values,
            )

            if (
                new_application_status
                != student.get(
                    "application_status"
                )
            ):
                update_registration(
                    str(
                        student["id"]
                    ),
                    {
                        "application_status": (
                            new_application_status
                        ),
                    },
                )

            log_activity_safe(
                actor_type=actor_type,
                actor_identifier=actor_identifier,
                action=ACTIVITY_ACTIONS[
                    "evaluation_saved"
                ],
                entity_type="Proof Submission",
                entity_id=str(
                    submission["id"]
                ),
                details={
                    "evaluation_total": (
                        total_score
                    ),
                    "evaluation_progress": (
                        progress
                    ),
                },
            )

            st.success(
                "Evaluation saved successfully."
            )

            st.rerun()

        except Exception as error:
            st.error(
                "The evaluation could not be saved."
            )
            st.code(
                str(error)
            )


# ============================================================
# ADMIN COMMUNICATIONS
# ============================================================

def render_admin_status_communications(
    registrations: list[dict[str, Any]],
) -> None:
    if not registrations:
        st.info(
            "No registrations are available."
        )
        return

    options = registration_option_map(
        registrations
    )

    selected_label = st.selectbox(
        "Student",
        list(
            options.keys()
        ),
        key="admin_status_email_student",
    )

    student = options[
        selected_label
    ]

    st.write(
        f"**Current status:** "
        f"{student['application_status']}"
    )

    st.write(
        f"**Email:** "
        f"{student['email']}"
    )

    if st.button(
        "Send Current Status Email",
        type="primary",
        use_container_width=True,
        key="admin_send_current_status",
    ):
        try:
            message_id = send_status_email(
                student
            )

            record_status_email_result(
                student,
                success=True,
                message_id=message_id,
            )

            st.success(
                "Status email sent."
            )
        except Exception as error:
            record_status_email_result(
                student,
                success=False,
                error_message=str(
                    error
                ),
            )

            st.error(
                str(error)
            )

    st.divider()
    st.subheader(
        "Retry Registration Email"
    )

    task_document = load_task_document(
        str(
            student["study_year"]
        )
    )

    if st.button(
        "Retry Registration Email",
        disabled=task_document is None,
        use_container_width=True,
        key="admin_retry_registration_email_v2",
    ):
        try:
            message_id = send_registration_email(
                student,
                task_document,
            )

            record_registration_email_result(
                str(
                    student["id"]
                ),
                success=True,
                message_id=message_id,
            )

            st.success(
                "Registration email sent."
            )
        except Exception as error:
            record_registration_email_result(
                str(
                    student["id"]
                ),
                success=False,
                error_message=str(
                    error
                ),
            )

            st.error(
                str(error)
            )


def render_admin_announcements(
    registrations: list[dict[str, Any]],
) -> None:
    st.subheader(
        "Create Announcement"
    )

    with st.form(
        "admin_create_announcement_form"
    ):
        title = st.text_input(
            "Title"
        )

        body = st.text_area(
            "Announcement message",
            height=150,
        )

        priority = st.selectbox(
            "Priority",
            ANNOUNCEMENT_PRIORITIES,
        )

        audience = st.selectbox(
            "Target audience",
            ANNOUNCEMENT_AUDIENCES,
        )

        target_year = st.selectbox(
            "Target year",
            [
                "Not Applicable",
                *YEARS,
            ],
        )

        target_club = st.selectbox(
            "Target club",
            [
                "Not Applicable",
                *CLUBS,
            ],
        )

        publish_now = st.checkbox(
            "Publish immediately",
            value=True,
        )

        send_email_now = st.checkbox(
            "Email this announcement to matching students",
        )

        expires_at = st.date_input(
            "Expiry date",
            value=date.today()
            + timedelta(
                days=30
            ),
        )

        submitted = st.form_submit_button(
            "Create Announcement",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        errors: list[str] = []

        if len(
            title.strip()
        ) < 4:
            errors.append(
                "Enter a clear announcement title."
            )

        if len(
            body.strip()
        ) < 10:
            errors.append(
                "Enter an announcement message."
            )

        if (
            audience
            in {
                "Year",
                "Year and Club",
            }
            and target_year
            == "Not Applicable"
        ):
            errors.append(
                "Select a target year."
            )

        if (
            audience
            in {
                "Club",
                "Year and Club",
            }
            and target_club
            == "Not Applicable"
        ):
            errors.append(
                "Select a target club."
            )

        if errors:
            for error_message in errors:
                st.error(
                    error_message
                )
        else:
            try:
                announcement = create_announcement(
                    {
                        "title": (
                            title.strip()
                        ),
                        "body": (
                            body.strip()
                        ),
                        "priority": (
                            priority
                        ),
                        "target_audience": (
                            audience
                        ),
                        "target_year": (
                            None
                            if target_year
                            == "Not Applicable"
                            else target_year
                        ),
                        "target_club": (
                            None
                            if target_club
                            == "Not Applicable"
                            else target_club
                        ),
                        "is_published": (
                            publish_now
                        ),
                        "send_email": (
                            send_email_now
                        ),
                        "published_at": (
                            utc_now_iso()
                            if publish_now
                            else None
                        ),
                        "expires_at": (
                            datetime.combine(
                                expires_at,
                                datetime.max.time(),
                                tzinfo=timezone.utc,
                            ).isoformat()
                        ),
                        "created_by": str(
                            st.secrets[
                                "ADMIN_USERNAME"
                            ]
                        ),
                    }
                )

                sent_count = 0
                failed_count = 0

                if (
                    send_email_now
                    and email_is_configured()
                ):
                    recipients = get_announcement_recipients(
                        announcement
                    )

                    for student in recipients:
                        try:
                            message_id = send_announcement_email(
                                student,
                                announcement,
                            )

                            record_announcement_email(
                                announcement_id=str(
                                    announcement[
                                        "id"
                                    ]
                                ),
                                registration_id=str(
                                    student["id"]
                                ),
                                delivery_status="Sent",
                                message_id=message_id,
                            )

                            sent_count += 1
                        except Exception as email_error:
                            record_announcement_email(
                                announcement_id=str(
                                    announcement[
                                        "id"
                                    ]
                                ),
                                registration_id=str(
                                    student["id"]
                                ),
                                delivery_status="Failed",
                                error_message=str(
                                    email_error
                                ),
                            )

                            failed_count += 1

                log_activity_safe(
                    actor_type="Admin",
                    actor_identifier=str(
                        st.secrets[
                            "ADMIN_USERNAME"
                        ]
                    ),
                    action=ACTIVITY_ACTIONS[
                        "announcement_created"
                    ],
                    entity_type="Announcement",
                    entity_id=str(
                        announcement["id"]
                    ),
                )

                st.success(
                    f"Announcement created. "
                    f"Emails sent: {sent_count}; "
                    f"failed: {failed_count}."
                )

                st.rerun()

            except Exception as error:
                st.error(
                    "The announcement could not be created."
                )
                st.code(
                    str(error)
                )

    st.divider()
    st.subheader(
        "Manage Existing Announcements"
    )

    announcements = get_all_announcements()

    if not announcements:
        st.info(
            "No announcements are available."
        )
        return

    announcement_map = {
        (
            f"{record['title']} | "
            f"{record['priority']} | "
            f"{'Published' if record['is_published'] else 'Draft'}"
        ): record
        for record in announcements
    }

    selected_label = st.selectbox(
        "Select announcement",
        list(
            announcement_map.keys()
        ),
        key="admin_manage_announcement_selection",
    )

    announcement = announcement_map[
        selected_label
    ]

    st.write(
        str(
            announcement["body"]
        )
    )

    action_one, action_two = st.columns(
        2
    )

    with action_one:
        if st.button(
            (
                "Unpublish Announcement"
                if announcement[
                    "is_published"
                ]
                else "Publish Announcement"
            ),
            type="primary",
            use_container_width=True,
            key="admin_toggle_announcement",
        ):
            update_announcement(
                str(
                    announcement["id"]
                ),
                {
                    "is_published": (
                        not announcement[
                            "is_published"
                        ]
                    ),
                    "published_at": (
                        None
                        if announcement[
                            "is_published"
                        ]
                        else utc_now_iso()
                    ),
                },
            )

            st.rerun()

    with action_two:
        delete_confirmed = st.checkbox(
            "Confirm announcement deletion",
            key="admin_delete_announcement_confirm",
        )

        if st.button(
            "Delete Announcement",
            disabled=not delete_confirmed,
            use_container_width=True,
            key="admin_delete_announcement",
        ):
            delete_announcement(
                str(
                    announcement["id"]
                )
            )

            st.rerun()


def render_admin_deadline_reminders(
    registrations: list[dict[str, Any]],
    submissions: list[dict[str, Any]],
) -> None:
    st.subheader(
        "Send Due Deadline Reminders"
    )

    final_registration_ids = {
        str(
            submission[
                "registration_id"
            ]
        )
        for submission in submissions
        if submission.get(
            "submission_state"
        )
        == "Final"
    }

    due_students: list[
        tuple[
            dict[str, Any],
            str,
        ]
    ] = []

    for student in registrations:
        if str(
            student["id"]
        ) in final_registration_ids:
            continue

        try:
            deadline_date = date.fromisoformat(
                str(
                    student[
                        "task_deadline"
                    ]
                )
            )
        except Exception:
            continue

        day_difference = (
            deadline_date
            - date.today()
        ).days

        reminder_type = None

        if day_difference == 3:
            reminder_type = "Three Days"
        elif day_difference == 1:
            reminder_type = "One Day"
        elif day_difference == 0:
            reminder_type = "Deadline Day"
        elif day_difference < 0:
            reminder_type = "Overdue"

        if reminder_type:
            due_students.append(
                (
                    student,
                    reminder_type,
                )
            )

    st.write(
        f"**Due reminder records:** "
        f"{len(due_students)}"
    )

    if not due_students:
        st.info(
            "No reminders are due today."
        )
        return

    reminder_frame = pd.DataFrame(
        [
            {
                "Student": student[
                    "full_name"
                ],
                "Registration Number": student[
                    "registration_number"
                ],
                "Email": student[
                    "email"
                ],
                "Deadline": student[
                    "task_deadline"
                ],
                "Reminder Type": reminder_type,
            }
            for student, reminder_type
            in due_students
        ]
    )

    st.dataframe(
        reminder_frame,
        use_container_width=True,
        hide_index=True,
    )

    resend_existing = st.checkbox(
        "Resend reminders that were already logged",
        key="admin_resend_deadline_reminders",
    )

    if st.button(
        "Send Due Reminders",
        type="primary",
        use_container_width=True,
        key="admin_send_due_reminders",
    ):
        sent_count = 0
        skipped_count = 0
        failed_count = 0

        for student, reminder_type in due_students:
            deadline_date = str(
                student[
                    "task_deadline"
                ]
            )

            existing_log = get_deadline_reminder_log(
                registration_id=str(
                    student["id"]
                ),
                deadline_date=deadline_date,
                reminder_type=reminder_type,
            )

            if (
                existing_log
                and existing_log.get(
                    "delivery_status"
                )
                == "Sent"
                and not resend_existing
            ):
                skipped_count += 1
                continue

            try:
                message_id = send_deadline_reminder_email(
                    student,
                    reminder_type,
                )

                record_deadline_reminder(
                    registration_id=str(
                        student["id"]
                    ),
                    deadline_date=deadline_date,
                    reminder_type=reminder_type,
                    delivery_status="Sent",
                    message_id=message_id,
                )

                sent_count += 1

            except Exception as error:
                record_deadline_reminder(
                    registration_id=str(
                        student["id"]
                    ),
                    deadline_date=deadline_date,
                    reminder_type=reminder_type,
                    delivery_status="Failed",
                    error_message=str(
                        error
                    ),
                )

                failed_count += 1

        st.success(
            f"Sent: {sent_count}; "
            f"skipped: {skipped_count}; "
            f"failed: {failed_count}."
        )


def send_and_store_offer_letter(
    student: dict[str, Any],
    template_bytes: bytes,
    *,
    allow_resend: bool = False,
) -> dict[str, Any]:
    """
    Generate, store and email one offer letter.

    The registration row is checked again immediately before sending.
    This prevents a slow Gmail response or repeated button clicks from
    sending the same offer letter more than once.
    """

    registration_id = str(
        student["id"]
    )

    fresh_student = (
        get_registration_by_id(
            registration_id
        )
        or student
    )

    current_email_status = str(
        fresh_student.get(
            "offer_email_status",
            "",
        )
        or ""
    ).strip()

    if (
        current_email_status == "Sent"
        and not allow_resend
    ):
        raise ValueError(
            "Offer letter already sent to this student. "
            "Enable the resend option only when another copy is required."
        )

    if (
        current_email_status == "Sending"
        and not allow_resend
    ):
        raise ValueError(
            "An offer letter is already being processed for this student. "
            "Wait for the current send operation to finish."
        )

    # Reserve the send operation before contacting Gmail. This protects
    # against repeated clicks and another administrator session sending
    # the same offer letter at the same time.
    update_registration(
        registration_id,
        {
            "offer_email_status": "Sending",
            "offer_email_error": None,
        },
    )

    try:
        result = send_offer_letter_email(
            fresh_student,
            template_bytes,
        )

        storage_path = (
            f"offer_letters/"
            f"{fresh_student['application_reference']}/"
            f"{result['filename']}"
        )

        upload_storage_file(
            bucket_name=GENERATED_DOCUMENT_BUCKET,
            storage_path=storage_path,
            file_bytes=result[
                "document_bytes"
            ],
            content_type=DOCX_MIME_TYPE,
            replace_existing=True,
        )

        create_generated_document_record(
            {
                "registration_id": registration_id,
                "document_type": "Offer Letter",
                "document_number": result[
                    "document_number"
                ],
                "storage_path": storage_path,
                "generated_by": str(
                    st.secrets[
                        "ADMIN_USERNAME"
                    ]
                ),
                "emailed": True,
                "emailed_at": utc_now_iso(),
            }
        )

        record_offer_email_result(
            fresh_student,
            success=True,
            message_id=result[
                "message_id"
            ],
        )

        return result

    except Exception as error:
        record_offer_email_result(
            fresh_student,
            success=False,
            error_message=str(
                error
            ),
        )
        raise


def render_admin_offer_letters(
    registrations: list[dict[str, Any]],
) -> None:
    selected_students = [
        student
        for student in registrations
        if student.get(
            "application_status"
        )
        == "Selected"
    ]

    if not selected_students:
        st.info(
            "No students currently have Selected status."
        )
        return

    template_bytes = load_offer_letter_template()

    if template_bytes is None:
        st.error(
            "The official offer-letter template is unavailable. "
            "Upload it in the Documents tab."
        )
        return

    options = registration_option_map(
        selected_students
    )

    selected_label = st.selectbox(
        "Selected student",
        list(
            options.keys()
        ),
        key="admin_offer_student",
    )

    student = options[
        selected_label
    ]

    # Reload the selected student so that the displayed email status is
    # always current after a previous send operation.
    student = (
        get_registration_by_id(
            str(
                student["id"]
            )
        )
        or student
    )

    details_one, details_two = st.columns(
        2
    )

    with details_one:
        st.write(
            f"**Student:** {student['full_name']}"
        )
        st.write(
            f"**Registration number:** "
            f"{student['registration_number']}"
        )
        st.write(
            f"**Club:** {student['club']}"
        )

    with details_two:
        offer_status = str(
            student.get(
                "offer_email_status",
                "Not Sent",
            )
            or "Not Sent"
        )

        st.write(
            f"**Offer-email status:** {offer_status}"
        )

        if student.get(
            "offer_email_sent_at"
        ):
            st.write(
                "**Last sent:** "
                + format_database_datetime(
                    student.get(
                        "offer_email_sent_at"
                    )
                )
            )

    already_sent = (
        offer_status == "Sent"
    )

    currently_sending = (
        offer_status == "Sending"
    )

    if already_sent:
        st.success(
            "Offer letter already sent to this student."
        )
    elif currently_sending:
        st.warning(
            "This offer letter is currently being processed. "
            "Do not click send again."
        )

    preview_bytes, preview_filename, preview_number = (
        generate_offer_letter_docx(
            student=student,
            template_bytes=template_bytes,
        )
    )

    st.download_button(
        "Preview Personalized Offer Letter",
        data=preview_bytes,
        file_name=preview_filename,
        mime=DOCX_MIME_TYPE,
        use_container_width=True,
    )

    resend_single = False

    if already_sent:
        resend_single = st.checkbox(
            "Resend this offer letter",
            value=False,
            help=(
                "Leave this unchecked for normal use. Enable it only "
                "when the student specifically needs another copy."
            ),
            key="admin_offer_resend_single",
        )

    confirmation = st.checkbox(
        "I confirm that this selected student should receive "
        "the official offer letter.",
        key="admin_offer_confirm_single",
    )

    if already_sent and not resend_single:
        single_button_label = (
            "Offer Letter Already Sent"
        )
    elif already_sent and resend_single:
        single_button_label = (
            "Resend Personalized Offer Letter"
        )
    elif currently_sending:
        single_button_label = (
            "Offer Letter Is Being Sent"
        )
    else:
        single_button_label = (
            "Send Personalized Offer Letter"
        )

    single_send_disabled = (
        not confirmation
        or currently_sending
        or (
            already_sent
            and not resend_single
        )
    )

    if st.button(
        single_button_label,
        type="primary",
        disabled=single_send_disabled,
        use_container_width=True,
        key="admin_send_offer_single",
    ):
        try:
            with st.spinner(
                "Generating, storing and emailing the offer letter. "
                "Please wait and do not click again..."
            ):
                result = send_and_store_offer_letter(
                    student,
                    template_bytes,
                    allow_resend=resend_single,
                )

            log_activity_safe(
                actor_type="Admin",
                actor_identifier=str(
                    st.secrets[
                        "ADMIN_USERNAME"
                    ]
                ),
                action=ACTIVITY_ACTIONS[
                    "offer_letter_sent"
                ],
                entity_type="Registration",
                entity_id=str(
                    student["id"]
                ),
                details={
                    "document_number": result[
                        "document_number"
                    ],
                    "resend": resend_single,
                },
            )

            st.success(
                "Offer letter generated, stored and emailed successfully."
            )

            st.rerun()

        except Exception as error:
            st.error(
                str(error)
            )

    st.divider()
    st.subheader(
        "Bulk Offer Letters"
    )

    sent_students = [
        item
        for item in selected_students
        if item.get(
            "offer_email_status"
        )
        == "Sent"
    ]

    pending_students = [
        item
        for item in selected_students
        if item.get(
            "offer_email_status"
        )
        not in {
            "Sent",
            "Sending",
        }
    ]

    sending_students = [
        item
        for item in selected_students
        if item.get(
            "offer_email_status"
        )
        == "Sending"
    ]

    bulk_summary_one, bulk_summary_two, bulk_summary_three = st.columns(
        3
    )

    bulk_summary_one.metric(
        "Ready to Send",
        len(
            pending_students
        ),
    )

    bulk_summary_two.metric(
        "Already Sent",
        len(
            sent_students
        ),
    )

    bulk_summary_three.metric(
        "Currently Processing",
        len(
            sending_students
        ),
    )

    resend_sent_students = st.checkbox(
        "Resend offer letters to students already marked Sent",
        value=False,
        help=(
            "Keep this unchecked to guarantee that each selected student "
            "receives only one offer letter."
        ),
        key="admin_offer_include_sent",
    )

    recipients = list(
        pending_students
    )

    if resend_sent_students:
        recipients.extend(
            sent_students
        )

    st.write(
        f"**Recipients in this operation:** {len(recipients)}"
    )

    if sent_students and not resend_sent_students:
        st.info(
            f"{len(sent_students)} student(s) are already marked Sent "
            "and will be skipped automatically."
        )

    bulk_confirmation = st.text_input(
        "Type SEND OFFER LETTERS",
        key="admin_offer_bulk_text",
    )

    if st.button(
        "Send All Listed Offer Letters",
        type="primary",
        disabled=(
            bulk_confirmation
            != "SEND OFFER LETTERS"
            or not recipients
        ),
        use_container_width=True,
        key="admin_send_offer_bulk",
    ):
        sent_count = 0
        skipped_count = 0
        failed_count = 0

        progress = st.progress(
            0
        )

        status_message = st.empty()

        for index, recipient in enumerate(
            recipients,
            start=1,
        ):
            status_message.info(
                f"Processing {index} of {len(recipients)}: "
                f"{recipient['registration_number']}"
            )

            try:
                send_and_store_offer_letter(
                    recipient,
                    template_bytes,
                    allow_resend=(
                        resend_sent_students
                        and recipient.get(
                            "offer_email_status"
                        )
                        == "Sent"
                    ),
                )

                sent_count += 1

            except ValueError as error:
                if (
                    "already sent"
                    in str(error).lower()
                    or "already being processed"
                    in str(error).lower()
                ):
                    skipped_count += 1
                else:
                    failed_count += 1

            except Exception:
                failed_count += 1

            progress.progress(
                index
                / len(
                    recipients
                )
            )

        status_message.empty()

        st.success(
            f"Offer letters sent: {sent_count}; "
            f"already sent or processing: {skipped_count}; "
            f"failed: {failed_count}."
        )

        st.rerun()

def render_admin_communications(
    registrations: list[dict[str, Any]],
    submissions: list[dict[str, Any]],
) -> None:
    (
        status_tab,
        announcement_tab,
        reminder_tab,
        offer_tab,
    ) = st.tabs(
        [
            "Status & Registration Emails",
            "Announcements",
            "Deadline Reminders",
            "Offer Letters",
        ]
    )

    with status_tab:
        render_admin_status_communications(
            registrations
        )

    with announcement_tab:
        render_admin_announcements(
            registrations
        )

    with reminder_tab:
        render_admin_deadline_reminders(
            registrations,
            submissions,
        )

    with offer_tab:
        render_admin_offer_letters(
            registrations
        )


# ============================================================
# ADMIN PROJECT SHOWCASE MANAGEMENT
# ============================================================

def render_admin_projects() -> None:
    st.subheader(
        "Presentation Project Catalogue"
    )

    st.info(
        "The completed projects extracted from the two 10x Devs "
        "presentations are already visible on the public showcase. "
        "Importing them into Supabase allows administrators to edit "
        "links, contributors, images and descriptions from this tab."
    )

    try:
        existing_database_projects = get_all_club_projects()
    except Exception:
        existing_database_projects = []

    existing_identities = {
        (
            f"{project.get('club', '')}|"
            f"{project.get('title', '')}"
        ).strip().casefold()
        for project in existing_database_projects
    }

    missing_presentation_projects = [
        project
        for project in DEFAULT_CLUB_PROJECTS
        if (
            f"{project.get('club', '')}|"
            f"{project.get('title', '')}"
        ).strip().casefold()
        not in existing_identities
    ]

    st.write(
        f"**Presentation projects:** {len(DEFAULT_CLUB_PROJECTS)}  "
        f"• **Not yet imported:** {len(missing_presentation_projects)}"
    )

    import_confirmation = st.checkbox(
        "Import the missing presentation projects into Supabase",
        key="admin_import_presentation_projects_confirm",
    )

    if st.button(
        "Import Missing Presentation Projects",
        type="primary",
        disabled=(
            not import_confirmation
            or not missing_presentation_projects
        ),
        use_container_width=True,
        key="admin_import_presentation_projects",
    ):
        imported_count = 0
        failed_count = 0

        for seed_project in missing_presentation_projects:
            try:
                create_club_project(
                    {
                        "club": seed_project["club"],
                        "title": seed_project["title"],
                        "short_description": (
                            seed_project["short_description"]
                        ),
                        "detailed_description": (
                            seed_project.get(
                                "detailed_description"
                            )
                        ),
                        "technologies": (
                            seed_project.get(
                                "technologies",
                                [],
                            )
                        ),
                        "student_names": [],
                        "academic_year": (
                            seed_project.get(
                                "academic_year"
                            )
                        ),
                        "github_url": (
                            seed_project.get(
                                "github_url"
                            )
                        ),
                        "live_url": (
                            seed_project.get(
                                "live_url"
                            )
                        ),
                        "demo_url": (
                            seed_project.get(
                                "demo_url"
                            )
                        ),
                        "thumbnail_storage_path": None,
                        "project_status": "Published",
                        "featured": bool(
                            seed_project.get(
                                "featured"
                            )
                        ),
                        "display_order": int(
                            seed_project.get(
                                "display_order",
                                0,
                            )
                        ),
                        "created_by": str(
                            st.secrets[
                                "ADMIN_USERNAME"
                            ]
                        ),
                    }
                )

                imported_count += 1
            except Exception:
                failed_count += 1

        st.success(
            f"Imported: {imported_count}; failed: {failed_count}."
        )

        st.rerun()

    st.divider()

    st.subheader(
        "Add Club Project"
    )

    with st.form(
        "admin_create_project_form"
    ):
        club = st.selectbox(
            "Club",
            CLUBS,
        )

        title = st.text_input(
            "Project title"
        )

        short_description = st.text_area(
            "Short description",
            height=100,
        )

        detailed_description = st.text_area(
            "Detailed description",
            height=150,
        )

        technologies_text = st.text_input(
            "Technologies separated by commas"
        )

        student_names_text = st.text_input(
            "Contributor names separated by commas",
            help=(
                "Contributor names are shown only for non-featured "
                "projects. Featured projects never display names."
            ),
        )

        academic_year = st.text_input(
            "Academic year or batch"
        )

        github_url = st.text_input(
            "GitHub URL"
        )

        live_url = st.text_input(
            "Live URL"
        )

        demo_url = st.text_input(
            "Demo URL"
        )

        project_status = st.selectbox(
            "Project status",
            PROJECT_STATUSES,
            index=1,
        )

        featured = st.checkbox(
            "Feature this project on the home page"
        )

        display_order = st.number_input(
            "Display order",
            min_value=0,
            value=0,
            step=1,
        )

        thumbnail = st.file_uploader(
            "Project thumbnail",
            type=ALLOWED_PROJECT_IMAGE_EXTENSIONS,
        )

        submitted = st.form_submit_button(
            "Create Project",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        errors: list[str] = []

        if len(
            title.strip()
        ) < 4:
            errors.append(
                "Enter a project title."
            )

        if len(
            short_description.strip()
        ) < 10:
            errors.append(
                "Enter a useful short description."
            )

        for label, value in {
            "GitHub URL": github_url,
            "Live URL": live_url,
            "Demo URL": demo_url,
        }.items():
            if (
                value.strip()
                and not is_valid_url(
                    value
                )
            ):
                errors.append(
                    f"Enter a valid {label}."
                )

        if (
            thumbnail
            and thumbnail.size
            > MAX_PROJECT_IMAGE_SIZE
        ):
            errors.append(
                "The project thumbnail is too large."
            )

        if errors:
            for error_message in errors:
                st.error(
                    error_message
                )
        else:
            thumbnail_path = None

            try:
                if thumbnail:
                    thumbnail_filename = clean_filename(
                        thumbnail.name
                    )

                    thumbnail_path = (
                        f"{safe_widget_key(club)}/"
                        f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}_"
                        f"{thumbnail_filename}"
                    )

                    upload_storage_file(
                        bucket_name=CLUB_PROJECT_MEDIA_BUCKET,
                        storage_path=thumbnail_path,
                        file_bytes=thumbnail.getvalue(),
                        content_type=(
                            thumbnail.type
                            or "image/jpeg"
                        ),
                        replace_existing=False,
                    )

                project = create_club_project(
                    {
                        "club": club,
                        "title": title.strip(),
                        "short_description": (
                            short_description.strip()
                        ),
                        "detailed_description": (
                            detailed_description.strip()
                            or None
                        ),
                        "technologies": [
                            item.strip()
                            for item in technologies_text.split(
                                ","
                            )
                            if item.strip()
                        ],
                        "student_names": (
                            []
                            if featured
                            else [
                                item.strip()
                                for item in student_names_text.split(
                                    ","
                                )
                                if item.strip()
                            ]
                        ),
                        "academic_year": (
                            academic_year.strip()
                            or None
                        ),
                        "github_url": (
                            github_url.strip()
                            or None
                        ),
                        "live_url": (
                            live_url.strip()
                            or None
                        ),
                        "demo_url": (
                            demo_url.strip()
                            or None
                        ),
                        "thumbnail_storage_path": (
                            thumbnail_path
                        ),
                        "project_status": (
                            project_status
                        ),
                        "featured": (
                            featured
                        ),
                        "display_order": int(
                            display_order
                        ),
                        "created_by": str(
                            st.secrets[
                                "ADMIN_USERNAME"
                            ]
                        ),
                    }
                )

                log_activity_safe(
                    actor_type="Admin",
                    actor_identifier=str(
                        st.secrets[
                            "ADMIN_USERNAME"
                        ]
                    ),
                    action=ACTIVITY_ACTIONS[
                        "project_created"
                    ],
                    entity_type="Club Project",
                    entity_id=str(
                        project["id"]
                    ),
                )

                st.success(
                    "Club project created."
                )

                st.rerun()

            except Exception as error:
                if thumbnail_path:
                    try:
                        delete_storage_file(
                            bucket_name=CLUB_PROJECT_MEDIA_BUCKET,
                            storage_path=thumbnail_path,
                        )
                    except Exception:
                        pass

                st.error(
                    "The club project could not be created."
                )

                st.code(
                    str(error)
                )

    st.divider()
    st.subheader(
        "Manage Existing Projects"
    )

    projects = get_all_club_projects()

    if not projects:
        st.info(
            "No projects are available."
        )
        return

    project_map = {
        (
            f"{project['title']} | "
            f"{project['club']} | "
            f"{project['project_status']}"
        ): project
        for project in projects
    }

    selected_label = st.selectbox(
        "Select project",
        list(
            project_map.keys()
        ),
        key="admin_manage_project_selection",
    )

    project = project_map[
        selected_label
    ]

    with st.form(
        "admin_edit_project_form"
    ):
        edit_title = st.text_input(
            "Project title",
            value=str(
                project["title"]
            ),
        )

        edit_short_description = st.text_area(
            "Short description",
            value=str(
                project[
                    "short_description"
                ]
            ),
        )

        edit_detailed_description = st.text_area(
            "Detailed description",
            value=str(
                project.get(
                    "detailed_description",
                    "",
                )
                or ""
            ),
        )

        edit_status = st.selectbox(
            "Status",
            PROJECT_STATUSES,
            index=PROJECT_STATUSES.index(
                project[
                    "project_status"
                ]
            ),
        )

        edit_featured = st.checkbox(
            "Featured",
            value=bool(
                project.get(
                    "featured"
                )
            ),
        )

        edit_order = st.number_input(
            "Display order",
            min_value=0,
            value=int(
                project.get(
                    "display_order",
                    0,
                )
            ),
            step=1,
        )

        saved = st.form_submit_button(
            "Save Project Changes",
            type="primary",
            use_container_width=True,
        )

    if saved:
        update_club_project(
            str(
                project["id"]
            ),
            {
                "title": edit_title.strip(),
                "short_description": (
                    edit_short_description.strip()
                ),
                "detailed_description": (
                    edit_detailed_description.strip()
                    or None
                ),
                "project_status": (
                    edit_status
                ),
                "featured": (
                    edit_featured
                ),
                "display_order": int(
                    edit_order
                ),
            },
        )

        st.success(
            "Project updated."
        )

        st.rerun()

    delete_confirmed = st.checkbox(
        "Confirm permanent project deletion",
        key="admin_delete_project_confirm",
    )

    if st.button(
        "Delete Project",
        disabled=not delete_confirmed,
        use_container_width=True,
        key="admin_delete_project",
    ):
        delete_club_project(
            str(
                project["id"]
            )
        )

        st.rerun()


# ============================================================
# INTERVIEW AND ONBOARDING MANAGEMENT
# ============================================================

def render_admin_interviews_onboarding(
    registrations: list[dict[str, Any]],
) -> None:
    interview_tab, onboarding_tab = st.tabs(
        [
            "Interview Scheduling",
            "Onboarding Attendance",
        ]
    )

    with interview_tab:
        eligible_students = [
            student
            for student in registrations
            if student.get(
                "application_status"
            )
            in {
                "Shortlisted",
                "Selected",
            }
        ]

        if not eligible_students:
            st.info(
                "No shortlisted or selected students are available."
            )
        else:
            options = registration_option_map(
                eligible_students
            )

            selected_label = st.selectbox(
                "Student",
                list(
                    options.keys()
                ),
                key="admin_interview_student",
            )

            student = options[
                selected_label
            ]

            existing_interview = get_interview_schedule(
                str(
                    student["id"]
                )
            )

            existing_datetime = (
                parse_database_datetime(
                    existing_interview.get(
                        "scheduled_at"
                    )
                )
                if existing_interview
                else None
            )

            selected_date = st.date_input(
                "Interview date",
                value=(
                    existing_datetime.date()
                    if existing_datetime
                    else date.today()
                    + timedelta(
                        days=1
                    )
                ),
            )

            selected_time = st.time_input(
                "Interview time",
                value=(
                    existing_datetime.time()
                    if existing_datetime
                    else datetime.now().time().replace(
                        second=0,
                        microsecond=0,
                    )
                ),
            )

            duration = st.number_input(
                "Duration in minutes",
                min_value=5,
                max_value=240,
                value=int(
                    existing_interview.get(
                        "duration_minutes",
                        20,
                    )
                    if existing_interview
                    else 20
                ),
                step=5,
            )

            mode = st.selectbox(
                "Mode",
                INTERVIEW_MODES,
                index=(
                    INTERVIEW_MODES.index(
                        existing_interview.get(
                            "interview_mode"
                        )
                    )
                    if (
                        existing_interview
                        and existing_interview.get(
                            "interview_mode"
                        )
                        in INTERVIEW_MODES
                    )
                    else 0
                ),
            )

            venue_or_link = st.text_input(
                "Venue or meeting link",
                value=str(
                    existing_interview.get(
                        "venue_or_link",
                        "",
                    )
                    or ""
                    if existing_interview
                    else ""
                ),
            )

            instructions = st.text_area(
                "Interview instructions",
                value=str(
                    existing_interview.get(
                        "instructions",
                        "",
                    )
                    or ""
                    if existing_interview
                    else ""
                ),
            )

            status = st.selectbox(
                "Interview status",
                INTERVIEW_SCHEDULE_STATUSES,
                index=(
                    INTERVIEW_SCHEDULE_STATUSES.index(
                        existing_interview.get(
                            "interview_status"
                        )
                    )
                    if (
                        existing_interview
                        and existing_interview.get(
                            "interview_status"
                        )
                        in INTERVIEW_SCHEDULE_STATUSES
                    )
                    else 0
                ),
            )

            send_email = st.checkbox(
                "Send interview schedule by email",
                value=True,
            )

            if st.button(
                "Save Interview Schedule",
                type="primary",
                use_container_width=True,
                key="admin_save_interview",
            ):
                scheduled_at = datetime.combine(
                    selected_date,
                    selected_time,
                    tzinfo=timezone.utc,
                ).isoformat()

                interview_record = upsert_interview_schedule(
                    {
                        "registration_id": str(
                            student["id"]
                        ),
                        "scheduled_at": scheduled_at,
                        "duration_minutes": int(
                            duration
                        ),
                        "interview_mode": (
                            mode
                        ),
                        "venue_or_link": (
                            venue_or_link.strip()
                            or None
                        ),
                        "instructions": (
                            instructions.strip()
                            or None
                        ),
                        "interview_status": (
                            status
                        ),
                        "scheduled_by": str(
                            st.secrets[
                                "ADMIN_USERNAME"
                            ]
                        ),
                    }
                )

                update_registration(
                    str(
                        student["id"]
                    ),
                    {
                        "interview_status": (
                            status
                        ),
                    },
                )

                if (
                    send_email
                    and email_is_configured()
                ):
                    try:
                        message_id = (
                            send_interview_schedule_email(
                                student,
                                interview_record,
                            )
                        )

                        upsert_interview_schedule(
                            {
                                **interview_record,
                                "email_status": (
                                    "Sent"
                                ),
                                "email_message_id": (
                                    message_id
                                ),
                                "email_error": None,
                                "email_sent_at": (
                                    utc_now_iso()
                                ),
                            }
                        )
                    except Exception as email_error:
                        upsert_interview_schedule(
                            {
                                **interview_record,
                                "email_status": (
                                    "Failed"
                                ),
                                "email_error": str(
                                    email_error
                                ),
                            }
                        )

                create_timeline_event(
                    registration_id=str(
                        student["id"]
                    ),
                    event_type="Interview",
                    title="Interview scheduled",
                    description=(
                        f"Interview scheduled for "
                        f"{format_database_datetime(scheduled_at)}."
                    ),
                    visible_to_student=True,
                    created_by=str(
                        st.secrets[
                            "ADMIN_USERNAME"
                        ]
                    ),
                )

                st.success(
                    "Interview schedule saved."
                )

                st.rerun()

        schedules = get_all_interview_schedules()

        if schedules:
            st.subheader(
                "All Interview Schedules"
            )

            st.dataframe(
                pd.DataFrame(
                    schedules
                ),
                use_container_width=True,
                hide_index=True,
            )

    with onboarding_tab:
        selected_students = [
            student
            for student in registrations
            if student.get(
                "application_status"
            )
            == "Selected"
        ]

        if not selected_students:
            st.info(
                "No selected students are available."
            )
            return

        options = registration_option_map(
            selected_students
        )

        selected_label = st.selectbox(
            "Selected student",
            list(
                options.keys()
            ),
            key="admin_onboarding_student",
        )

        student = options[
            selected_label
        ]

        existing_record = get_onboarding_attendance(
            str(
                student["id"]
            )
        )

        status_options = ATTENDANCE_STATUSES

        attendance_status = st.selectbox(
            "Attendance status",
            status_options,
            index=(
                status_options.index(
                    existing_record.get(
                        "attendance_status"
                    )
                )
                if (
                    existing_record
                    and existing_record.get(
                        "attendance_status"
                    )
                    in status_options
                )
                else 0
            ),
        )

        notes = st.text_area(
            "Onboarding instructions or notes",
            value=str(
                existing_record.get(
                    "notes",
                    "",
                )
                or ""
                if existing_record
                else ""
            ),
        )

        send_email = st.checkbox(
            "Send onboarding email",
            value=True,
            key="admin_onboarding_email",
        )

        if st.button(
            "Save Onboarding Update",
            type="primary",
            use_container_width=True,
            key="admin_save_onboarding",
        ):
            onboarding_record = upsert_onboarding_attendance(
                {
                    "registration_id": str(
                        student["id"]
                    ),
                    "attendance_status": (
                        attendance_status
                    ),
                    "invitation_sent_at": (
                        utc_now_iso()
                        if attendance_status
                        == "Invited"
                        else (
                            existing_record.get(
                                "invitation_sent_at"
                            )
                            if existing_record
                            else None
                        )
                    ),
                    "checked_in_at": (
                        utc_now_iso()
                        if attendance_status
                        == "Attended"
                        else None
                    ),
                    "notes": (
                        notes.strip()
                        or None
                    ),
                    "updated_by": str(
                        st.secrets[
                            "ADMIN_USERNAME"
                        ]
                    ),
                }
            )

            update_registration(
                str(
                    student["id"]
                ),
                {
                    "onboarding_status": (
                        {
                            "Pending": (
                                "Not Started"
                            ),
                            "Invited": (
                                "Invited"
                            ),
                            "Confirmed": (
                                "Confirmed"
                            ),
                            "Attended": (
                                "Completed"
                            ),
                            "Absent": (
                                "Absent"
                            ),
                        }[
                            attendance_status
                        ]
                    ),
                },
            )

            if (
                send_email
                and email_is_configured()
            ):
                try:
                    send_onboarding_email(
                        student,
                        notes.strip()
                        or (
                            "Please log in to the portal "
                            "to review and confirm your "
                            "onboarding attendance."
                        ),
                    )
                except Exception as error:
                    st.warning(
                        f"Update saved, but email failed: {error}"
                    )

            st.success(
                "Onboarding update saved."
            )

            st.rerun()


# ============================================================
# EVALUATOR MANAGEMENT
# ============================================================

def render_admin_evaluators() -> None:
    st.subheader(
        "Create Evaluator Account"
    )

    with st.form(
        "admin_create_evaluator_form"
    ):
        full_name = st.text_input(
            "Evaluator full name"
        )

        username = st.text_input(
            "Evaluator username"
        )

        email = st.text_input(
            "Evaluator email"
        )

        password = st.text_input(
            "Temporary password",
            type="password",
        )

        assigned_clubs = st.multiselect(
            "Assigned clubs",
            CLUBS,
            default=CLUBS,
        )

        change_status = st.checkbox(
            "May change application status"
        )

        send_emails = st.checkbox(
            "May send emails"
        )

        manage_students = st.checkbox(
            "May manage student records"
        )

        submitted = st.form_submit_button(
            "Create Evaluator",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        errors = validate_password(
            password
        )

        if len(
            full_name.strip()
        ) < 3:
            errors.append(
                "Enter the evaluator's full name."
            )

        if len(
            username.strip()
        ) < 4:
            errors.append(
                "Enter a username containing at least four characters."
            )

        if not is_valid_email(
            email.strip()
        ):
            errors.append(
                "Enter a valid evaluator email address."
            )

        if not assigned_clubs:
            errors.append(
                "Assign at least one club."
            )

        if errors:
            for error_message in errors:
                st.error(
                    error_message
                )
        else:
            try:
                create_evaluator_account(
                    {
                        "full_name": (
                            normalize_name(
                                full_name
                            )
                        ),
                        "username": (
                            username.strip().lower()
                        ),
                        "email": (
                            email.strip().lower()
                        ),
                        "password_hash": (
                            hash_password(
                                password
                            )
                        ),
                        "assigned_clubs": (
                            assigned_clubs
                        ),
                        "permissions": {
                            **DEFAULT_EVALUATOR_PERMISSIONS,
                            "change_application_status": (
                                change_status
                            ),
                            "send_emails": (
                                send_emails
                            ),
                            "manage_students": (
                                manage_students
                            ),
                        },
                        "created_by": str(
                            st.secrets[
                                "ADMIN_USERNAME"
                            ]
                        ),
                    }
                )

                st.success(
                    "Evaluator account created."
                )

                st.rerun()

            except Exception as error:
                st.error(
                    "The evaluator account could not be created."
                )

                st.code(
                    str(error)
                )

    st.divider()
    st.subheader(
        "Manage Evaluators"
    )

    evaluators = get_all_evaluators()

    if not evaluators:
        st.info(
            "No evaluator accounts are available."
        )
        return

    safe_evaluator_frame = pd.DataFrame(
        [
            {
                key: value
                for key, value in evaluator.items()
                if key
                != "password_hash"
            }
            for evaluator in evaluators
        ]
    )

    st.dataframe(
        safe_evaluator_frame,
        use_container_width=True,
        hide_index=True,
    )

    evaluator_map = {
        (
            f"{evaluator['full_name']} | "
            f"{evaluator['username']}"
        ): evaluator
        for evaluator in evaluators
    }

    selected_label = st.selectbox(
        "Select evaluator",
        list(
            evaluator_map.keys()
        ),
        key="admin_manage_evaluator_selection",
    )

    evaluator = evaluator_map[
        selected_label
    ]

    active = st.checkbox(
        "Evaluator account is active",
        value=bool(
            evaluator.get(
                "is_active",
                True,
            )
        ),
        key="admin_evaluator_active",
    )

    assigned_clubs = st.multiselect(
        "Assigned clubs",
        CLUBS,
        default=[
            club
            for club in evaluator.get(
                "assigned_clubs",
                [],
            )
            if club in CLUBS
        ],
        key="admin_evaluator_clubs",
    )

    new_password = st.text_input(
        "New password (leave blank to keep current password)",
        type="password",
        key="admin_evaluator_new_password",
    )

    if st.button(
        "Save Evaluator Changes",
        type="primary",
        use_container_width=True,
        key="admin_save_evaluator",
    ):
        values: dict[
            str,
            Any,
        ] = {
            "is_active": active,
            "assigned_clubs": (
                assigned_clubs
            ),
        }

        if new_password:
            password_errors = validate_password(
                new_password
            )

            if password_errors:
                for error_message in password_errors:
                    st.error(
                        error_message
                    )
                return

            values[
                "password_hash"
            ] = hash_password(
                new_password
            )

        update_evaluator_account(
            str(
                evaluator["id"]
            ),
            values,
        )

        st.success(
            "Evaluator account updated."
        )

        st.rerun()

    delete_confirmation = st.text_input(
        "Type the evaluator username to delete the account",
        key="admin_delete_evaluator_text",
    )

    if st.button(
        "Delete Evaluator",
        disabled=(
            delete_confirmation
            != evaluator["username"]
        ),
        use_container_width=True,
        key="admin_delete_evaluator",
    ):
        delete_evaluator_account(
            str(
                evaluator["id"]
            )
        )

        st.rerun()


# ============================================================
# SUPPORT MANAGEMENT
# ============================================================

def render_admin_support() -> None:
    requests = get_all_support_requests()

    if not requests:
        st.info(
            "No support requests are available."
        )
        return

    request_frame = pd.DataFrame(
        requests
    )

    visible_columns = [
        column
        for column in [
            "full_name",
            "email",
            "subject",
            "request_status",
            "assigned_to",
            "created_at",
        ]
        if column
        in request_frame.columns
    ]

    st.dataframe(
        request_frame[
            visible_columns
        ],
        use_container_width=True,
        hide_index=True,
    )

    request_map = {
        (
            f"{request['subject']} | "
            f"{request['full_name']} | "
            f"{request['request_status']}"
        ): request
        for request in requests
    }

    selected_label = st.selectbox(
        "Select support request",
        list(
            request_map.keys()
        ),
        key="admin_support_selection",
    )

    request = request_map[
        selected_label
    ]

    st.write(
        f"**Student message:** "
        f"{request['message']}"
    )

    status = st.selectbox(
        "Request status",
        SUPPORT_REQUEST_STATUSES,
        index=SUPPORT_REQUEST_STATUSES.index(
            request[
                "request_status"
            ]
        ),
    )

    assigned_to = st.text_input(
        "Assigned to",
        value=str(
            request.get(
                "assigned_to",
                "",
            )
            or ""
        ),
    )

    admin_response = st.text_area(
        "Administrator response",
        value=str(
            request.get(
                "admin_response",
                "",
            )
            or ""
        ),
        height=150,
    )

    send_response = st.checkbox(
        "Send response by email",
        value=True,
    )

    if st.button(
        "Save Support Response",
        type="primary",
        use_container_width=True,
        key="admin_save_support_response",
    ):
        values = {
            "request_status": (
                status
            ),
            "assigned_to": (
                assigned_to.strip()
                or None
            ),
            "admin_response": (
                admin_response.strip()
                or None
            ),
            "resolved_at": (
                utc_now_iso()
                if status
                in {
                    "Resolved",
                    "Closed",
                }
                else None
            ),
        }

        updated_request = update_support_request(
            str(
                request["id"]
            ),
            values,
        )

        if (
            send_response
            and admin_response.strip()
            and email_is_configured()
        ):
            try:
                send_support_response_email(
                    updated_request
                    or {
                        **request,
                        **values,
                    }
                )
            except Exception as error:
                st.warning(
                    f"Response saved, but email failed: {error}"
                )

        st.success(
            "Support request updated."
        )

        st.rerun()

    delete_confirmed = st.checkbox(
        "Confirm support-request deletion",
        key="admin_delete_support_confirm",
    )

    if st.button(
        "Delete Support Request",
        disabled=not delete_confirmed,
        use_container_width=True,
        key="admin_delete_support",
    ):
        delete_support_request(
            str(
                request["id"]
            )
        )

        st.rerun()


# ============================================================
# DOCUMENT MANAGEMENT
# ============================================================

def render_admin_task_documents() -> None:
    for study_year in YEARS:
        filename = TASK_DOCUMENTS[
            study_year
        ]

        st.subheader(
            f"{study_year} Task Document"
        )

        current_bytes = load_task_document(
            study_year
        )

        if current_bytes:
            st.success(
                f"`{filename}` is available."
            )

            st.download_button(
                "Download Current Document",
                data=current_bytes,
                file_name=filename,
                mime=DOCX_MIME_TYPE,
                key=(
                    "admin_download_task_"
                    f"{safe_widget_key(study_year)}"
                ),
                use_container_width=True,
            )
        else:
            st.warning(
                "No current task document is available."
            )

        uploaded_file = st.file_uploader(
            "Upload or replace DOCX",
            type=[
                "docx",
            ],
            key=(
                "admin_upload_task_"
                f"{safe_widget_key(study_year)}"
            ),
        )

        upload_confirmed = st.checkbox(
            (
                f"I confirm this is the official "
                f"{study_year} task document."
            ),
            key=(
                "admin_confirm_task_"
                f"{safe_widget_key(study_year)}"
            ),
        )

        if st.button(
            "Save Task Document",
            disabled=(
                uploaded_file is None
                or not upload_confirmed
            ),
            type="primary",
            key=(
                "admin_save_task_"
                f"{safe_widget_key(study_year)}"
            ),
            use_container_width=True,
        ):
            upload_storage_file(
                bucket_name=TASK_DOCUMENT_BUCKET,
                storage_path=filename,
                file_bytes=uploaded_file.getvalue(),
                content_type=DOCX_MIME_TYPE,
                replace_existing=True,
            )

            st.success(
                "Task document saved."
            )

            st.rerun()

        delete_text = st.text_input(
            (
                f"Type DELETE {study_year.upper()} DOCUMENT "
                f"to remove it"
            ),
            key=(
                "admin_delete_task_text_"
                f"{safe_widget_key(study_year)}"
            ),
        )

        expected_text = (
            f"DELETE {study_year.upper()} DOCUMENT"
        )

        if st.button(
            "Delete Task Document",
            disabled=(
                delete_text
                != expected_text
                or current_bytes is None
            ),
            key=(
                "admin_delete_task_"
                f"{safe_widget_key(study_year)}"
            ),
            use_container_width=True,
        ):
            delete_storage_file(
                bucket_name=TASK_DOCUMENT_BUCKET,
                storage_path=filename,
            )

            st.rerun()

        st.divider()


def render_admin_offer_template() -> None:
    st.subheader(
        "Official Offer-Letter Template"
    )

    current_template = load_offer_letter_template()

    if current_template:
        try:
            validation = validate_offer_letter_template(
                current_template
            )

            if validation[
                "valid"
            ]:
                st.success(
                    "The current template is valid."
                )
            else:
                st.error(
                    "The current template is missing required placeholders: "
                    + ", ".join(
                        validation[
                            "missing_required_placeholders"
                        ]
                    )
                )
        except Exception as error:
            st.error(
                f"The current template is invalid: {error}"
            )

        st.download_button(
            "Download Current Template",
            data=current_template,
            file_name=OFFER_LETTER_TEMPLATE_PATH,
            mime=DOCX_MIME_TYPE,
            use_container_width=True,
        )
    else:
        st.warning(
            "No official offer-letter template is uploaded."
        )

    uploaded_template = st.file_uploader(
        "Upload DOCX offer-letter template",
        type=ALLOWED_OFFER_TEMPLATE_EXTENSIONS,
        key="admin_offer_template_upload",
    )

    if uploaded_template:
        if (
            uploaded_template.size
            > MAX_OFFER_TEMPLATE_SIZE
        ):
            st.error(
                "The uploaded template exceeds the size limit."
            )
        else:
            try:
                uploaded_validation = validate_offer_letter_template(
                    uploaded_template.getvalue()
                )

                st.write(
                    "**Detected placeholders:** "
                    + ", ".join(
                        uploaded_validation[
                            "detected_placeholders"
                        ]
                    )
                )

                if not uploaded_validation[
                    "valid"
                ]:
                    st.error(
                        "Missing required placeholders: "
                        + ", ".join(
                            uploaded_validation[
                                "missing_required_placeholders"
                            ]
                        )
                    )
            except Exception as error:
                uploaded_validation = {
                    "valid": False,
                }

                st.error(
                    str(error)
                )

            confirmation = st.checkbox(
                "I confirm this is the official reusable template.",
                key="admin_offer_template_confirm",
            )

            if st.button(
                "Upload or Replace Template",
                type="primary",
                disabled=(
                    not confirmation
                    or not uploaded_validation.get(
                        "valid"
                    )
                ),
                use_container_width=True,
                key="admin_save_offer_template",
            ):
                upload_storage_file(
                    bucket_name=OFFER_LETTER_TEMPLATE_BUCKET,
                    storage_path=OFFER_LETTER_TEMPLATE_PATH,
                    file_bytes=uploaded_template.getvalue(),
                    content_type=DOCX_MIME_TYPE,
                    replace_existing=True,
                )

                st.success(
                    "Offer-letter template saved."
                )

                st.rerun()

    delete_confirmation = st.text_input(
        "Type DELETE OFFER TEMPLATE",
        key="admin_delete_offer_template_text",
    )

    if st.button(
        "Delete Offer-Letter Template",
        disabled=(
            delete_confirmation
            != "DELETE OFFER TEMPLATE"
            or current_template is None
        ),
        use_container_width=True,
        key="admin_delete_offer_template",
    ):
        delete_storage_file(
            bucket_name=OFFER_LETTER_TEMPLATE_BUCKET,
            storage_path=OFFER_LETTER_TEMPLATE_PATH,
        )

        st.rerun()


def render_admin_generated_documents() -> None:
    documents = get_generated_documents()

    if not documents:
        st.info(
            "No generated documents are available."
        )
        return

    st.dataframe(
        pd.DataFrame(
            documents
        ),
        use_container_width=True,
        hide_index=True,
    )

    document_map = {
        (
            f"{document['document_type']} | "
            f"{document['document_number']}"
        ): document
        for document in documents
    }

    selected_label = st.selectbox(
        "Select generated document",
        list(
            document_map.keys()
        ),
        key="admin_generated_document_selection",
    )

    document = document_map[
        selected_label
    ]

    if document.get(
        "storage_path"
    ):
        try:
            file_bytes = download_storage_file(
                bucket_name=GENERATED_DOCUMENT_BUCKET,
                storage_path=str(
                    document[
                        "storage_path"
                    ]
                ),
            )

            extension = (
                "docx"
                if document[
                    "document_type"
                ]
                == "Offer Letter"
                else "pdf"
            )

            mime_type = (
                DOCX_MIME_TYPE
                if extension
                == "docx"
                else "application/pdf"
            )

            st.download_button(
                "Download Selected Document",
                data=file_bytes,
                file_name=(
                    f"{safe_widget_key(document['document_type'])}_"
                    f"{document['document_number']}."
                    f"{extension}"
                ),
                mime=mime_type,
                use_container_width=True,
            )
        except Exception as error:
            st.error(
                str(error)
            )


def render_admin_documents() -> None:
    task_tab, offer_tab, generated_tab = st.tabs(
        [
            "Task Documents",
            "Offer-Letter Template",
            "Generated Documents",
        ]
    )

    with task_tab:
        render_admin_task_documents()

    with offer_tab:
        render_admin_offer_template()

    with generated_tab:
        render_admin_generated_documents()


# ============================================================
# SETTINGS AND ACTIVITY LOGS
# ============================================================

def render_admin_settings_and_logs() -> None:
    settings_tab, logs_tab = st.tabs(
        [
            "Portal Settings",
            "Activity Logs",
        ]
    )

    with settings_tab:
        maintenance = get_setting_safe(
            "maintenance_mode",
            {
                "enabled": False,
                "message": (
                    "The portal is temporarily under maintenance."
                ),
            },
        )

        registration_settings = get_setting_safe(
            "registration_settings",
            {
                "open": True,
                "allowed_years": YEARS,
            },
        )

        submission_settings = get_setting_safe(
            "submission_settings",
            {
                "open": True,
                "allow_drafts": True,
                "enforce_deadline": True,
            },
        )

        project_settings = get_setting_safe(
            "project_showcase_settings",
            {
                "enabled": True,
                "show_featured_first": True,
                "maximum_home_projects_per_club": (
                    DEFAULT_PROJECTS_PER_CLUB
                ),
            },
        )

        support_settings = get_setting_safe(
            "support_settings",
            {
                "enabled": True,
                "contact_email": (
                    "10xdevss@gmail.com"
                ),
            },
        )

        with st.form(
            "admin_portal_settings_form"
        ):
            maintenance_enabled = st.checkbox(
                "Enable maintenance mode",
                value=bool(
                    maintenance.get(
                        "enabled"
                    )
                ),
            )

            maintenance_message = st.text_area(
                "Maintenance message",
                value=str(
                    maintenance.get(
                        "message",
                        "",
                    )
                ),
            )

            registration_open = st.checkbox(
                "Registration is open",
                value=bool(
                    registration_settings.get(
                        "open",
                        True,
                    )
                ),
            )

            allowed_years = st.multiselect(
                "Allowed registration years",
                YEARS,
                default=[
                    year
                    for year in registration_settings.get(
                        "allowed_years",
                        YEARS,
                    )
                    if year in YEARS
                ],
            )

            submission_open = st.checkbox(
                "Submission is open",
                value=bool(
                    submission_settings.get(
                        "open",
                        True,
                    )
                ),
            )

            allow_drafts = st.checkbox(
                "Allow draft submissions",
                value=bool(
                    submission_settings.get(
                        "allow_drafts",
                        True,
                    )
                ),
            )

            enforce_deadline = st.checkbox(
                "Enforce task deadlines",
                value=bool(
                    submission_settings.get(
                        "enforce_deadline",
                        True,
                    )
                ),
            )

            project_showcase_enabled = st.checkbox(
                "Enable project showcase",
                value=bool(
                    project_settings.get(
                        "enabled",
                        True,
                    )
                ),
            )

            projects_per_club = st.number_input(
                "Maximum home-page projects per club",
                min_value=1,
                max_value=20,
                value=int(
                    project_settings.get(
                        "maximum_home_projects_per_club",
                        DEFAULT_PROJECTS_PER_CLUB,
                    )
                ),
            )

            support_enabled = st.checkbox(
                "Enable support requests",
                value=bool(
                    support_settings.get(
                        "enabled",
                        True,
                    )
                ),
            )

            support_email = st.text_input(
                "Support contact email",
                value=str(
                    support_settings.get(
                        "contact_email",
                        "10xdevss@gmail.com",
                    )
                ),
            )

            saved = st.form_submit_button(
                "Save Portal Settings",
                type="primary",
                use_container_width=True,
            )

        if saved:
            updated_by = str(
                st.secrets[
                    "ADMIN_USERNAME"
                ]
            )

            update_portal_setting(
                "maintenance_mode",
                {
                    "enabled": (
                        maintenance_enabled
                    ),
                    "message": (
                        maintenance_message.strip()
                    ),
                },
                updated_by,
            )

            update_portal_setting(
                "registration_settings",
                {
                    "open": registration_open,
                    "allowed_years": (
                        allowed_years
                    ),
                },
                updated_by,
            )

            update_portal_setting(
                "submission_settings",
                {
                    "open": submission_open,
                    "allow_drafts": (
                        allow_drafts
                    ),
                    "enforce_deadline": (
                        enforce_deadline
                    ),
                },
                updated_by,
            )

            update_portal_setting(
                "project_showcase_settings",
                {
                    "enabled": (
                        project_showcase_enabled
                    ),
                    "show_featured_first": True,
                    "maximum_home_projects_per_club": int(
                        projects_per_club
                    ),
                },
                updated_by,
            )

            update_portal_setting(
                "support_settings",
                {
                    "enabled": (
                        support_enabled
                    ),
                    "contact_email": (
                        support_email.strip()
                    ),
                },
                updated_by,
            )

            log_activity_safe(
                actor_type="Admin",
                actor_identifier=updated_by,
                action=ACTIVITY_ACTIONS[
                    "settings_updated"
                ],
                entity_type="Portal Settings",
            )

            st.success(
                "Portal settings saved."
            )

            st.rerun()

    with logs_tab:
        logs = get_activity_logs(
            limit=1000
        )

        if not logs:
            st.info(
                "No activity logs are available."
            )
        else:
            log_frame = pd.DataFrame(
                logs
            )

            st.dataframe(
                log_frame,
                use_container_width=True,
                hide_index=True,
            )

            st.download_button(
                "Download Activity Logs CSV",
                data=log_frame.to_csv(
                    index=False
                ).encode(
                    "utf-8"
                ),
                file_name=(
                    "10x_devs_activity_logs.csv"
                ),
                mime="text/csv",
                use_container_width=True,
            )


# ============================================================
# DATA BACKUP, ZIP EXPORT AND DELETION
# ============================================================

def build_database_backup_zip(
    registrations: list[dict[str, Any]],
    submissions: list[dict[str, Any]],
) -> bytes:
    buffer = BytesIO()

    with zipfile.ZipFile(
        buffer,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        datasets = {
            "registrations.csv": (
                safe_registration_frame(
                    registrations
                )
            ),
            "proof_submissions.csv": (
                pd.DataFrame(
                    submissions
                )
            ),
            "announcements.csv": (
                pd.DataFrame(
                    get_all_announcements()
                )
            ),
            "club_projects.csv": (
                pd.DataFrame(
                    get_all_club_projects()
                )
            ),
            "interviews.csv": (
                pd.DataFrame(
                    get_all_interview_schedules()
                )
            ),
            "onboarding.csv": (
                pd.DataFrame(
                    get_all_onboarding_attendance()
                )
            ),
            "support_requests.csv": (
                pd.DataFrame(
                    get_all_support_requests()
                )
            ),
            "activity_logs.csv": (
                pd.DataFrame(
                    get_activity_logs(
                        limit=10000
                    )
                )
            ),
        }

        for filename, frame in datasets.items():
            archive.writestr(
                filename,
                frame.to_csv(
                    index=False
                ),
            )

    buffer.seek(
        0
    )

    return buffer.getvalue()


def build_submission_files_zip(
    registrations: list[dict[str, Any]],
    submissions: list[dict[str, Any]],
) -> tuple[bytes, int]:
    student_by_id = {
        str(
            student["id"]
        ): student
        for student in registrations
    }

    buffer = BytesIO()
    file_count = 0

    with zipfile.ZipFile(
        buffer,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for submission in submissions:
            student = student_by_id.get(
                str(
                    submission.get(
                        "registration_id"
                    )
                )
            )

            if not student:
                continue

            student_folder = (
                f"{student['registration_number']}_"
                f"{safe_widget_key(student['full_name'])}"
            )

            all_file_records = [
                *parse_json_list(
                    submission.get(
                        "proof_files",
                        [],
                    )
                ),
            ]

            for evidence in parse_json_list(
                submission.get(
                    "specific_task_evidence",
                    [],
                )
            ):
                if isinstance(
                    evidence,
                    dict,
                ):
                    all_file_records.extend(
                        parse_json_list(
                            evidence.get(
                                "files",
                                [],
                            )
                        )
                    )

            for file_record in all_file_records:
                if not isinstance(
                    file_record,
                    dict,
                ):
                    continue

                storage_path = str(
                    file_record.get(
                        "path",
                        "",
                    )
                ).strip()

                if not storage_path:
                    continue

                try:
                    file_bytes = download_storage_file(
                        bucket_name=PROOF_SUBMISSION_BUCKET,
                        storage_path=storage_path,
                    )

                    filename = clean_filename(
                        str(
                            file_record.get(
                                "name",
                                Path(
                                    storage_path
                                ).name,
                            )
                        )
                    )

                    archive.writestr(
                        f"{student_folder}/{filename}",
                        file_bytes,
                    )

                    file_count += 1
                except Exception:
                    continue

    buffer.seek(
        0
    )

    return (
        buffer.getvalue(),
        file_count,
    )


def render_admin_data_management(
    registrations: list[dict[str, Any]],
    submissions: list[dict[str, Any]],
) -> None:
    st.subheader(
        "Backup and Export"
    )

    backup_bytes = build_database_backup_zip(
        registrations,
        submissions,
    )

    st.download_button(
        "Download Database Backup ZIP",
        data=backup_bytes,
        file_name=(
            f"10x_devs_backup_"
            f"{date.today().isoformat()}.zip"
        ),
        mime="application/zip",
        use_container_width=True,
    )

    if st.button(
        "Prepare All Submission Files ZIP",
        use_container_width=True,
        key="admin_prepare_submission_zip",
    ):
        with st.spinner(
            "Downloading submission files from private storage..."
        ):
            submission_zip, file_count = build_submission_files_zip(
                registrations,
                submissions,
            )

        st.session_state[
            "admin_submission_zip"
        ] = submission_zip

        st.session_state[
            "admin_submission_zip_count"
        ] = file_count

    if st.session_state.get(
        "admin_submission_zip"
    ):
        st.download_button(
            (
                "Download All Submission Files "
                f"({st.session_state.get('admin_submission_zip_count', 0)} files)"
            ),
            data=st.session_state[
                "admin_submission_zip"
            ],
            file_name=(
                f"10x_devs_submission_files_"
                f"{date.today().isoformat()}.zip"
            ),
            mime="application/zip",
            use_container_width=True,
        )

    st.divider()
    st.subheader(
        "Delete One Registration"
    )

    if registrations:
        options = registration_option_map(
            registrations
        )

        selected_label = st.selectbox(
            "Student to delete",
            list(
                options.keys()
            ),
            key="admin_delete_student_selection",
        )

        student = options[
            selected_label
        ]

        expected_text = str(
            student[
                "registration_number"
            ]
        )

        confirmation_text = st.text_input(
            f"Type {expected_text}",
            key="admin_delete_student_text",
        )

        permanent_confirmation = st.checkbox(
            "I understand that the student, submission, timeline and "
            "stored evidence will be deleted permanently.",
            key="admin_delete_student_checkbox",
        )

        if st.button(
            "Delete Selected Registration",
            disabled=(
                confirmation_text.strip().upper()
                != expected_text.upper()
                or not permanent_confirmation
            ),
            use_container_width=True,
            key="admin_delete_selected_student",
        ):
            result = delete_registration_and_related_data(
                str(
                    student["id"]
                )
            )

            st.success(
                f"Registration deleted. "
                f"Proof files removed: "
                f"{result['proof_files_deleted']}."
            )

            st.rerun()

    st.divider()

    with st.expander(
        "Delete All Registration and Submission Data"
    ):
        st.error(
            "This permanently deletes every registration and related "
            "submission. Task documents, templates and club projects "
            "are retained."
        )

        confirmation_text = st.text_input(
            "Type DELETE ALL 10X DATA",
            key="admin_delete_all_text_v2",
        )

        permanent_confirmation = st.checkbox(
            "I understand that this operation cannot be undone.",
            key="admin_delete_all_checkbox_v2",
        )

        if st.button(
            "Delete All Registration Data",
            disabled=(
                confirmation_text
                != "DELETE ALL 10X DATA"
                or not permanent_confirmation
            ),
            use_container_width=True,
            key="admin_delete_all_v2",
        ):
            result = delete_all_registration_data()

            st.success(
                f"Deleted: "
                f"{result['registrations_deleted']}; "
                f"failed: "
                f"{result['registrations_failed']}."
            )

            st.rerun()


# ============================================================
# ADMIN DASHBOARD
# ============================================================

def render_admin_dashboard() -> None:
    title_column, logout_column = st.columns(
        [
            5,
            1,
        ]
    )

    with title_column:
        st.title(
            "10x Devs Administration"
        )

    with logout_column:
        if st.button(
            "Logout",
            key="admin_logout_v2",
            use_container_width=True,
        ):
            logout_everyone()
            navigate_to(
                "login"
            )

    try:
        registrations = get_all_registrations()
        submissions = get_all_proof_submissions()
    except Exception as error:
        st.error(
            "Administration data could not be loaded."
        )
        st.code(
            str(error)
        )
        return

    (
        analytics_tab,
        students_tab,
        submissions_tab,
        communications_tab,
        projects_tab,
        interview_tab,
        evaluators_tab,
        support_tab,
        documents_tab,
        settings_tab,
        data_tab,
    ) = st.tabs(
        [
            "Analytics",
            "Students",
            "Submissions",
            "Communications",
            "Projects",
            "Interviews & Onboarding",
            "Evaluators",
            "Support",
            "Documents",
            "Settings & Logs",
            "Data Management",
        ]
    )

    with analytics_tab:
        render_admin_analytics(
            registrations,
            submissions,
        )

    with students_tab:
        render_admin_students(
            registrations
        )

    with submissions_tab:
        render_submission_review_workspace(
            registrations,
            submissions,
            actor_type="Admin",
            actor_identifier=str(
                st.secrets[
                    "ADMIN_USERNAME"
                ]
            ),
        )

    with communications_tab:
        render_admin_communications(
            registrations,
            submissions,
        )

    with projects_tab:
        render_admin_projects()

    with interview_tab:
        render_admin_interviews_onboarding(
            registrations
        )

    with evaluators_tab:
        render_admin_evaluators()

    with support_tab:
        render_admin_support()

    with documents_tab:
        render_admin_documents()

    with settings_tab:
        render_admin_settings_and_logs()

    with data_tab:
        render_admin_data_management(
            registrations,
            submissions,
        )


# ============================================================
# EVALUATOR DASHBOARD
# ============================================================

def render_evaluator_dashboard() -> None:
    evaluator_id = st.session_state[
        "evaluator_id"
    ]

    evaluators = get_all_evaluators()

    evaluator = next(
        (
            record
            for record in evaluators
            if str(
                record["id"]
            )
            == str(
                evaluator_id
            )
        ),
        None,
    )

    if not evaluator:
        logout_everyone()
        navigate_to(
            "login"
        )

    title_column, logout_column = st.columns(
        [
            5,
            1,
        ]
    )

    with title_column:
        st.title(
            f"Evaluator Dashboard — "
            f"{evaluator['full_name']}"
        )

    with logout_column:
        if st.button(
            "Logout",
            key="evaluator_logout_v2",
            use_container_width=True,
        ):
            logout_everyone()
            navigate_to(
                "login"
            )

    assigned_clubs = evaluator.get(
        "assigned_clubs",
        [],
    )

    st.info(
        "Assigned clubs: "
        + (
            ", ".join(
                assigned_clubs
            )
            if assigned_clubs
            else "All clubs"
        )
    )

    registrations = get_all_registrations()
    submissions = get_all_proof_submissions()

    render_submission_review_workspace(
        registrations,
        submissions,
        actor_type="Evaluator",
        actor_identifier=str(
            evaluator["username"]
        ),
        evaluator=evaluator,
    )


# ============================================================
# MAINTENANCE PAGE
# ============================================================

def render_maintenance_page(
    settings: dict[str, Any],
) -> None:
    st.title(
        "Portal Maintenance"
    )

    st.warning(
        str(
            settings.get(
                "message",
                "The portal is temporarily under maintenance.",
            )
        )
    )

    st.caption(
        "Administrators can continue to log in and manage the portal."
    )

    if st.button(
        "Administrator Login",
        type="primary",
        use_container_width=True,
    ):
        navigate_to(
            "login"
        )


# ============================================================
# ROUTER
# ============================================================

if st.query_params.get(
    "home"
) == "1":
    logout_everyone()
    st.session_state[
        "page"
    ] = "landing"
    st.query_params.clear()
    st.rerun()


render_sidebar()


if not configuration_is_valid():
    st.stop()


maintenance_settings = maintenance_mode_settings()

maintenance_enabled = bool(
    maintenance_settings.get(
        "enabled",
        False,
    )
)


if st.session_state[
    "admin_authenticated"
]:
    render_admin_dashboard()

elif (
    maintenance_enabled
    and not st.session_state[
        "admin_authenticated"
    ]
):
    render_maintenance_page(
        maintenance_settings
    )

elif st.session_state[
    "evaluator_authenticated"
]:
    render_evaluator_dashboard()

elif st.session_state[
    "student_authenticated"
]:
    render_student_dashboard()

elif st.session_state[
    "page"
] == "landing":
    render_landing_page()

elif st.session_state[
    "page"
] == "register":
    render_registration_page()

elif st.session_state[
    "page"
] == "projects":
    render_projects_page()

elif st.session_state[
    "page"
] == "forgot_password":
    render_forgot_password_page()

elif st.session_state[
    "page"
] == "support":
    render_public_support_page()

else:
    render_login_page()

from __future__ import annotations

import hmac
import html
import json
import mimetypes
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

from core.auth import hash_password, verify_password
from core.constants import (
    ALLOWED_PROOF_EXTENSIONS,
    APPLICATION_STATUSES,
    CLUBS,
    MAX_PROOF_FILES,
    MAX_TOTAL_PROOF_SIZE,
    TASK_DOCUMENTS,
    YEARS,
)
from core.database import (
    create_proof_submission,
    create_registration,
    create_temporary_file_url,
    delete_all_registration_data,
    delete_registration_and_related_data,
    delete_storage_file,
    download_storage_file,
    find_duplicate_registration,
    get_all_proof_submissions,
    get_all_registrations,
    get_proof_submission,
    get_student,
    update_registration,
    upload_storage_file,
)
from core.email_service import (
    email_is_configured,
    send_registration_email,
)


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="10x Devs",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# LOAD CSS
# ============================================================

css_path = Path("assets/style.css")

if css_path.exists():
    st.markdown(
        (
            "<style>"
            + css_path.read_text(
                encoding="utf-8"
            )
            + "</style>"
        ),
        unsafe_allow_html=True,
    )


# ============================================================
# CONFIGURATION CHECK
# ============================================================

def configuration_is_valid() -> bool:
    required_values = [
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "ADMIN_USERNAME",
        "ADMIN_PASSWORD",
    ]

    missing_values = [
        setting_name
        for setting_name in required_values
        if not str(
            st.secrets.get(
                setting_name,
                "",
            )
        ).strip()
    ]

    if missing_values:
        st.error(
            "Application configuration is incomplete."
        )

        st.write(
            "Missing settings: "
            + ", ".join(missing_values)
        )

        return False

    return True


# ============================================================
# SESSION STATE
# ============================================================

if "page" not in st.session_state:
    st.session_state.page = "landing"

if "student_authenticated" not in st.session_state:
    st.session_state.student_authenticated = False

if "admin_authenticated" not in st.session_state:
    st.session_state.admin_authenticated = False

if "student_registration_number" not in st.session_state:
    st.session_state.student_registration_number = None


# ============================================================
# GENERAL HELPERS
# ============================================================

def normalize_registration_number(
    value: str,
) -> str:
    return (
        value.strip()
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
    clean_value = value.strip()

    return (
        len(clean_value) >= 6
        and "@" in clean_value
        and "." in clean_value.split("@")[-1]
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
        parsed_url.scheme in {
            "http",
            "https",
        }
        and bool(parsed_url.netloc)
    )


def value_is_present(
    value: object,
) -> bool:
    """Safely check values coming from a Pandas DataFrame."""

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


def is_reserved_admin_value(
    value: str,
) -> bool:
    normalized_value = (
        value.strip().casefold()
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


def load_task_document(
    study_year: str,
) -> bytes | None:
    try:
        return download_storage_file(
            bucket_name="task-documents",
            storage_path=TASK_DOCUMENTS[
                study_year
            ],
        )

    except Exception:
        return None


def logout_everyone() -> None:
    st.session_state.student_authenticated = False
    st.session_state.admin_authenticated = False
    st.session_state.student_registration_number = None


def open_public_page(
    page_name: str,
) -> None:
    logout_everyone()

    st.session_state.page = page_name

    st.rerun()


# ============================================================
# EMAIL RETRY
# ============================================================

def retry_registration_email(
    student: dict,
) -> tuple[bool, str]:
    """Retry a failed or pending registration email."""

    if not email_is_configured():
        return (
            False,
            "Gmail SMTP is not configured. Check GMAIL_ADDRESS "
            "and GMAIL_APP_PASSWORD in Streamlit Secrets.",
        )

    task_document = load_task_document(
        student["study_year"]
    )

    if task_document is None:
        return (
            False,
            f"The {student['study_year']} task document "
            "is not available.",
        )

    try:
        message_id = send_registration_email(
            student,
            task_document,
        )

        update_registration(
            student["id"],
            {
                "email_status": "Sent",
                "email_error": None,
                "email_message_id": message_id,
            },
        )

        return (
            True,
            "Registration email sent successfully.",
        )

    except Exception as error:
        error_message = str(error)

        update_registration(
            student["id"],
            {
                "email_status": "Failed",
                "email_error": error_message[:1000],
                "email_message_id": None,
            },
        )

        return (
            False,
            error_message,
        )


# ============================================================
# SIDEBAR
# ============================================================

def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            (
                '<a class="sidebar-brand-link" '
                'href="?home=1" target="_self">'
                '<span>10x</span> Devs'
                "</a>"
                '<div class="sidebar-subtitle">'
                "Student Club Registration Portal"
                "</div>"
            ),
            unsafe_allow_html=True,
        )

        register_active = (
            st.session_state.page == "register"
            and not st.session_state.student_authenticated
            and not st.session_state.admin_authenticated
        )

        login_active = (
            st.session_state.page == "login"
            or st.session_state.student_authenticated
            or st.session_state.admin_authenticated
        )

        register_clicked = st.button(
            "Register",
            key="navigation_register",
            type=(
                "primary"
                if register_active
                else "secondary"
            ),
            use_container_width=True,
        )

        login_clicked = st.button(
            "Login",
            key="navigation_login",
            type=(
                "primary"
                if login_active
                else "secondary"
            ),
            use_container_width=True,
        )

        if register_clicked:
            open_public_page(
                "register"
            )

        if login_clicked:
            open_public_page(
                "login"
            )

        st.markdown(
            '<div class="sidebar-divider"></div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            (
                '<div class="sidebar-clubs">'
                '<div class="sidebar-clubs-title">'
                "Technical Clubs"
                "</div>"
                '<div class="sidebar-club-name">'
                "Computer Vision Club"
                "</div>"
                '<div class="sidebar-club-name">'
                "Web Development Club"
                "</div>"
                '<div class="sidebar-club-name">'
                "Machine Learning Club"
                "</div>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )


# ============================================================
# LANDING PAGE
# ============================================================

def render_leadership_section() -> None:
    st.markdown(
        (
            '<section class="leadership-panel">'
            '<div class="leadership-heading">'
            '<div class="leadership-heading-label">'
            "10x Devs Leadership"
            "</div>"
            '<div class="leadership-heading-title">'
            "Academic leadership and coordination"
            "</div>"
            '<div class="leadership-heading-description">'
            "10x Devs operates under the guidance of the "
            "institutional and departmental leadership of "
            "CSE (Artificial Intelligence and Machine Learning)."
            "</div>"
            "</div>"
            '<div class="leadership-grid">'
            '<div class="leadership-card">'
            '<div class="leadership-role">Inaugurated by</div>'
            '<div class="leadership-name">'
            "Dr. Ravi Kadiyala"
            "</div>"
            '<div class="leadership-designation">'
            "Principal"
            "</div>"
            "</div>"
            '<div class="leadership-card">'
            '<div class="leadership-role">President</div>'
            '<div class="leadership-name">'
            "Dr. Ch. Suresh Babu"
            "</div>"
            '<div class="leadership-designation">'
            "Head of the Department, CSE (AI &amp; ML)"
            "</div>"
            "</div>"
            '<div class="leadership-card">'
            '<div class="leadership-role">Secretary</div>'
            '<div class="leadership-name">'
            "A. Sri Chaitanya"
            "</div>"
            '<div class="leadership-designation">'
            "Ph.D."
            "</div>"
            "</div>"
            '<div class="leadership-card">'
            '<div class="leadership-role">Coordinator</div>'
            '<div class="leadership-name">'
            "Chetan Ventrapragada"
            "</div>"
            '<div class="leadership-designation">'
            "Final-Year Student"
            "</div>"
            "</div>"
            "</div>"
            "</section>"
        ),
        unsafe_allow_html=True,
    )


def render_landing_page() -> None:
    st.markdown(
        (
            '<section class="hero">'
            '<div class="hero-label">'
            "REGISTRATION • PROJECTS • COMMUNITY"
            "</div>"
            '<h1 class="hero-title">'
            'Build at <span>10x.</span>'
            "</h1>"
            '<p class="hero-description">'
            "10x Devs is a student technical community of the "
            "Department of Computer Science and Engineering "
            "(Artificial Intelligence and Machine Learning). "
            "The community focuses on practical learning, "
            "collaborative development and industry-oriented projects."
            "</p>"
            "</section>"
        ),
        unsafe_allow_html=True,
    )

    st.markdown(
        (
            '<section class="about-panel">'
            '<div class="about-label">'
            "About 10x Devs"
            "</div>"
            '<div class="about-title">'
            "Practical learning through technical clubs"
            "</div>"
            '<div class="about-description">'
            "10x Devs was officially started on 25 January 2025. "
            "It provides students with opportunities to work in "
            "focused technical clubs, complete structured tasks, "
            "participate in projects and demonstrate practical skills."
            "</div>"
            "</section>"
        ),
        unsafe_allow_html=True,
    )

    render_leadership_section()


# ============================================================
# REGISTRATION PAGE
# ============================================================

def render_registration_page() -> None:
    st.markdown(
        (
            '<div class="page-header">'
            '<div class="page-kicker">'
            "Student application"
            "</div>"
            '<div class="page-title">'
            "Create your account"
            "</div>"
            '<div class="page-description">'
            "Enter accurate academic information and select exactly "
            "one club. The selected club cannot be changed later."
            "</div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )

    with st.form(
        "student_registration_form",
        clear_on_submit=False,
    ):
        full_name = st.text_input(
            "Full name",
            placeholder="Enter your complete name",
        )

        registration_number = st.text_input(
            "Registration number",
            placeholder="Example: 238T1A4201",
        )

        year_column, email_column = st.columns(2)

        with year_column:
            study_year = st.selectbox(
                "Current academic year",
                YEARS,
            )

        with email_column:
            email = st.text_input(
                "Email address",
                placeholder="student@example.com",
            )

        password_column, confirm_column = st.columns(2)

        with password_column:
            password = st.text_input(
                "Create password",
                type="password",
            )

        with confirm_column:
            confirm_password = st.text_input(
                "Confirm password",
                type="password",
            )

        club = st.selectbox(
            "Select one club",
            CLUBS,
        )

        declaration = st.checkbox(
            "I confirm that the entered information is accurate "
            "and understand that the selected club cannot be changed."
        )

        submitted = st.form_submit_button(
            "Create Account",
            type="primary",
            use_container_width=True,
        )

    if not submitted:
        return

    clean_name = normalize_name(
        full_name
    )

    clean_registration_number = (
        normalize_registration_number(
            registration_number
        )
    )

    clean_email = email.strip().lower()

    errors: list[str] = []

    if len(clean_name) < 3:
        errors.append(
            "Enter your complete name."
        )

    if is_reserved_admin_value(
        clean_name
    ):
        errors.append(
            "The name 'admin' is reserved."
        )

    if is_reserved_admin_value(
        clean_registration_number
    ):
        errors.append(
            "The registration number 'admin' is reserved."
        )

    if len(clean_registration_number) < 5:
        errors.append(
            "Enter a valid registration number."
        )

    if not is_valid_email(
        clean_email
    ):
        errors.append(
            "Enter a valid email address."
        )

    if len(password) < 8:
        errors.append(
            "Password must contain at least 8 characters."
        )

    if password != confirm_password:
        errors.append(
            "Password and confirm password do not match."
        )

    if not declaration:
        errors.append(
            "Accept the declaration before creating the account."
        )

    if errors:
        for error_message in errors:
            st.error(
                error_message
            )

        return

    try:
        duplicate_message = (
            find_duplicate_registration(
                clean_registration_number,
                clean_email,
            )
        )

    except Exception as error:
        st.error(
            "Could not connect to Supabase."
        )

        st.code(
            str(error)
        )

        return

    if duplicate_message:
        st.error(
            duplicate_message
        )

        return

    task_document = load_task_document(
        study_year
    )

    if task_document is None:
        st.error(
            f"The administrator has not uploaded the "
            f"{study_year} task document."
        )

        return

    deadline_days = int(
        st.secrets.get(
            "TASK_DEADLINE_DAYS",
            2,
        )
    )

    task_deadline = (
        date.today()
        + timedelta(
            days=deadline_days
        )
    )

    registration_data = {
        "full_name": clean_name,
        "registration_number": clean_registration_number,
        "study_year": study_year,
        "email": clean_email,
        "password_hash": hash_password(
            password
        ),
        "club": club,
        "task_deadline": task_deadline.isoformat(),
        "email_status": "Pending",
        "application_status": "Registered",
    }

    try:
        with st.spinner(
            "Creating your account..."
        ):
            student = create_registration(
                registration_data
            )

        application_reference = student[
            "application_reference"
        ]

        candidate_number = student[
            "candidate_number"
        ]

        email_status = "Pending"
        email_error_message = None

        if email_is_configured():
            try:
                message_id = send_registration_email(
                    student,
                    task_document,
                )

                email_status = "Sent"

                update_registration(
                    student["id"],
                    {
                        "email_status": "Sent",
                        "email_error": None,
                        "email_message_id": message_id,
                    },
                )

            except Exception as email_error:
                email_status = "Failed"

                email_error_message = str(
                    email_error
                )

                update_registration(
                    student["id"],
                    {
                        "email_status": "Failed",
                        "email_error": (
                            email_error_message[:1000]
                        ),
                        "email_message_id": None,
                    },
                )

        st.success(
            "Your account was created successfully."
        )

        reference_column, candidate_column = st.columns(
            2
        )

        with reference_column:
            st.markdown(
                (
                    '<div class="reference-card">'
                    '<div class="reference-label">'
                    "APPLICATION REFERENCE"
                    "</div>"
                    '<div class="reference-value">'
                    f"{html.escape(application_reference)}"
                    "</div>"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )

        with candidate_column:
            st.markdown(
                (
                    '<div class="reference-card">'
                    '<div class="reference-label">'
                    "CANDIDATE NUMBER"
                    "</div>"
                    '<div class="reference-value">'
                    f"{html.escape(candidate_number)}"
                    "</div>"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )

        st.write(
            f"**Selected club:** {club}"
        )

        st.write(
            f"**Academic year:** {study_year}"
        )

        st.write(
            f"**Task deadline:** {task_deadline}"
        )

        st.write(
            f"**Email status:** {email_status}"
        )

        if email_status == "Failed":
            st.warning(
                "The account was created, but the email could "
                "not be delivered. The administrator can retry it."
            )

            if email_error_message:
                with st.expander(
                    "Email delivery details"
                ):
                    st.code(
                        email_error_message
                    )

        elif email_status == "Pending":
            st.info(
                "Email automation is not configured. "
                "Download the task document below."
            )

        st.download_button(
            label=(
                f"Download {study_year} "
                "Task Document"
            ),
            data=task_document,
            file_name=TASK_DOCUMENTS[
                study_year
            ],
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
            use_container_width=True,
        )

    except Exception as error:
        st.error(
            "The account could not be created."
        )

        st.code(
            str(error)
        )


# ============================================================
# LOGIN PAGE
# ============================================================

def render_login_page() -> None:
    st.markdown(
        (
            '<div class="page-header">'
            '<div class="page-kicker">'
            "Secure access"
            "</div>"
            '<div class="page-title">'
            "Login to your account"
            "</div>"
            '<div class="page-description">'
            "Enter your account ID and password to continue."
            "</div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )

    with st.form(
        "combined_login_form"
    ):
        identifier = st.text_input(
            "Account ID",
            placeholder="Enter your registration number",
        )

        password = st.text_input(
            "Password",
            type="password",
        )

        submitted = st.form_submit_button(
            "Login",
            type="primary",
            use_container_width=True,
        )

    if not submitted:
        return

    clean_identifier = identifier.strip()

    admin_username = str(
        st.secrets["ADMIN_USERNAME"]
    ).strip()

    admin_password = str(
        st.secrets["ADMIN_PASSWORD"]
    )

    if hmac.compare_digest(
        clean_identifier.casefold(),
        admin_username.casefold(),
    ):
        if hmac.compare_digest(
            password,
            admin_password,
        ):
            st.session_state.admin_authenticated = True
            st.session_state.student_authenticated = False
            st.session_state.student_registration_number = None

            st.rerun()

        else:
            st.error(
                "The entered credentials are incorrect."
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

    if (
        student
        and verify_password(
            password,
            student["password_hash"],
        )
    ):
        st.session_state.student_authenticated = True
        st.session_state.admin_authenticated = False

        st.session_state.student_registration_number = (
            student["registration_number"]
        )

        st.rerun()

    else:
        st.error(
            "The entered credentials are incorrect."
        )


# ============================================================
# STUDENT DASHBOARD
# ============================================================

def render_student_dashboard() -> None:
    try:
        student = get_student(
            st.session_state.student_registration_number
        )

    except Exception as error:
        st.error(
            "The student dashboard could not be loaded."
        )

        st.code(
            str(error)
        )

        return

    if student is None:
        logout_everyone()

        st.session_state.page = "login"

        st.rerun()

    title_column, logout_column = st.columns(
        [5, 1]
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

            st.session_state.page = "login"

            st.rerun()

    safe_club = html.escape(
        str(student["club"])
    )

    safe_status = html.escape(
        str(student["application_status"])
    )

    safe_deadline = html.escape(
        str(student["task_deadline"])
    )

    st.markdown(
        (
            '<section class="dashboard-summary-grid">'
            '<div class="dashboard-summary-card">'
            '<div class="dashboard-summary-label">'
            "Registered Club"
            "</div>"
            '<div class="dashboard-summary-value '
            'dashboard-club-value">'
            f"{safe_club}"
            "</div>"
            "</div>"
            '<div class="dashboard-summary-card">'
            '<div class="dashboard-summary-label">'
            "Application Status"
            "</div>"
            '<div class="dashboard-summary-value">'
            f"{safe_status}"
            "</div>"
            "</div>"
            '<div class="dashboard-summary-card">'
            '<div class="dashboard-summary-label">'
            "Task Deadline"
            "</div>"
            '<div class="dashboard-summary-value">'
            f"{safe_deadline}"
            "</div>"
            "</div>"
            "</section>"
        ),
        unsafe_allow_html=True,
    )

    details_left, details_right = st.columns(
        2
    )

    with details_left:
        st.write(
            f"**Registration number:** "
            f"{student['registration_number']}"
        )

        st.write(
            f"**Academic year:** "
            f"{student['study_year']}"
        )

        st.write(
            f"**Email:** {student['email']}"
        )

    with details_right:
        st.write(
            f"**Application reference:** "
            f"{student['application_reference']}"
        )

        st.write(
            f"**Candidate number:** "
            f"{student['candidate_number']}"
        )

        st.write(
            f"**Email status:** "
            f"{student['email_status']}"
        )

    task_document = load_task_document(
        student["study_year"]
    )

    if task_document:
        st.download_button(
            label=(
                f"Download {student['study_year']} "
                "Task Document"
            ),
            data=task_document,
            file_name=TASK_DOCUMENTS[
                student["study_year"]
            ],
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        )

    try:
        submission = get_proof_submission(
            student["id"]
        )

    except Exception as error:
        st.error(
            "The proof-submission status could not be loaded."
        )

        st.code(
            str(error)
        )

        return

    if submission:
        st.markdown(
            (
                '<div class="success-notice">'
                "Your proof has already been submitted. "
                "A second submission is not allowed."
                "</div>"
            ),
            unsafe_allow_html=True,
        )

        st.write(
            f"**Submitted at:** "
            f"{submission['submitted_at']}"
        )

        st.write(
            f"**GitHub repository:** "
            f"{submission.get('github_url') or 'Not provided'}"
        )

        st.write(
            f"**Deployment:** "
            f"{submission.get('deployment_url') or 'Not provided'}"
        )

        st.write(
            f"**Demonstration video:** "
            f"{submission.get('video_url') or 'Not provided'}"
        )

        st.write(
            f"**Work summary:** "
            f"{submission.get('notes') or 'Not provided'}"
        )

        return

    render_proof_submission_form(
        student
    )


# ============================================================
# PROOF SUBMISSION
# ============================================================

def render_proof_submission_form(
    student: dict,
) -> None:
    st.subheader(
        "Final Proof Submission"
    )

    st.warning(
        "This submission can be completed only once."
    )

    with st.form(
        "proof_submission_form"
    ):
        github_url = st.text_input(
            "GitHub repository URL"
        )

        deployment_url = st.text_input(
            "Deployment or portfolio URL"
        )

        video_url = st.text_input(
            "Demonstration video URL"
        )

        notes = st.text_area(
            "Work summary"
        )

        uploaded_files = st.file_uploader(
            "Proof files",
            type=ALLOWED_PROOF_EXTENSIONS,
            accept_multiple_files=True,
        )

        confirmation = st.checkbox(
            "I understand that this submission is final."
        )

        submitted = st.form_submit_button(
            "Submit Proof Permanently",
            type="primary",
            use_container_width=True,
        )

    if not submitted:
        return

    uploaded_files = uploaded_files or []

    clean_github_url = github_url.strip()
    clean_deployment_url = deployment_url.strip()
    clean_video_url = video_url.strip()

    if not confirmation:
        st.error(
            "Accept the final confirmation."
        )

        return

    invalid_urls = []

    if not is_valid_url(
        clean_github_url
    ):
        invalid_urls.append(
            "GitHub URL"
        )

    if not is_valid_url(
        clean_deployment_url
    ):
        invalid_urls.append(
            "Deployment URL"
        )

    if not is_valid_url(
        clean_video_url
    ):
        invalid_urls.append(
            "Video URL"
        )

    if invalid_urls:
        st.error(
            "Enter valid URLs for: "
            + ", ".join(invalid_urls)
        )

        return

    if not any(
        [
            clean_github_url,
            clean_deployment_url,
            clean_video_url,
            uploaded_files,
        ]
    ):
        st.error(
            "Provide at least one proof link or file."
        )

        return

    if len(uploaded_files) > MAX_PROOF_FILES:
        st.error(
            f"Upload no more than "
            f"{MAX_PROOF_FILES} files."
        )

        return

    total_size = sum(
        file.size
        for file in uploaded_files
    )

    if total_size > MAX_TOTAL_PROOF_SIZE:
        st.error(
            "The combined file size must not exceed 25 MB."
        )

        return

    if get_proof_submission(
        student["id"]
    ):
        st.error(
            "Proof has already been submitted."
        )

        return

    stored_files = []

    try:
        for index, uploaded_file in enumerate(
            uploaded_files,
            start=1,
        ):
            safe_name = (
                Path(
                    uploaded_file.name
                )
                .name
                .replace(" ", "_")
                .replace("/", "_")
                .replace("\\", "_")
            )

            storage_path = (
                f"{student['application_reference']}/"
                f"{index}_{safe_name}"
            )

            content_type = (
                uploaded_file.type
                or mimetypes.guess_type(
                    safe_name
                )[0]
                or "application/octet-stream"
            )

            upload_storage_file(
                bucket_name="proof-submissions",
                storage_path=storage_path,
                file_bytes=uploaded_file.getvalue(),
                content_type=content_type,
                replace_existing=False,
            )

            stored_files.append(
                {
                    "name": safe_name,
                    "path": storage_path,
                    "content_type": content_type,
                    "size": uploaded_file.size,
                }
            )

        create_proof_submission(
            {
                "registration_id": student["id"],
                "github_url": clean_github_url or None,
                "deployment_url": clean_deployment_url or None,
                "video_url": clean_video_url or None,
                "notes": notes.strip() or None,
                "proof_files": stored_files,
            }
        )

        update_registration(
            student["id"],
            {
                "application_status": "Proof Submitted",
            },
        )

        st.success(
            "Proof submitted successfully."
        )

        st.rerun()

    except Exception as error:
        st.error(
            "The proof submission could not be completed."
        )

        st.code(
            str(error)
        )


# ============================================================
# ADMIN DASHBOARD
# ============================================================

def render_admin_dashboard() -> None:
    title_column, logout_column = st.columns(
        [5, 1]
    )

    with title_column:
        st.title(
            "Administration Dashboard"
        )

        st.caption(
            "Manage registrations, submissions, "
            "task documents and stored data."
        )

    with logout_column:
        if st.button(
            "Logout",
            key="admin_logout",
            use_container_width=True,
        ):
            logout_everyone()

            st.session_state.page = "login"

            st.rerun()

    (
        overview_tab,
        proof_tab,
        documents_tab,
        data_management_tab,
    ) = st.tabs(
        [
            "Overview",
            "Proof Review",
            "Task Documents",
            "Data Management",
        ]
    )

    try:
        registrations = get_all_registrations()
        submissions = get_all_proof_submissions()

    except Exception as error:
        st.error(
            "Dashboard data could not be loaded."
        )

        st.code(
            str(error)
        )

        return

    registration_frame = pd.DataFrame(
        registrations
    )

    submission_frame = pd.DataFrame(
        submissions
    )

    with overview_tab:
        render_admin_overview(
            registration_frame
        )

    with proof_tab:
        render_admin_proof_review(
            registration_frame,
            submission_frame,
        )

    with documents_tab:
        render_admin_task_documents()

    with data_management_tab:
        render_admin_data_management(
            registration_frame
        )


# ============================================================
# ADMIN OVERVIEW
# ============================================================

def render_admin_overview(
    registration_frame: pd.DataFrame,
) -> None:
    if registration_frame.empty:
        st.info(
            "No registrations have been received."
        )

        return

    submitted_statuses = [
        "Proof Submitted",
        "Under Scrutiny",
        "Shortlisted",
        "Rejected",
        "Selected",
    ]

    metric_one, metric_two, metric_three, metric_four = (
        st.columns(4)
    )

    metric_one.metric(
        "Total Registrations",
        len(registration_frame),
    )

    metric_two.metric(
        "Proof Submitted",
        int(
            registration_frame[
                "application_status"
            ]
            .isin(
                submitted_statuses
            )
            .sum()
        ),
    )

    metric_three.metric(
        "Pending Proof",
        int(
            (
                registration_frame[
                    "application_status"
                ]
                == "Registered"
            ).sum()
        ),
    )

    metric_four.metric(
        "Selected",
        int(
            (
                registration_frame[
                    "application_status"
                ]
                == "Selected"
            ).sum()
        ),
    )

    filter_one, filter_two, filter_three = st.columns(
        3
    )

    with filter_one:
        selected_club = st.selectbox(
            "Club",
            ["All"] + CLUBS,
        )

    with filter_two:
        selected_year = st.selectbox(
            "Year",
            ["All"] + YEARS,
        )

    with filter_three:
        selected_filter_status = st.selectbox(
            "Status",
            ["All"] + APPLICATION_STATUSES,
        )

    filtered_frame = registration_frame.copy()

    if selected_club != "All":
        filtered_frame = filtered_frame[
            filtered_frame["club"]
            == selected_club
        ]

    if selected_year != "All":
        filtered_frame = filtered_frame[
            filtered_frame["study_year"]
            == selected_year
        ]

    if selected_filter_status != "All":
        filtered_frame = filtered_frame[
            filtered_frame[
                "application_status"
            ]
            == selected_filter_status
        ]

    display_columns = [
        "serial_number",
        "full_name",
        "registration_number",
        "study_year",
        "email",
        "club",
        "application_reference",
        "candidate_number",
        "task_deadline",
        "email_status",
        "application_status",
        "created_at",
    ]

    available_columns = [
        column
        for column in display_columns
        if column in filtered_frame.columns
    ]

    if filtered_frame.empty:
        st.warning(
            "No registrations match the selected filters."
        )

    else:
        st.dataframe(
            filtered_frame[
                available_columns
            ],
            use_container_width=True,
            hide_index=True,
        )

        csv_data = (
            filtered_frame[
                available_columns
            ]
            .to_csv(
                index=False
            )
            .encode(
                "utf-8"
            )
        )

        st.download_button(
            "Download Registration CSV",
            csv_data,
            file_name="10x_devs_registrations.csv",
            mime="text/csv",
        )

    st.divider()

    st.subheader(
        "Update Application Status"
    )

    selected_reference = st.selectbox(
        "Application reference",
        registration_frame[
            "application_reference"
        ].tolist(),
        key="status_reference",
    )

    selected_new_status = st.selectbox(
        "New status",
        APPLICATION_STATUSES,
        key="new_application_status",
    )

    if st.button(
        "Update Status",
        key="update_status",
        type="primary",
    ):
        selected_record = registration_frame[
            registration_frame[
                "application_reference"
            ]
            == selected_reference
        ].iloc[0]

        update_registration(
            selected_record["id"],
            {
                "application_status": selected_new_status,
            },
        )

        st.toast(
            "Application status updated."
        )

        st.rerun()

    st.divider()

    st.subheader(
        "Registration Email Delivery"
    )

    email_reference = st.selectbox(
        "Select application for email retry",
        registration_frame[
            "application_reference"
        ].tolist(),
        key="email_retry_reference",
    )

    email_record = registration_frame[
        registration_frame[
            "application_reference"
        ]
        == email_reference
    ].iloc[0].to_dict()

    st.write(
        f"**Student:** "
        f"{email_record['full_name']}"
    )

    st.write(
        f"**Email:** "
        f"{email_record['email']}"
    )

    st.write(
        f"**Current status:** "
        f"{email_record.get('email_status', 'Pending')}"
    )

    email_error = email_record.get(
        "email_error"
    )

    if value_is_present(
        email_error
    ):
        with st.expander(
            "Previous email error"
        ):
            st.code(
                str(email_error)
            )

    if st.button(
        "Retry Registration Email",
        key="retry_registration_email",
        type="primary",
    ):
        with st.spinner(
            "Sending registration email..."
        ):
            success, message = (
                retry_registration_email(
                    email_record
                )
            )

        if success:
            st.toast(
                message
            )

            st.rerun()

        else:
            st.error(
                "The email could not be sent."
            )

            st.code(
                message
            )


# ============================================================
# ADMIN PROOF REVIEW
# ============================================================

def render_admin_proof_review(
    registration_frame: pd.DataFrame,
    submission_frame: pd.DataFrame,
) -> None:
    if submission_frame.empty:
        st.info(
            "No proof submissions are available."
        )

        return

    if registration_frame.empty:
        st.warning(
            "Registration information is unavailable."
        )

        return

    registration_columns = [
        "id",
        "full_name",
        "registration_number",
        "study_year",
        "club",
        "application_reference",
        "candidate_number",
        "application_status",
    ]

    combined_frame = submission_frame.merge(
        registration_frame[
            registration_columns
        ],
        left_on="registration_id",
        right_on="id",
        how="left",
        suffixes=(
            "_submission",
            "_student",
        ),
    )

    st.dataframe(
        combined_frame[
            [
                "full_name",
                "registration_number",
                "study_year",
                "club",
                "application_reference",
                "submitted_at",
                "application_status",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

    references = (
        combined_frame[
            "application_reference"
        ]
        .dropna()
        .tolist()
    )

    if not references:
        st.warning(
            "No valid proof submission references are available."
        )

        return

    selected_reference = st.selectbox(
        "Select submission",
        references,
        key="selected_proof_reference",
    )

    selected_record = combined_frame[
        combined_frame[
            "application_reference"
        ]
        == selected_reference
    ].iloc[0]

    st.subheader(
        str(
            selected_record[
                "full_name"
            ]
        )
    )

    st.write(
        f"**Registration number:** "
        f"{selected_record['registration_number']}"
    )

    st.write(
        f"**Club:** "
        f"{selected_record['club']}"
    )

    st.write(
        f"**Year:** "
        f"{selected_record['study_year']}"
    )

    st.write(
        f"**Application reference:** "
        f"{selected_record['application_reference']}"
    )

    github_url = selected_record.get(
        "github_url"
    )

    deployment_url = selected_record.get(
        "deployment_url"
    )

    video_url = selected_record.get(
        "video_url"
    )

    if value_is_present(
        github_url
    ):
        st.link_button(
            "Open GitHub Repository",
            str(github_url),
        )

    if value_is_present(
        deployment_url
    ):
        st.link_button(
            "Open Deployment",
            str(deployment_url),
        )

    if value_is_present(
        video_url
    ):
        st.link_button(
            "Open Demonstration Video",
            str(video_url),
        )

    notes = selected_record.get(
        "notes"
    )

    st.write(
        str(notes)
        if value_is_present(notes)
        else "No work summary was provided."
    )

    proof_files = selected_record.get(
        "proof_files",
        [],
    )

    if isinstance(
        proof_files,
        str,
    ):
        try:
            proof_files = json.loads(
                proof_files
            )

        except json.JSONDecodeError:
            proof_files = []

    if not isinstance(
        proof_files,
        list,
    ):
        proof_files = []

    for proof_file in proof_files:
        if not isinstance(
            proof_file,
            dict,
        ):
            continue

        storage_path = str(
            proof_file.get(
                "path",
                "",
            )
        ).strip()

        if not storage_path:
            continue

        try:
            temporary_url = (
                create_temporary_file_url(
                    bucket_name="proof-submissions",
                    storage_path=storage_path,
                    expiry_seconds=600,
                )
            )

            if temporary_url:
                st.link_button(
                    (
                        "Open "
                        + str(
                            proof_file.get(
                                "name",
                                "Proof file",
                            )
                        )
                    ),
                    temporary_url,
                )

        except Exception as error:
            st.warning(
                "A proof file could not be opened."
            )

            st.code(
                str(error)
            )


# ============================================================
# ADMIN TASK DOCUMENTS
# ============================================================

def render_admin_task_documents() -> None:
    st.info(
        "Upload one fixed DOCX document for each academic year. "
        "Deleting a document prevents registrations for that year "
        "until another document is uploaded."
    )

    for study_year in YEARS:
        st.subheader(
            f"{study_year} Task Document"
        )

        filename = TASK_DOCUMENTS[
            study_year
        ]

        current_document = load_task_document(
            study_year
        )

        if current_document:
            st.success(
                f"{filename} is currently available."
            )

            download_column, delete_column = st.columns(
                2
            )

            with download_column:
                st.download_button(
                    "Download Current Document",
                    current_document,
                    file_name=filename,
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "wordprocessingml.document"
                    ),
                    key=f"download_{study_year}",
                    use_container_width=True,
                )

            with delete_column:
                delete_confirmation = st.checkbox(
                    "Confirm document deletion",
                    key=f"confirm_delete_{study_year}",
                )

                if st.button(
                    "Delete Current Document",
                    key=f"delete_{study_year}",
                    use_container_width=True,
                ):
                    if not delete_confirmation:
                        st.error(
                            "Confirm deletion before continuing."
                        )

                    else:
                        try:
                            delete_storage_file(
                                bucket_name="task-documents",
                                storage_path=filename,
                            )

                            st.toast(
                                f"{study_year} document deleted."
                            )

                            st.rerun()

                        except Exception as error:
                            st.error(
                                "The document could not be deleted."
                            )

                            st.code(
                                str(error)
                            )

        else:
            st.warning(
                "No document is currently uploaded."
            )

        uploaded_document = st.file_uploader(
            "Upload or replace Word document",
            type=["docx"],
            key=f"upload_{study_year}",
        )

        if st.button(
            f"Save {study_year} Document",
            key=f"save_{study_year}",
            type="primary",
        ):
            if uploaded_document is None:
                st.error(
                    "Select a DOCX file first."
                )

            else:
                try:
                    upload_storage_file(
                        bucket_name="task-documents",
                        storage_path=filename,
                        file_bytes=(
                            uploaded_document.getvalue()
                        ),
                        content_type=(
                            "application/vnd.openxmlformats-officedocument."
                            "wordprocessingml.document"
                        ),
                        replace_existing=True,
                    )

                    st.toast(
                        f"{study_year} document saved."
                    )

                    st.rerun()

                except Exception as error:
                    st.error(
                        "The document could not be saved."
                    )

                    st.code(
                        str(error)
                    )

        st.divider()


# ============================================================
# ADMIN DATA MANAGEMENT
# ============================================================

def render_admin_data_management(
    registration_frame: pd.DataFrame,
) -> None:
    st.markdown(
        (
            '<div class="danger-notice">'
            "<strong>Permanent data deletion</strong><br>"
            "Deleting a registration removes the student account, "
            "its proof-submission entry and its uploaded proof files. "
            "Deleted data cannot be restored through this portal."
            "</div>"
        ),
        unsafe_allow_html=True,
    )

    if registration_frame.empty:
        st.info(
            "There are no registration entries to delete."
        )

        return

    st.subheader(
        "Delete One Registration"
    )

    selection_options: dict[str, str] = {}

    for _, row in registration_frame.iterrows():
        display_label = (
            f"{row['application_reference']} | "
            f"{row['registration_number']} | "
            f"{row['full_name']}"
        )

        selection_options[
            display_label
        ] = str(
            row["id"]
        )

    selected_label = st.selectbox(
        "Select student registration",
        list(
            selection_options.keys()
        ),
        key="delete_student_selection",
    )

    selected_registration_id = (
        selection_options[
            selected_label
        ]
    )

    selected_rows = registration_frame[
        registration_frame["id"].astype(str)
        == selected_registration_id
    ]

    if selected_rows.empty:
        st.error(
            "The selected registration could not be found."
        )

        return

    selected_row = selected_rows.iloc[0]

    detail_column_one, detail_column_two = st.columns(
        2
    )

    with detail_column_one:
        st.write(
            f"**Student name:** "
            f"{selected_row['full_name']}"
        )

        st.write(
            f"**Registration number:** "
            f"{selected_row['registration_number']}"
        )

        st.write(
            f"**Email:** "
            f"{selected_row['email']}"
        )

    with detail_column_two:
        st.write(
            f"**Application reference:** "
            f"{selected_row['application_reference']}"
        )

        st.write(
            f"**Club:** "
            f"{selected_row['club']}"
        )

        st.write(
            f"**Status:** "
            f"{selected_row['application_status']}"
        )

    expected_confirmation = str(
        selected_row[
            "registration_number"
        ]
    )

    typed_confirmation = st.text_input(
        (
            "Type the registration number to confirm deletion: "
            f"{expected_confirmation}"
        ),
        key="single_delete_confirmation",
    )

    confirm_single_delete = st.checkbox(
        "I understand that this deletion is permanent.",
        key="single_delete_checkbox",
    )

    single_delete_enabled = (
        confirm_single_delete
        and typed_confirmation.strip().upper()
        == expected_confirmation.strip().upper()
    )

    if st.button(
        "Delete Selected Registration",
        key="delete_selected_registration",
        disabled=not single_delete_enabled,
        use_container_width=True,
    ):
        try:
            with st.spinner(
                "Deleting registration and related data..."
            ):
                result = (
                    delete_registration_and_related_data(
                        selected_registration_id
                    )
                )

            if result[
                "proof_files_failed"
            ] > 0:
                st.warning(
                    f"{result['proof_files_failed']} proof file(s) "
                    "could not be deleted from Storage. "
                    "The database entry was deleted."
                )

            st.toast(
                "The selected registration was permanently deleted."
            )

            st.rerun()

        except Exception as error:
            st.error(
                "The selected registration could not be deleted."
            )

            st.code(
                str(error)
            )

    st.divider()

    with st.expander(
        "Delete All Registration Data"
    ):
        st.warning(
            "This deletes every student registration, every "
            "proof-submission entry and every uploaded proof file. "
            "The official 2nd-year and 3rd-year task documents remain."
        )

        st.write(
            f"**Current registration count:** "
            f"{len(registration_frame)}"
        )

        all_confirmation = st.text_input(
            "Type DELETE ALL 10X DATA exactly",
            key="delete_all_confirmation",
        )

        confirm_all_delete = st.checkbox(
            (
                "I understand that all student registration "
                "and submission data will be permanently deleted."
            ),
            key="delete_all_checkbox",
        )

        delete_all_enabled = (
            confirm_all_delete
            and all_confirmation.strip()
            == "DELETE ALL 10X DATA"
        )

        if st.button(
            "Delete All Registration Data",
            key="delete_all_registration_data",
            disabled=not delete_all_enabled,
            use_container_width=True,
        ):
            try:
                with st.spinner(
                    "Deleting all registration data..."
                ):
                    result = (
                        delete_all_registration_data()
                    )

                if result[
                    "registrations_failed"
                ] > 0:
                    st.warning(
                        f"{result['registrations_failed']} "
                        "registration(s) could not be deleted."
                    )

                if result[
                    "proof_files_failed"
                ] > 0:
                    st.warning(
                        f"{result['proof_files_failed']} proof "
                        "file(s) could not be deleted from Storage."
                    )

                st.toast(
                    "Registration data deletion completed."
                )

                st.rerun()

            except Exception as error:
                st.error(
                    "All registration data could not be deleted."
                )

                st.code(
                    str(error)
                )


# ============================================================
# LOGO QUERY-PARAMETER HANDLER
# ============================================================

if st.query_params.get(
    "home"
) == "1":
    logout_everyone()

    st.session_state.page = "landing"

    st.query_params.clear()

    st.rerun()


# ============================================================
# APPLICATION ROUTER
# ============================================================

render_sidebar()

if not configuration_is_valid():
    st.stop()


if st.session_state.admin_authenticated:
    render_admin_dashboard()


elif st.session_state.student_authenticated:
    render_student_dashboard()


elif st.session_state.page == "landing":
    render_landing_page()


elif st.session_state.page == "register":
    render_registration_page()


else:
    render_login_page()
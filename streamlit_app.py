from __future__ import annotations

import hmac
import json
import mimetypes
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from textwrap import dedent
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

from core.auth import hash_password, verify_password
from core.constants import (
    ALLOWED_PROOF_EXTENSIONS,
    APPLICATION_STATUSES,
    CLUBS,
    EVALUATION_CRITERIA,
    MANDATORY_TASKS,
    MAX_PROOF_FILES,
    MAX_TOTAL_PROOF_SIZE,
    SECOND_YEAR_TASKS,
    TASK_DOCUMENTS,
    THIRD_YEAR_TASKS,
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
    update_proof_submission,
    update_registration,
    upload_storage_file,
)
from core.email_service import (
    email_is_configured,
    send_offer_letter_email,
    send_registration_email,
    send_status_email,
    send_submission_under_scrutiny_email,
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
# LOAD CUSTOM CSS
# ============================================================

CSS_PATH = Path("assets/style.css")

if CSS_PATH.exists():
    st.html(
        f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>"
    )


# ============================================================
# CONFIGURATION
# ============================================================

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
        if not str(st.secrets.get(setting, "")).strip()
    ]

    if missing_settings:
        st.error("Application configuration is incomplete.")
        st.write("Missing settings: " + ", ".join(missing_settings))
        return False

    return True


# ============================================================
# SESSION STATE
# ============================================================

SESSION_DEFAULTS = {
    "page": "landing",
    "student_authenticated": False,
    "admin_authenticated": False,
    "student_registration_number": None,
}


for session_key, default_value in SESSION_DEFAULTS.items():
    if session_key not in st.session_state:
        st.session_state[session_key] = default_value


# ============================================================
# GENERAL HELPERS
# ============================================================

def render_html(html_content: str) -> None:
    """
    Render HTML directly without Markdown parsing.
    """

    st.html(
        dedent(html_content).strip()
    )


def normalize_registration_number(value: str) -> str:
    return value.strip().upper().replace(" ", "")


def normalize_name(value: str) -> str:
    return " ".join(value.strip().split())


def is_valid_email(value: str) -> bool:
    value = value.strip()

    return (
        "@" in value
        and "." in value.split("@")[-1]
    )


def is_valid_url(value: str) -> bool:
    if not value.strip():
        return True

    parsed_url = urlparse(value.strip())

    return (
        parsed_url.scheme in {"http", "https"}
        and bool(parsed_url.netloc)
    )


def value_is_present(value: object) -> bool:
    if value is None:
        return False

    try:
        if pd.isna(value):
            return False
    except (TypeError, ValueError):
        pass

    return bool(str(value).strip())


def parse_json_list(value: object) -> list:
    if isinstance(value, list):
        return value

    if isinstance(value, str):
        try:
            decoded = json.loads(value)

            if isinstance(decoded, list):
                return decoded
        except json.JSONDecodeError:
            return []

    return []


def parse_json_dict(value: object) -> dict:
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


def is_reserved_admin_value(value: str) -> bool:
    normalized_value = value.strip().casefold()

    configured_admin = str(
        st.secrets.get("ADMIN_USERNAME", "admin")
    ).strip().casefold()

    return normalized_value in {
        "admin",
        "administrator",
        configured_admin,
    }


def safe_widget_key(value: str) -> str:
    return re.sub(
        r"[^a-zA-Z0-9]+",
        "_",
        value,
    ).strip("_").lower()


def clean_filename(filename: str) -> str:
    return (
        Path(filename)
        .name
        .replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
    )


def allowed_specific_tasks(student: dict) -> list[str]:
    study_year = str(student["study_year"])
    club = str(student["club"])

    if study_year == "2nd Year":
        return list(SECOND_YEAR_TASKS)

    if study_year == "3rd Year":
        return list(
            THIRD_YEAR_TASKS.get(club, [])
        )

    return []


def mandatory_task_for_student(student: dict) -> str:
    return MANDATORY_TASKS.get(
        str(student["study_year"]),
        "Mandatory Portfolio",
    )


def load_task_document(study_year: str) -> bytes | None:
    try:
        return download_storage_file(
            bucket_name="task-documents",
            storage_path=TASK_DOCUMENTS[study_year],
        )
    except Exception:
        return None


def logout_everyone() -> None:
    st.session_state.student_authenticated = False
    st.session_state.admin_authenticated = False
    st.session_state.student_registration_number = None


def open_public_page(page_name: str) -> None:
    logout_everyone()
    st.session_state.page = page_name
    st.rerun()


# ============================================================
# EMAIL TRACKING
# ============================================================

def record_registration_email_result(
    registration_id: str,
    success: bool,
    message_id: str | None = None,
    error_message: str | None = None,
) -> None:
    if success:
        values = {
            "email_status": "Sent",
            "email_error": None,
            "email_message_id": message_id,
        }
    else:
        values = {
            "email_status": "Failed",
            "email_error": str(
                error_message or "Unknown registration email error"
            )[:1000],
            "email_message_id": None,
        }

    update_registration(registration_id, values)


def record_submission_email_result(
    registration_id: str,
    success: bool,
    message_id: str | None = None,
    error_message: str | None = None,
) -> None:
    if success:
        values = {
            "submission_email_status": "Sent",
            "submission_email_sent_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "submission_email_error": None,
            "submission_email_message_id": message_id,
        }
    else:
        values = {
            "submission_email_status": "Failed",
            "submission_email_sent_at": None,
            "submission_email_error": str(
                error_message or "Unknown submission email error"
            )[:1000],
            "submission_email_message_id": None,
        }

    update_registration(registration_id, values)


def record_status_email_result(
    student: dict,
    success: bool,
    message_id: str | None = None,
    error_message: str | None = None,
) -> None:
    if success:
        values = {
            "status_email_status": "Sent",
            "status_email_sent_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "status_email_error": None,
            "status_email_message_id": message_id,
        }
    else:
        values = {
            "status_email_status": "Failed",
            "status_email_sent_at": None,
            "status_email_error": str(
                error_message or "Unknown status email error"
            )[:1000],
            "status_email_message_id": None,
        }

    update_registration(
        str(student["id"]),
        values,
    )


def record_offer_email_result(
    student: dict,
    success: bool,
    message_id: str | None = None,
    error_message: str | None = None,
) -> None:
    if success:
        values = {
            "offer_email_status": "Sent",
            "offer_email_sent_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "offer_email_error": None,
            "offer_email_message_id": message_id,
        }
    else:
        values = {
            "offer_email_status": "Failed",
            "offer_email_sent_at": None,
            "offer_email_error": str(
                error_message or "Unknown offer email error"
            )[:1000],
            "offer_email_message_id": None,
        }

    update_registration(
        str(student["id"]),
        values,
    )


def retry_registration_email(
    student: dict,
) -> tuple[bool, str]:
    task_document = load_task_document(
        str(student["study_year"])
    )

    if task_document is None:
        return False, "The task document is unavailable."

    try:
        message_id = send_registration_email(
            student,
            task_document,
        )

        record_registration_email_result(
            str(student["id"]),
            True,
            message_id=message_id,
        )

        return True, "Registration email sent successfully."

    except Exception as error:
        try:
            record_registration_email_result(
                str(student["id"]),
                False,
                error_message=str(error),
            )
        except Exception:
            pass

        return False, str(error)


# ============================================================
# SIDEBAR
# ============================================================

def render_sidebar() -> None:
    with st.sidebar:
        render_html(
            """
            <a
                class="sidebar-brand-link"
                href="?home=1"
                target="_self"
                aria-label="Return to the 10x Devs home page"
            >
                <div class="sidebar-logo-box">
                    10x
                </div>

                <div class="sidebar-brand-text">
                    <span>10x</span> Devs
                </div>
            </a>

            <div class="sidebar-subtitle">
                Student Club Registration Portal
            </div>
            """
        )

        if st.button(
            "Register",
            key="navigation_register",
            use_container_width=True,
        ):
            open_public_page("register")

        if st.button(
            "Login",
            key="navigation_login",
            use_container_width=True,
        ):
            open_public_page("login")

        st.divider()

        render_html(
            """
            <div class="sidebar-section-title">
                Technical Clubs
            </div>

            <div class="sidebar-club-list">

                <div class="sidebar-club-item">
                    <div class="sidebar-club-dot"></div>
                    <div class="sidebar-club-name">
                        Computer Vision Club
                    </div>
                </div>

                <div class="sidebar-club-item">
                    <div class="sidebar-club-dot"></div>
                    <div class="sidebar-club-name">
                        Web Development Club
                    </div>
                </div>

                <div class="sidebar-club-item">
                    <div class="sidebar-club-dot"></div>
                    <div class="sidebar-club-name">
                        Machine Learning Club
                    </div>
                </div>

            </div>
            """
        )


# ============================================================
# LANDING PAGE
# ============================================================

def render_landing_page() -> None:
    render_html(
        """
        <div class="landing-page">

            <section class="hero">
                <div class="hero-content">

                    <div class="hero-label">
                        Registration • Projects • Community
                    </div>

                    <h1 class="hero-title">
                        Build at <span>10x.</span>
                    </h1>

                    <p class="hero-description">
                        10x Devs is a student technical community
                        focused on practical learning, collaborative
                        development and industry-oriented projects.
                        The community helps students improve their
                        technical skills by building working
                        applications, contributing to team projects
                        and learning through implementation.
                    </p>

                    <div class="hero-tags">
                        <div class="hero-tag">
                            Practical Development
                        </div>

                        <div class="hero-tag">
                            Team Collaboration
                        </div>

                        <div class="hero-tag">
                            Project-Based Learning
                        </div>

                        <div class="hero-tag">
                            Technical Community
                        </div>
                    </div>

                </div>
            </section>


            <section class="landing-section">

                <div class="section-label">
                    About the Community
                </div>

                <h2 class="section-title">
                    About 10x Devs
                </h2>

                <p class="section-description">
                    10x Devs was officially inaugurated on
                    25 January 2025. It provides students with
                    a structured environment to learn modern
                    technologies, work with peers and convert
                    technical knowledge into practical projects.
                </p>

                <div class="about-grid">

                    <div class="about-card">
                        <div class="about-card-number">01</div>

                        <div class="about-card-title">
                            Learn by Building
                        </div>

                        <p class="about-card-text">
                            Members strengthen their technical
                            knowledge through practical tasks,
                            working applications, demonstrations
                            and project documentation.
                        </p>
                    </div>

                    <div class="about-card">
                        <div class="about-card-number">02</div>

                        <div class="about-card-title">
                            Work as a Team
                        </div>

                        <p class="about-card-text">
                            Students collaborate with club members,
                            share technical resources, review ideas
                            and contribute to projects based on
                            their interests and skills.
                        </p>
                    </div>

                    <div class="about-card">
                        <div class="about-card-number">03</div>

                        <div class="about-card-title">
                            Develop Professionally
                        </div>

                        <p class="about-card-text">
                            The community encourages portfolio
                            development, GitHub usage, deployment,
                            documentation and presentation of
                            completed technical work.
                        </p>
                    </div>

                </div>
            </section>


            <section class="landing-section">

                <div class="section-label">
                    Technical Domains
                </div>

                <h2 class="section-title">
                    Explore Our Clubs
                </h2>

                <p class="section-description">
                    Students register for one technical club based
                    on their primary area of interest. Third-year
                    applicants submit only the tasks associated
                    with their registered club.
                </p>

                <div class="club-grid">

                    <div class="club-card">
                        <div class="club-code">CV CLUB</div>

                        <div class="club-title">
                            Computer Vision Club
                        </div>

                        <p class="club-description">
                            Focuses on image processing, object
                            detection, gesture recognition, video
                            analysis and practical vision-based
                            applications using modern tools.
                        </p>

                        <div class="club-focus">
                            OpenCV • YOLO • Image Processing
                        </div>
                    </div>

                    <div class="club-card">
                        <div class="club-code">WEB CLUB</div>

                        <div class="club-title">
                            Web Development Club
                        </div>

                        <p class="club-description">
                            Focuses on responsive interfaces,
                            backend development, database
                            integration, deployment and complete
                            full-stack application development.
                        </p>

                        <div class="club-focus">
                            Frontend • Backend • Databases
                        </div>
                    </div>

                    <div class="club-card">
                        <div class="club-code">ML CLUB</div>

                        <div class="club-title">
                            Machine Learning Club
                        </div>

                        <p class="club-description">
                            Focuses on machine learning, natural
                            language processing, recommendation
                            systems, data analysis and intelligent
                            application development.
                        </p>

                        <div class="club-focus">
                            Machine Learning • NLP • Data
                        </div>
                    </div>

                </div>
            </section>


            <section class="process-panel">

                <div class="process-heading">
                    Recruitment Process
                </div>

                <div class="process-grid">

                    <div class="process-card">
                        <div class="process-number">Step 01</div>

                        <div class="process-text">
                            Register for one technical club and
                            download the official year-wise task
                            document.
                        </div>
                    </div>

                    <div class="process-card">
                        <div class="process-number">Step 02</div>

                        <div class="process-text">
                            Complete the mandatory portfolio task
                            and at least one eligible specific task.
                        </div>
                    </div>

                    <div class="process-card">
                        <div class="process-number">Step 03</div>

                        <div class="process-text">
                            Submit source links, deployment links,
                            demonstration videos and supporting
                            evidence.
                        </div>
                    </div>

                    <div class="process-card">
                        <div class="process-number">Step 04</div>

                        <div class="process-text">
                            The submission is evaluated and the
                            application status is communicated
                            through the portal and email.
                        </div>
                    </div>

                </div>
            </section>


            <section class="landing-section">

                <div class="section-label">
                    Community Leadership
                </div>

                <h2 class="section-title">
                    Leadership
                </h2>

                <p class="section-description">
                    10x Devs operates with institutional guidance
                    and student coordination to support technical
                    learning, project execution and collaborative
                    development.
                </p>

                <div class="leadership-grid">

                    <div class="leadership-card">
                        <div class="leadership-initials">RK</div>

                        <div>
                            <div class="leadership-role">
                                Inaugurated by
                            </div>

                            <div class="leadership-name">
                                Dr. Ravi Kadiyala
                            </div>

                            <div class="leadership-detail">
                                Principal
                            </div>
                        </div>
                    </div>

                    <div class="leadership-card">
                        <div class="leadership-initials">SB</div>

                        <div>
                            <div class="leadership-role">
                                President
                            </div>

                            <div class="leadership-name">
                                Dr. Ch. Suresh Babu
                            </div>

                            <div class="leadership-detail">
                                HOD, CSE (AI & ML)
                            </div>
                        </div>
                    </div>

                    <div class="leadership-card">
                        <div class="leadership-initials">SC</div>

                        <div>
                            <div class="leadership-role">
                                Secretary
                            </div>

                            <div class="leadership-name">
                                A. Sri Chaitanya
                            </div>

                            <div class="leadership-detail">
                                Ph.D.
                            </div>
                        </div>
                    </div>

                    <div class="leadership-card">
                        <div class="leadership-initials">CV</div>

                        <div>
                            <div class="leadership-role">
                                Coordinator
                            </div>

                            <div class="leadership-name">
                                Chetan Ventrapragada
                            </div>

                            <div class="leadership-detail">
                                Final-Year Student
                            </div>
                        </div>
                    </div>

                </div>
            </section>


            <section class="landing-footer">
                <div>
                    <div class="landing-footer-title">
                        10x Devs Student Club Registration Portal
                    </div>

                    <div class="landing-footer-text">
                        Register, complete the assigned tasks and
                        submit your technical work for evaluation.
                    </div>
                </div>

                <div class="landing-footer-badge">
                    Inaugurated 25 January 2025
                </div>
            </section>

        </div>
        """
    )


# ============================================================
# REGISTRATION
# ============================================================

def render_registration_page() -> None:
    st.title("Create Your Account")

    st.info(
        "Every student must complete the mandatory portfolio task "
        "and at least one specific task. Multiple specific tasks "
        "can be submitted together. Third-year students can submit "
        "only tasks belonging to their registered club."
    )

    with st.form("registration_form"):
        full_name = st.text_input("Full name")

        registration_number = st.text_input(
            "Registration number"
        )

        year_column, email_column = st.columns(2)

        with year_column:
            study_year = st.selectbox(
                "Current academic year",
                YEARS,
            )

        with email_column:
            email = st.text_input("Email address")

        password_column, confirmation_column = st.columns(2)

        with password_column:
            password = st.text_input(
                "Create password",
                type="password",
            )

        with confirmation_column:
            confirm_password = st.text_input(
                "Confirm password",
                type="password",
            )

        club = st.selectbox(
            "Select one club",
            CLUBS,
        )

        declaration = st.checkbox(
            "I confirm that the details are accurate and "
            "understand that my registered club cannot be changed."
        )

        submitted = st.form_submit_button(
            "Create Account",
            type="primary",
            use_container_width=True,
        )

    if not submitted:
        return

    clean_name = normalize_name(full_name)

    clean_registration_number = (
        normalize_registration_number(
            registration_number
        )
    )

    clean_email = email.strip().lower()

    errors: list[str] = []

    if len(clean_name) < 3:
        errors.append("Enter your complete name.")

    if (
        is_reserved_admin_value(clean_name)
        or is_reserved_admin_value(
            clean_registration_number
        )
    ):
        errors.append("Admin-related values are reserved.")

    if len(clean_registration_number) < 5:
        errors.append(
            "Enter a valid registration number."
        )

    if not is_valid_email(clean_email):
        errors.append(
            "Enter a valid email address."
        )

    if len(password) < 8:
        errors.append(
            "Password must contain at least 8 characters."
        )

    if password != confirm_password:
        errors.append("Passwords do not match.")

    if not declaration:
        errors.append("Accept the declaration.")

    if errors:
        for error_message in errors:
            st.error(error_message)

        return

    try:
        duplicate_message = find_duplicate_registration(
            clean_registration_number,
            clean_email,
        )
    except Exception as error:
        st.error("Could not connect to Supabase.")
        st.code(str(error))
        return

    if duplicate_message:
        st.error(duplicate_message)
        return

    task_document = load_task_document(study_year)

    if task_document is None:
        st.error(
            f"The {study_year} task document "
            "has not been uploaded."
        )
        return

    task_deadline = (
        date.today()
        + timedelta(
            days=int(
                st.secrets.get(
                    "TASK_DEADLINE_DAYS",
                    2,
                )
            )
        )
    )

    try:
        student = create_registration(
            {
                "full_name": clean_name,
                "registration_number": (
                    clean_registration_number
                ),
                "study_year": study_year,
                "email": clean_email,
                "password_hash": hash_password(password),
                "club": club,
                "task_deadline": task_deadline.isoformat(),
                "email_status": "Pending",
                "application_status": "Registered",
            }
        )

        if email_is_configured():
            try:
                message_id = send_registration_email(
                    student,
                    task_document,
                )

                record_registration_email_result(
                    str(student["id"]),
                    True,
                    message_id=message_id,
                )
            except Exception as email_error:
                try:
                    record_registration_email_result(
                        str(student["id"]),
                        False,
                        error_message=str(email_error),
                    )
                except Exception:
                    pass

        st.success("Account created successfully.")

        st.write(
            f"**Application reference:** "
            f"{student['application_reference']}"
        )

        st.write(
            f"**Candidate number:** "
            f"{student['candidate_number']}"
        )

        st.write(
            f"**Registered club:** "
            f"{student['club']}"
        )

        st.write(
            f"**Mandatory task:** "
            f"{mandatory_task_for_student(student)}"
        )

        st.warning(
            "Complete the mandatory task and at least one "
            "eligible specific task before the deadline."
        )

        st.download_button(
            label=f"Download {study_year} Task Document",
            data=task_document,
            file_name=TASK_DOCUMENTS[study_year],
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
            use_container_width=True,
        )

    except Exception as error:
        st.error("The account could not be created.")
        st.code(str(error))


# ============================================================
# LOGIN
# ============================================================

def render_login_page() -> None:
    st.title("Login")

    with st.form("login_form"):
        identifier = st.text_input("Account ID")

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

    admin_username = str(
        st.secrets["ADMIN_USERNAME"]
    ).strip()

    admin_password = str(
        st.secrets["ADMIN_PASSWORD"]
    )

    if hmac.compare_digest(
        identifier.strip().casefold(),
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
            st.error("Incorrect credentials.")

        return

    try:
        student = get_student(
            normalize_registration_number(identifier)
        )
    except Exception as error:
        st.error("The login service is unavailable.")
        st.code(str(error))
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
        st.error("Incorrect credentials.")


# ============================================================
# STUDENT DASHBOARD
# ============================================================

def render_student_dashboard() -> None:
    try:
        student = get_student(
            st.session_state.student_registration_number
        )
    except Exception as error:
        st.error("The dashboard could not be loaded.")
        st.code(str(error))
        return

    if not student:
        logout_everyone()
        st.session_state.page = "login"
        st.rerun()

    title_column, logout_column = st.columns([5, 1])

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

    metric_one, metric_two, metric_three = st.columns(3)

    metric_one.metric(
        "Academic Year",
        student["study_year"],
    )

    metric_two.metric(
        "Application Status",
        student["application_status"],
    )

    metric_three.metric(
        "Task Deadline",
        student["task_deadline"],
    )

    st.write(
        f"**Registered club:** {student['club']}"
    )

    st.write(
        f"**Mandatory task:** "
        f"{mandatory_task_for_student(student)}"
    )

    st.info(
        "Task eligibility is taken from your saved registration. "
        "Third-year students cannot submit tasks from another club."
    )

    task_document = load_task_document(
        str(student["study_year"])
    )

    if task_document:
        st.download_button(
            "Download Task Document",
            task_document,
            file_name=TASK_DOCUMENTS[
                student["study_year"]
            ],
            use_container_width=True,
        )

    try:
        submission = get_proof_submission(
            str(student["id"])
        )
    except Exception as error:
        st.error(
            "Submission information could not be loaded."
        )
        st.code(str(error))
        return

    submission_notice = st.session_state.pop(
        "submission_success_notice",
        None,
    )

    if submission_notice:
        st.success(
            "The mandatory task and all selected specific "
            "tasks were submitted successfully."
        )

        st.info(
            "Your application has automatically changed "
            "to Under Scrutiny."
        )

        st.write(
            f"**Specific tasks submitted:** "
            f"{submission_notice['specific_task_count']}"
        )

        if submission_notice["email_sent"]:
            st.success(
                "A submission-success and Under Scrutiny "
                "email was sent to your registered email."
            )
        else:
            st.warning(
                "Your submission was saved successfully, "
                "but the confirmation email could not be sent. "
                "The administrator can send your status later."
            )

    if submission:
        render_existing_submission(
            submission,
            student,
        )
        return

    render_proof_submission_form(student)


def render_existing_submission(
    submission: dict,
    student: dict,
) -> None:
    st.success(
        "Your final proof has already been submitted."
    )

    st.write(
        f"**Current application status:** "
        f"{student['application_status']}"
    )

    if (
        student["application_status"]
        == "Under Scrutiny"
    ):
        st.info(
            "Your submitted work is currently being reviewed "
            "by the evaluation team."
        )

    st.write(
        f"**Mandatory task:** "
        f"{submission.get('mandatory_task_name') or 'Not available'}"
    )

    selected_tasks = parse_json_list(
        submission.get("selected_tasks", [])
    )

    if not selected_tasks:
        old_task = submission.get("selected_task")

        if value_is_present(old_task):
            selected_tasks = [str(old_task)]

    st.markdown("### Submitted Specific Tasks")

    for task_number, task_name in enumerate(
        selected_tasks,
        start=1,
    ):
        st.write(f"{task_number}. {task_name}")

    st.write(
        f"**Total specific tasks submitted:** "
        f"{len(selected_tasks)}"
    )

    st.write(
        f"**Submitted at:** "
        f"{submission.get('submitted_at')}"
    )

    if value_is_present(
        submission.get("evaluation_total")
    ):
        st.info(
            f"Evaluation score: "
            f"{submission['evaluation_total']}/100"
        )


# ============================================================
# STUDENT PROOF SUBMISSION
# ============================================================

def render_proof_submission_form(
    student: dict,
) -> None:
    study_year = str(student["study_year"])
    club = str(student["club"])

    mandatory_task = mandatory_task_for_student(
        student
    )

    eligible_tasks = allowed_specific_tasks(student)

    st.divider()
    st.subheader("Final Proof Submission")

    st.warning(
        "This is a one-time final submission. Include the "
        "mandatory task and every specific task you want evaluated."
    )

    if not eligible_tasks:
        st.error(
            "No eligible specific tasks are configured for "
            "your registered year and club."
        )
        return

    st.markdown("## 1. Mandatory Task")

    st.text_input(
        "Mandatory task",
        value=mandatory_task,
        disabled=True,
    )

    if study_year == "2nd Year":
        portfolio_run_mode = st.selectbox(
            "Mandatory portfolio run mode",
            [
                "Localhost",
                "Public Deployment",
            ],
        )
    else:
        portfolio_run_mode = "Public Deployment"

        st.info(
            "The third-year mandatory full-stack portfolio "
            "must be publicly deployed."
        )

    portfolio_github_url = st.text_input(
        "Mandatory portfolio source or GitHub URL",
        key="mandatory_portfolio_source",
        placeholder=(
            "https://github.com/username/portfolio"
        ),
    )

    portfolio_deployment_url = st.text_input(
        "Mandatory portfolio deployment URL",
        key="mandatory_portfolio_deployment",
        placeholder="https://your-portfolio.example",
    )

    mandatory_files = st.file_uploader(
        (
            "Mandatory-task screenshots, source ZIP "
            "or supporting documents"
        ),
        type=ALLOWED_PROOF_EXTENSIONS,
        accept_multiple_files=True,
        key="mandatory_task_files",
    )

    st.markdown("## 2. Specific Tasks")

    if study_year == "3rd Year":
        st.success(
            f"You are registered for {club}. "
            f"Only {club} tasks are displayed and accepted."
        )
    else:
        st.info(
            "Select one or more tasks from the common "
            "second-year task list."
        )

    selected_tasks = st.multiselect(
        "Select all specific tasks you completed",
        eligible_tasks,
        help=(
            "Select at least one task. Multiple tasks may "
            "be submitted in the same final submission."
        ),
    )

    task_inputs: dict[str, dict] = {}

    for task_number, task_name in enumerate(
        selected_tasks,
        start=1,
    ):
        task_key = safe_widget_key(task_name)

        with st.expander(
            f"Specific Task {task_number}: {task_name}",
            expanded=True,
        ):
            source_url = st.text_input(
                "Source or GitHub URL",
                key=f"specific_source_{task_key}",
                placeholder=(
                    "https://github.com/username/project"
                ),
            )

            deployment_url = st.text_input(
                "Deployment URL",
                key=f"specific_deployment_{task_key}",
                help=(
                    "Optional for webcam-based, "
                    "hardware-dependent or localhost projects."
                ),
            )

            demo_url = st.text_input(
                "Demonstration video URL",
                key=f"specific_demo_{task_key}",
                placeholder=(
                    "YouTube, Google Drive or another "
                    "accessible link"
                ),
            )

            task_notes = st.text_area(
                "Brief explanation of this task",
                key=f"specific_notes_{task_key}",
                placeholder=(
                    "Explain completed features, technologies "
                    "used and how to run the project."
                ),
            )

            task_files = st.file_uploader(
                (
                    "Screenshots, ZIP or supporting files "
                    "for this task"
                ),
                type=ALLOWED_PROOF_EXTENSIONS,
                accept_multiple_files=True,
                key=f"specific_files_{task_key}",
            )

            task_inputs[task_name] = {
                "source_url": source_url.strip(),
                "deployment_url": deployment_url.strip(),
                "demo_url": demo_url.strip(),
                "notes": task_notes.strip(),
                "files": task_files or [],
            }

    st.markdown("## 3. Final Confirmation")

    readme_confirmed = st.checkbox(
        "I confirm that setup instructions or README files "
        "are provided for my submitted work."
    )

    mandatory_confirmed = st.checkbox(
        "I confirm that I completed the mandatory task."
    )

    club_task_confirmed = st.checkbox(
        "I confirm that every selected specific task is permitted "
        "for my registered year and club."
    )

    final_confirmation = st.checkbox(
        "I understand that this submission is final and cannot "
        "be edited after submission."
    )

    submit_button = st.button(
        "Submit All Proof Permanently",
        type="primary",
        use_container_width=True,
    )

    if not submit_button:
        return

    errors: list[str] = []

    try:
        latest_student = get_student(
            str(student["registration_number"])
        )
    except Exception as error:
        st.error(
            "Your registration could not be verified."
        )
        st.code(str(error))
        return

    if not latest_student:
        st.error(
            "Your registration could not be verified."
        )
        return

    latest_allowed_tasks = allowed_specific_tasks(
        latest_student
    )

    invalid_tasks = [
        task_name
        for task_name in selected_tasks
        if task_name not in latest_allowed_tasks
    ]

    if invalid_tasks:
        errors.append(
            "One or more selected tasks are not permitted "
            "for your registered year and club."
        )

    if not selected_tasks:
        errors.append(
            "Select at least one specific task."
        )

    mandatory_files = mandatory_files or []

    if study_year == "3rd Year":
        if not portfolio_github_url.strip():
            errors.append(
                "The mandatory portfolio GitHub or source URL "
                "is required for third-year students."
            )

        if not portfolio_deployment_url.strip():
            errors.append(
                "Public deployment of the mandatory full-stack "
                "portfolio is required."
            )
    else:
        if (
            not portfolio_github_url.strip()
            and not mandatory_files
        ):
            errors.append(
                "Provide the mandatory portfolio source URL "
                "or upload supporting files."
            )

        if (
            portfolio_run_mode == "Public Deployment"
            and not portfolio_deployment_url.strip()
        ):
            errors.append(
                "Enter the mandatory portfolio deployment URL."
            )

    for field_name, field_value in {
        "mandatory portfolio source URL": (
            portfolio_github_url.strip()
        ),
        "mandatory portfolio deployment URL": (
            portfolio_deployment_url.strip()
        ),
    }.items():
        if (
            field_value
            and not is_valid_url(field_value)
        ):
            errors.append(
                f"Enter a valid {field_name}."
            )

    all_uploaded_files = list(mandatory_files)

    for task_name in selected_tasks:
        evidence = task_inputs[task_name]

        if (
            not evidence["source_url"]
            and not evidence["files"]
        ):
            errors.append(
                "Provide a source URL or supporting files "
                f"for '{task_name}'."
            )

        for field_name in [
            "source_url",
            "deployment_url",
            "demo_url",
        ]:
            field_value = evidence[field_name]

            if (
                field_value
                and not is_valid_url(field_value)
            ):
                errors.append(
                    "Enter a valid "
                    f"{field_name.replace('_', ' ')} "
                    f"for '{task_name}'."
                )

        if study_year == "3rd Year":
            if not evidence["source_url"]:
                errors.append(
                    "GitHub or source URL is required "
                    f"for '{task_name}'."
                )

            if not evidence["demo_url"]:
                errors.append(
                    "A demonstration video is required "
                    f"for '{task_name}'."
                )

            if not evidence["files"]:
                errors.append(
                    "Upload at least one screenshot or supporting "
                    f"file for '{task_name}'."
                )

        all_uploaded_files.extend(
            evidence["files"]
        )

    if not mandatory_files:
        errors.append(
            "Upload at least one screenshot, ZIP or supporting "
            "file for the mandatory task."
        )

    if not readme_confirmed:
        errors.append(
            "Confirm the README or setup-instruction requirement."
        )

    if not mandatory_confirmed:
        errors.append(
            "Confirm completion of the mandatory task."
        )

    if not club_task_confirmed:
        errors.append(
            "Confirm the selected-task eligibility."
        )

    if not final_confirmation:
        errors.append(
            "Accept the final submission confirmation."
        )

    if len(all_uploaded_files) > MAX_PROOF_FILES:
        errors.append(
            f"Upload no more than {MAX_PROOF_FILES} files "
            "across the complete submission."
        )

    total_uploaded_size = sum(
        uploaded_file.size
        for uploaded_file in all_uploaded_files
    )

    maximum_size_mb = (
        MAX_TOTAL_PROOF_SIZE
        // (1024 * 1024)
    )

    if total_uploaded_size > MAX_TOTAL_PROOF_SIZE:
        errors.append(
            "The combined uploaded-file size must not exceed "
            f"{maximum_size_mb} MB."
        )

    if errors:
        for error_message in errors:
            st.error(error_message)

        return

    try:
        existing_submission = get_proof_submission(
            str(student["id"])
        )
    except Exception as error:
        st.error(
            "The existing submission status could not be checked."
        )
        st.code(str(error))
        return

    if existing_submission:
        st.error(
            "Proof has already been submitted."
        )
        return

    stored_mandatory_files: list[dict] = []
    specific_task_evidence: list[dict] = []
    uploaded_storage_paths: list[str] = []

    try:
        for file_number, uploaded_file in enumerate(
            mandatory_files,
            start=1,
        ):
            filename = clean_filename(
                uploaded_file.name
            )

            storage_path = (
                f"{student['application_reference']}/"
                f"mandatory/"
                f"{file_number}_{filename}"
            )

            content_type = (
                uploaded_file.type
                or mimetypes.guess_type(filename)[0]
                or "application/octet-stream"
            )

            upload_storage_file(
                bucket_name="proof-submissions",
                storage_path=storage_path,
                file_bytes=uploaded_file.getvalue(),
                content_type=content_type,
                replace_existing=False,
            )

            uploaded_storage_paths.append(
                storage_path
            )

            stored_mandatory_files.append(
                {
                    "name": filename,
                    "path": storage_path,
                    "category": "mandatory_task",
                    "content_type": content_type,
                    "size": uploaded_file.size,
                }
            )

        for task_number, task_name in enumerate(
            selected_tasks,
            start=1,
        ):
            evidence = task_inputs[task_name]
            task_key = safe_widget_key(task_name)

            stored_task_files: list[dict] = []

            for file_number, uploaded_file in enumerate(
                evidence["files"],
                start=1,
            ):
                filename = clean_filename(
                    uploaded_file.name
                )

                storage_path = (
                    f"{student['application_reference']}/"
                    f"specific_tasks/"
                    f"{task_number}_{task_key}/"
                    f"{file_number}_{filename}"
                )

                content_type = (
                    uploaded_file.type
                    or mimetypes.guess_type(filename)[0]
                    or "application/octet-stream"
                )

                upload_storage_file(
                    bucket_name="proof-submissions",
                    storage_path=storage_path,
                    file_bytes=uploaded_file.getvalue(),
                    content_type=content_type,
                    replace_existing=False,
                )

                uploaded_storage_paths.append(
                    storage_path
                )

                stored_task_files.append(
                    {
                        "name": filename,
                        "path": storage_path,
                        "category": "specific_task",
                        "task_name": task_name,
                        "content_type": content_type,
                        "size": uploaded_file.size,
                    }
                )

            specific_task_evidence.append(
                {
                    "task_name": task_name,
                    "source_url": (
                        evidence["source_url"]
                        or None
                    ),
                    "deployment_url": (
                        evidence["deployment_url"]
                        or None
                    ),
                    "demo_url": (
                        evidence["demo_url"]
                        or None
                    ),
                    "notes": (
                        evidence["notes"]
                        or None
                    ),
                    "files": stored_task_files,
                }
            )

        create_proof_submission(
            {
                "registration_id": student["id"],
                "mandatory_task_name": mandatory_task,
                "mandatory_task_confirmed": True,
                "selected_task": selected_tasks[0],
                "selected_tasks": selected_tasks,
                "specific_task_evidence": (
                    specific_task_evidence
                ),
                "portfolio_run_mode": (
                    portfolio_run_mode
                ),
                "portfolio_github_url": (
                    portfolio_github_url.strip()
                    or None
                ),
                "portfolio_deployment_url": (
                    portfolio_deployment_url.strip()
                    or None
                ),
                "readme_confirmed": (
                    readme_confirmed
                ),
                "proof_files": (
                    stored_mandatory_files
                ),

                # Compatibility columns
                "github_url": (
                    portfolio_github_url.strip()
                    or None
                ),
                "deployment_url": (
                    portfolio_deployment_url.strip()
                    or None
                ),
                "video_url": None,
                "demo_url": None,
                "notes": (
                    "Mandatory task plus "
                    f"{len(selected_tasks)} "
                    "specific task(s) submitted."
                ),
            }
        )

        update_registration(
            str(student["id"]),
            {
                "application_status": (
                    "Under Scrutiny"
                ),
            },
        )

    except Exception as error:
        for storage_path in uploaded_storage_paths:
            try:
                delete_storage_file(
                    bucket_name="proof-submissions",
                    storage_path=storage_path,
                )
            except Exception:
                pass

        st.error(
            "The submission could not be completed."
        )
        st.code(str(error))
        return

    automatic_email_sent = False
    automatic_email_error = None

    if email_is_configured():
        try:
            updated_student = dict(student)

            updated_student[
                "application_status"
            ] = "Under Scrutiny"

            message_id = (
                send_submission_under_scrutiny_email(
                    student=updated_student,
                    mandatory_task=mandatory_task,
                    selected_tasks=selected_tasks,
                )
            )

            try:
                record_submission_email_result(
                    registration_id=str(
                        student["id"]
                    ),
                    success=True,
                    message_id=message_id,
                )
            except Exception:
                pass

            automatic_email_sent = True

        except Exception as email_error:
            automatic_email_error = str(
                email_error
            )

            try:
                record_submission_email_result(
                    registration_id=str(
                        student["id"]
                    ),
                    success=False,
                    error_message=(
                        automatic_email_error
                    ),
                )
            except Exception:
                pass
    else:
        automatic_email_error = (
            "Gmail SMTP is not configured."
        )

        try:
            record_submission_email_result(
                registration_id=str(
                    student["id"]
                ),
                success=False,
                error_message=automatic_email_error,
            )
        except Exception:
            pass

    st.session_state.submission_success_notice = {
        "email_sent": automatic_email_sent,
        "email_error": automatic_email_error,
        "specific_task_count": len(
            selected_tasks
        ),
    }

    st.rerun()


# ============================================================
# ADMIN DASHBOARD
# ============================================================

def render_admin_dashboard() -> None:
    title_column, logout_column = st.columns(
        [5, 1]
    )

    with title_column:
        st.title("Administration Dashboard")

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
        status_email_tab,
        offer_letter_tab,
        document_tab,
        data_tab,
    ) = st.tabs(
        [
            "Overview",
            "Proof Review",
            "Status Emails",
            "Offer Letters",
            "Task Documents",
            "Data Management",
        ]
    )

    try:
        registrations = get_all_registrations()
        submissions = get_all_proof_submissions()
    except Exception as error:
        st.error(
            "Admin data could not be loaded."
        )
        st.code(str(error))
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

    with status_email_tab:
        render_admin_status_emails(
            registration_frame
        )

    with offer_letter_tab:
        render_admin_offer_letters(
            registration_frame
        )

    with document_tab:
        render_admin_task_documents()

    with data_tab:
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
            "No registrations are available."
        )
        return

    metric_one, metric_two, metric_three, metric_four = (
        st.columns(4)
    )

    metric_one.metric(
        "Registrations",
        len(registration_frame),
    )

    metric_two.metric(
        "Under Scrutiny",
        int(
            (
                registration_frame[
                    "application_status"
                ]
                == "Under Scrutiny"
            ).sum()
        ),
    )

    metric_three.metric(
        "Shortlisted",
        int(
            (
                registration_frame[
                    "application_status"
                ]
                == "Shortlisted"
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

    filter_one, filter_two, filter_three = (
        st.columns(3)
    )

    with filter_one:
        club_filter = st.selectbox(
            "Club filter",
            ["All", *CLUBS],
            key="overview_club_filter",
        )

    with filter_two:
        year_filter = st.selectbox(
            "Year filter",
            ["All", *YEARS],
            key="overview_year_filter",
        )

    with filter_three:
        status_filter = st.selectbox(
            "Status filter",
            ["All", *APPLICATION_STATUSES],
            key="overview_status_filter",
        )

    filtered_frame = registration_frame.copy()

    if club_filter != "All":
        filtered_frame = filtered_frame[
            filtered_frame["club"]
            == club_filter
        ]

    if year_filter != "All":
        filtered_frame = filtered_frame[
            filtered_frame["study_year"]
            == year_filter
        ]

    if status_filter != "All":
        filtered_frame = filtered_frame[
            filtered_frame["application_status"]
            == status_filter
        ]

    st.dataframe(
        filtered_frame,
        use_container_width=True,
        hide_index=True,
    )

    st.download_button(
        "Download Registration CSV",
        filtered_frame.to_csv(
            index=False
        ).encode("utf-8"),
        file_name="10x_devs_registrations.csv",
        mime="text/csv",
        use_container_width=True,
    )

    st.divider()
    st.subheader("Update Application Status")

    application_reference = st.selectbox(
        "Application to update",
        registration_frame[
            "application_reference"
        ].tolist(),
        key="overview_status_reference",
    )

    selected_application = registration_frame[
        registration_frame[
            "application_reference"
        ]
        == application_reference
    ].iloc[0]

    current_status = str(
        selected_application[
            "application_status"
        ]
    )

    current_status_index = (
        APPLICATION_STATUSES.index(
            current_status
        )
        if current_status in APPLICATION_STATUSES
        else 0
    )

    new_status = st.selectbox(
        "New application status",
        APPLICATION_STATUSES,
        index=current_status_index,
        key="overview_new_status",
    )

    if st.button(
        "Update Status",
        type="primary",
        key="overview_update_status",
        use_container_width=True,
    ):
        try:
            update_registration(
                str(selected_application["id"]),
                {
                    "application_status": (
                        new_status
                    ),
                },
            )

            st.success(
                "Application status updated."
            )
            st.rerun()

        except Exception as error:
            st.error(
                "Application status could not be updated."
            )
            st.code(str(error))

    st.divider()
    st.subheader("Registration Email Delivery")

    email_reference = st.selectbox(
        "Application for email retry",
        registration_frame[
            "application_reference"
        ].tolist(),
        key="registration_email_reference",
    )

    email_record = registration_frame[
        registration_frame[
            "application_reference"
        ]
        == email_reference
    ].iloc[0].to_dict()

    information_one, information_two = st.columns(2)

    with information_one:
        st.write(
            f"**Student:** "
            f"{email_record['full_name']}"
        )

        st.write(
            f"**Email:** "
            f"{email_record['email']}"
        )

    with information_two:
        st.write(
            f"**Current email status:** "
            f"{email_record.get('email_status', 'Pending')}"
        )

        st.write(
            f"**Application reference:** "
            f"{email_record['application_reference']}"
        )

    if value_is_present(
        email_record.get("email_error")
    ):
        with st.expander(
            "Previous registration-email error"
        ):
            st.code(
                str(email_record["email_error"])
            )

    if st.button(
        "Retry Registration Email",
        type="primary",
        key="retry_registration_email",
        use_container_width=True,
    ):
        success, message = retry_registration_email(
            email_record
        )

        if success:
            st.success(message)
            st.rerun()
        else:
            st.error(message)


# ============================================================
# ADMIN PROOF REVIEW
# ============================================================

def render_admin_proof_review(
    registration_frame: pd.DataFrame,
    submission_frame: pd.DataFrame,
) -> None:
    if (
        registration_frame.empty
        or submission_frame.empty
    ):
        st.info(
            "No proof submissions are available."
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

    if "selected_tasks" not in combined_frame.columns:
        combined_frame["selected_tasks"] = [
            []
            for _ in range(len(combined_frame))
        ]

    combined_frame[
        "specific_task_count"
    ] = combined_frame[
        "selected_tasks"
    ].apply(
        lambda value: len(
            parse_json_list(value)
        )
    )

    review_columns = [
        "full_name",
        "registration_number",
        "study_year",
        "club",
        "mandatory_task_name",
        "specific_task_count",
        "evaluation_total",
        "application_status",
    ]

    visible_columns = [
        column
        for column in review_columns
        if column in combined_frame.columns
    ]

    st.dataframe(
        combined_frame[visible_columns],
        use_container_width=True,
        hide_index=True,
    )

    available_references = combined_frame[
        "application_reference"
    ].dropna().tolist()

    if not available_references:
        st.warning(
            "No valid application references are available."
        )
        return

    selected_reference = st.selectbox(
        "Select proof submission",
        available_references,
        key="proof_review_reference",
    )

    selected_record = combined_frame[
        combined_frame[
            "application_reference"
        ]
        == selected_reference
    ].iloc[0]

    st.subheader(
        str(selected_record["full_name"])
    )

    detail_one, detail_two = st.columns(2)

    with detail_one:
        st.write(
            f"**Registration number:** "
            f"{selected_record['registration_number']}"
        )

        st.write(
            f"**Academic year:** "
            f"{selected_record['study_year']}"
        )

        st.write(
            f"**Registered club:** "
            f"{selected_record['club']}"
        )

    with detail_two:
        st.write(
            f"**Application reference:** "
            f"{selected_record['application_reference']}"
        )

        st.write(
            f"**Candidate number:** "
            f"{selected_record['candidate_number']}"
        )

        st.write(
            f"**Current status:** "
            f"{selected_record['application_status']}"
        )

    st.markdown("### Mandatory Task")

    st.write(
        str(
            selected_record.get(
                "mandatory_task_name"
            )
            or "Not available"
        )
    )

    portfolio_source = selected_record.get(
        "portfolio_github_url"
    )

    portfolio_deployment = selected_record.get(
        "portfolio_deployment_url"
    )

    portfolio_column_one, portfolio_column_two = (
        st.columns(2)
    )

    with portfolio_column_one:
        if value_is_present(portfolio_source):
            st.link_button(
                "Open Mandatory Portfolio Source",
                str(portfolio_source),
                use_container_width=True,
            )

    with portfolio_column_two:
        if value_is_present(
            portfolio_deployment
        ):
            st.link_button(
                "Open Mandatory Portfolio Deployment",
                str(portfolio_deployment),
                use_container_width=True,
            )

    mandatory_files = parse_json_list(
        selected_record.get("proof_files", [])
    )

    if mandatory_files:
        st.markdown(
            "#### Mandatory Task Evidence"
        )

    for file_record in mandatory_files:
        if not isinstance(file_record, dict):
            continue

        storage_path = str(
            file_record.get("path", "")
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
                    "Open "
                    + str(
                        file_record.get(
                            "name",
                            "Mandatory evidence",
                        )
                    ),
                    temporary_url,
                )
        except Exception as error:
            st.warning(
                "A mandatory-task file could not be opened."
            )
            st.code(str(error))

    st.markdown("### Specific Tasks")

    selected_tasks = parse_json_list(
        selected_record.get(
            "selected_tasks",
            [],
        )
    )

    if not selected_tasks:
        old_task = selected_record.get(
            "selected_task"
        )

        if value_is_present(old_task):
            selected_tasks = [str(old_task)]

    if (
        selected_record["study_year"]
        == "2nd Year"
    ):
        permitted_tasks = SECOND_YEAR_TASKS
    else:
        permitted_tasks = THIRD_YEAR_TASKS.get(
            selected_record["club"],
            [],
        )

    invalid_tasks = [
        task_name
        for task_name in selected_tasks
        if task_name not in permitted_tasks
    ]

    if invalid_tasks:
        st.error(
            "This submission contains one or more tasks "
            "that are not permitted for the registered club."
        )

        st.write(
            "**Invalid tasks:** "
            + ", ".join(invalid_tasks)
        )
    else:
        st.success(
            "All submitted tasks are valid for the student's "
            "registered year and club."
        )

    st.write(
        f"**Total specific tasks submitted:** "
        f"{len(selected_tasks)}"
    )

    task_evidence = parse_json_list(
        selected_record.get(
            "specific_task_evidence",
            [],
        )
    )

    if task_evidence:
        for task_number, task_record in enumerate(
            task_evidence,
            start=1,
        ):
            if not isinstance(task_record, dict):
                continue

            task_name = str(
                task_record.get(
                    "task_name",
                    f"Task {task_number}",
                )
            )

            with st.expander(
                f"Task {task_number}: {task_name}",
                expanded=True,
            ):
                source_url = task_record.get(
                    "source_url"
                )

                deployment_url = task_record.get(
                    "deployment_url"
                )

                demo_url = task_record.get(
                    "demo_url"
                )

                task_notes = task_record.get(
                    "notes"
                )

                link_columns = st.columns(3)

                with link_columns[0]:
                    if value_is_present(source_url):
                        st.link_button(
                            "Open Source",
                            str(source_url),
                            use_container_width=True,
                        )

                with link_columns[1]:
                    if value_is_present(
                        deployment_url
                    ):
                        st.link_button(
                            "Open Deployment",
                            str(deployment_url),
                            use_container_width=True,
                        )

                with link_columns[2]:
                    if value_is_present(demo_url):
                        st.link_button(
                            "Open Demo Video",
                            str(demo_url),
                            use_container_width=True,
                        )

                if value_is_present(task_notes):
                    st.markdown(
                        "**Student explanation**"
                    )
                    st.write(str(task_notes))

                task_files = parse_json_list(
                    task_record.get("files", [])
                )

                for file_record in task_files:
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
                        temporary_url = (
                            create_temporary_file_url(
                                bucket_name=(
                                    "proof-submissions"
                                ),
                                storage_path=storage_path,
                                expiry_seconds=600,
                            )
                        )

                        if temporary_url:
                            st.link_button(
                                "Open "
                                + str(
                                    file_record.get(
                                        "name",
                                        "Evidence file",
                                    )
                                ),
                                temporary_url,
                            )
                    except Exception as error:
                        st.warning(
                            "A specific-task evidence file "
                            "could not be opened."
                        )
                        st.code(str(error))
    else:
        for task_number, task_name in enumerate(
            selected_tasks,
            start=1,
        ):
            st.write(
                f"{task_number}. {task_name}"
            )

    render_submission_evaluation(
        selected_record
    )


# ============================================================
# ADMIN EVALUATION
# ============================================================

def render_submission_evaluation(
    selected_record: pd.Series,
) -> None:
    study_year = str(
        selected_record["study_year"]
    )

    criteria = EVALUATION_CRITERIA.get(
        study_year,
        {},
    )

    if not criteria:
        st.warning(
            "No evaluation criteria are configured "
            "for this year."
        )
        return

    submission_id = str(
        selected_record["id_submission"]
    )

    registration_id = str(
        selected_record["id_student"]
    )

    existing_scores = parse_json_dict(
        selected_record.get(
            "evaluation_scores",
            {},
        )
    )

    st.divider()
    st.subheader(
        f"{study_year} Evaluation"
    )

    with st.form(
        f"evaluation_form_{submission_id}"
    ):
        score_values: dict[str, float] = {}

        for criterion_name, maximum_score in (
            criteria.items()
        ):
            current_score = float(
                existing_scores.get(
                    criterion_name,
                    0,
                )
            )

            score_values[
                criterion_name
            ] = st.number_input(
                (
                    f"{criterion_name} "
                    f"(0–{maximum_score})"
                ),
                min_value=0.0,
                max_value=float(maximum_score),
                value=min(
                    current_score,
                    float(maximum_score),
                ),
                step=1.0,
                key=(
                    f"evaluation_score_"
                    f"{submission_id}_"
                    f"{safe_widget_key(criterion_name)}"
                ),
            )

        evaluation_notes = st.text_area(
            "Evaluation notes",
            value=str(
                selected_record.get(
                    "evaluation_notes",
                    "",
                )
                or ""
            ),
            key=f"evaluation_notes_{submission_id}",
        )

        current_status = str(
            selected_record.get(
                "application_status",
                "Under Scrutiny",
            )
        )

        status_index = (
            APPLICATION_STATUSES.index(
                current_status
            )
            if current_status in APPLICATION_STATUSES
            else 0
        )

        evaluation_status = st.selectbox(
            "Application decision/status",
            APPLICATION_STATUSES,
            index=status_index,
            key=f"evaluation_status_{submission_id}",
        )

        total_score = sum(
            score_values.values()
        )

        st.metric(
            "Calculated Total",
            f"{total_score:.0f}/100",
        )

        save_evaluation = (
            st.form_submit_button(
                "Save Evaluation",
                type="primary",
                use_container_width=True,
            )
        )

    if save_evaluation:
        try:
            update_proof_submission(
                submission_id,
                {
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
                    "evaluated_at": datetime.now(
                        timezone.utc
                    ).isoformat(),
                },
            )

            update_registration(
                registration_id,
                {
                    "application_status": (
                        evaluation_status
                    ),
                },
            )

            st.success(
                "Evaluation and application status were saved."
            )
            st.rerun()

        except Exception as error:
            st.error(
                "The evaluation could not be saved."
            )
            st.code(str(error))


# ============================================================
# ADMIN STATUS EMAILS
# ============================================================

def render_admin_status_emails(
    registration_frame: pd.DataFrame,
) -> None:
    st.info(
        "Send the current application status to one student "
        "or send each selected student their respective status."
    )

    if registration_frame.empty:
        st.info(
            "No registrations are available."
        )
        return

    if not email_is_configured():
        st.error(
            "Gmail SMTP is not configured."
        )
        return

    st.subheader("Send to One Student")

    student_options: dict[str, int] = {}

    for row_index, row in (
        registration_frame.iterrows()
    ):
        label = (
            f"{row['application_reference']} | "
            f"{row['full_name']} | "
            f"{row['application_status']}"
        )

        student_options[label] = row_index

    selected_label = st.selectbox(
        "Select student",
        list(student_options.keys()),
        key="single_status_student",
    )

    selected_student = registration_frame.loc[
        student_options[selected_label]
    ].to_dict()

    information_one, information_two = st.columns(2)

    with information_one:
        st.write(
            f"**Student:** "
            f"{selected_student['full_name']}"
        )

        st.write(
            f"**Email:** "
            f"{selected_student['email']}"
        )

    with information_two:
        st.write(
            f"**Current status:** "
            f"{selected_student['application_status']}"
        )

        st.write(
            f"**Previous email result:** "
            f"{selected_student.get('status_email_status', 'Not Sent')}"
        )

    if value_is_present(
        selected_student.get(
            "status_email_error"
        )
    ):
        with st.expander(
            "Previous status-email error"
        ):
            st.code(
                str(
                    selected_student[
                        "status_email_error"
                    ]
                )
            )

    if st.button(
        "Send Current Status",
        type="primary",
        key="send_single_status_email",
        use_container_width=True,
    ):
        try:
            message_id = send_status_email(
                selected_student
            )

            record_status_email_result(
                selected_student,
                True,
                message_id=message_id,
            )

            st.success("Status email sent.")
            st.rerun()

        except Exception as error:
            try:
                record_status_email_result(
                    selected_student,
                    False,
                    error_message=str(error),
                )
            except Exception:
                pass

            st.error(str(error))

    st.divider()
    st.subheader("Bulk Status Emails")

    audience_mode = st.radio(
        "Recipients",
        [
            "All Students",
            "Filter by Status",
        ],
        horizontal=True,
        key="status_email_audience",
    )

    recipients = registration_frame.copy()

    if audience_mode == "Filter by Status":
        selected_statuses = st.multiselect(
            "Application statuses",
            APPLICATION_STATUSES,
            key="status_email_filters",
        )

        if selected_statuses:
            recipients = recipients[
                recipients[
                    "application_status"
                ].isin(selected_statuses)
            ]
        else:
            recipients = recipients.iloc[0:0]

    st.write(
        f"**Recipients:** {len(recipients)}"
    )

    if not recipients.empty:
        preview_columns = [
            "full_name",
            "email",
            "study_year",
            "club",
            "application_status",
            "status_email_status",
        ]

        visible_columns = [
            column
            for column in preview_columns
            if column in recipients.columns
        ]

        st.dataframe(
            recipients[visible_columns],
            use_container_width=True,
            hide_index=True,
        )

    confirmation_text = st.text_input(
        "Type SEND STATUS EMAILS",
        key="bulk_status_confirmation",
    )

    confirmation_checkbox = st.checkbox(
        "Each selected student should receive "
        "their own current application status.",
        key="bulk_status_checkbox",
    )

    bulk_enabled = (
        not recipients.empty
        and confirmation_checkbox
        and confirmation_text.strip()
        == "SEND STATUS EMAILS"
    )

    if st.button(
        "Send Status Emails",
        type="primary",
        disabled=not bulk_enabled,
        key="send_bulk_status",
        use_container_width=True,
    ):
        recipient_records = recipients.to_dict(
            orient="records"
        )

        sent_count = 0
        failed_count = 0
        failed_records: list[dict] = []

        progress_bar = st.progress(0)
        progress_text = st.empty()

        total_recipients = len(
            recipient_records
        )

        for recipient_number, recipient in enumerate(
            recipient_records,
            start=1,
        ):
            progress_text.write(
                f"Sending {recipient_number} of "
                f"{total_recipients}: "
                f"{recipient['full_name']}"
            )

            try:
                message_id = send_status_email(
                    recipient
                )

                record_status_email_result(
                    recipient,
                    True,
                    message_id=message_id,
                )

                sent_count += 1

            except Exception as error:
                try:
                    record_status_email_result(
                        recipient,
                        False,
                        error_message=str(error),
                    )
                except Exception:
                    pass

                failed_count += 1

                failed_records.append(
                    {
                        "Student": recipient.get(
                            "full_name"
                        ),
                        "Email": recipient.get(
                            "email"
                        ),
                        "Error": str(error),
                    }
                )

            progress_bar.progress(
                recipient_number
                / total_recipients
            )

        progress_text.empty()

        st.success(
            f"Completed. Sent: {sent_count}; "
            f"Failed: {failed_count}."
        )

        if failed_records:
            st.dataframe(
                pd.DataFrame(failed_records),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.rerun()


# ============================================================
# ADMIN OFFER LETTERS
# ============================================================

def render_admin_offer_letters(
    registration_frame: pd.DataFrame,
) -> None:
    st.info(
        "Offer letters can be sent only to students whose "
        "current application status is Selected."
    )

    if registration_frame.empty:
        st.info(
            "No registrations are available."
        )
        return

    if not email_is_configured():
        st.error(
            "Gmail SMTP is not configured."
        )
        return

    selected_students = registration_frame[
        registration_frame[
            "application_status"
        ]
        == "Selected"
    ].copy()

    if selected_students.empty:
        st.warning(
            "No students currently have the Selected status."
        )
        return

    metric_one, metric_two, metric_three = (
        st.columns(3)
    )

    metric_one.metric(
        "Selected Students",
        len(selected_students),
    )

    if (
        "offer_email_status"
        in selected_students.columns
    ):
        sent_count = int(
            (
                selected_students[
                    "offer_email_status"
                ]
                == "Sent"
            ).sum()
        )

        failed_count = int(
            (
                selected_students[
                    "offer_email_status"
                ]
                == "Failed"
            ).sum()
        )
    else:
        sent_count = 0
        failed_count = 0

    metric_two.metric(
        "Offer Letters Sent",
        sent_count,
    )

    metric_three.metric(
        "Offer Letters Failed",
        failed_count,
    )

    st.subheader(
        "Send to One Selected Student"
    )

    student_options: dict[str, int] = {}

    for row_index, row in (
        selected_students.iterrows()
    ):
        label = (
            f"{row['application_reference']} | "
            f"{row['full_name']} | "
            f"{row['club']}"
        )

        student_options[label] = row_index

    selected_label = st.selectbox(
        "Select selected student",
        list(student_options.keys()),
        key="single_offer_student",
    )

    selected_student = selected_students.loc[
        student_options[selected_label]
    ].to_dict()

    information_one, information_two = st.columns(2)

    with information_one:
        st.write(
            f"**Student:** "
            f"{selected_student['full_name']}"
        )

        st.write(
            f"**Email:** "
            f"{selected_student['email']}"
        )

        st.write(
            f"**Registration number:** "
            f"{selected_student['registration_number']}"
        )

    with information_two:
        st.write(
            f"**Club:** "
            f"{selected_student['club']}"
        )

        st.write(
            f"**Application status:** "
            f"{selected_student['application_status']}"
        )

        st.write(
            f"**Previous offer status:** "
            f"{selected_student.get('offer_email_status', 'Not Sent')}"
        )

    if value_is_present(
        selected_student.get(
            "offer_email_error"
        )
    ):
        with st.expander(
            "Previous offer-letter error"
        ):
            st.code(
                str(
                    selected_student[
                        "offer_email_error"
                    ]
                )
            )

    confirm_single_offer = st.checkbox(
        "I confirm that this selected student should "
        "receive the official offer letter.",
        key="confirm_single_offer",
    )

    if st.button(
        "Send Offer Letter",
        type="primary",
        disabled=not confirm_single_offer,
        key="send_single_offer",
        use_container_width=True,
    ):
        try:
            message_id = send_offer_letter_email(
                selected_student
            )

            record_offer_email_result(
                selected_student,
                True,
                message_id=message_id,
            )

            st.success("Offer letter sent.")
            st.rerun()

        except Exception as error:
            try:
                record_offer_email_result(
                    selected_student,
                    False,
                    error_message=str(error),
                )
            except Exception:
                pass

            st.error(str(error))

    st.divider()
    st.subheader("Bulk Offer Letters")

    club_filter = st.selectbox(
        "Filter by club",
        [
            "All Selected Students",
            *CLUBS,
        ],
        key="offer_club_filter",
    )

    recipients = selected_students.copy()

    if club_filter != "All Selected Students":
        recipients = recipients[
            recipients["club"]
            == club_filter
        ]

    include_already_sent = st.checkbox(
        "Include students who already received an offer letter",
        key="include_sent_offers",
    )

    if (
        not include_already_sent
        and "offer_email_status"
        in recipients.columns
    ):
        recipients = recipients[
            recipients["offer_email_status"]
            != "Sent"
        ]

    st.write(
        f"**Offer-letter recipients:** "
        f"{len(recipients)}"
    )

    if not recipients.empty:
        preview_columns = [
            "full_name",
            "registration_number",
            "email",
            "study_year",
            "club",
            "application_reference",
            "offer_email_status",
        ]

        visible_columns = [
            column
            for column in preview_columns
            if column in recipients.columns
        ]

        st.dataframe(
            recipients[visible_columns],
            use_container_width=True,
            hide_index=True,
        )

    confirmation_text = st.text_input(
        "Type SEND OFFER LETTERS",
        key="bulk_offer_confirmation",
    )

    confirmation_checkbox = st.checkbox(
        "I confirm that every listed student has been selected.",
        key="bulk_offer_checkbox",
    )

    bulk_enabled = (
        not recipients.empty
        and confirmation_checkbox
        and confirmation_text.strip()
        == "SEND OFFER LETTERS"
    )

    if st.button(
        "Send Offer Letters",
        type="primary",
        disabled=not bulk_enabled,
        key="send_bulk_offers",
        use_container_width=True,
    ):
        recipient_records = recipients.to_dict(
            orient="records"
        )

        sent_count = 0
        failed_count = 0
        failed_records: list[dict] = []

        progress_bar = st.progress(0)
        progress_text = st.empty()

        total_recipients = len(
            recipient_records
        )

        for recipient_number, recipient in enumerate(
            recipient_records,
            start=1,
        ):
            progress_text.write(
                f"Sending {recipient_number} of "
                f"{total_recipients}: "
                f"{recipient['full_name']}"
            )

            try:
                message_id = (
                    send_offer_letter_email(
                        recipient
                    )
                )

                record_offer_email_result(
                    recipient,
                    True,
                    message_id=message_id,
                )

                sent_count += 1

            except Exception as error:
                try:
                    record_offer_email_result(
                        recipient,
                        False,
                        error_message=str(error),
                    )
                except Exception:
                    pass

                failed_count += 1

                failed_records.append(
                    {
                        "Student": recipient.get(
                            "full_name"
                        ),
                        "Email": recipient.get(
                            "email"
                        ),
                        "Club": recipient.get(
                            "club"
                        ),
                        "Error": str(error),
                    }
                )

            progress_bar.progress(
                recipient_number
                / total_recipients
            )

        progress_text.empty()

        st.success(
            f"Completed. Sent: {sent_count}; "
            f"Failed: {failed_count}."
        )

        if failed_records:
            st.dataframe(
                pd.DataFrame(failed_records),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.rerun()


# ============================================================
# ADMIN TASK DOCUMENTS
# ============================================================

def render_admin_task_documents() -> None:
    st.info(
        "Upload one fixed DOCX task document "
        "for each academic year."
    )

    for study_year in YEARS:
        st.subheader(
            f"{study_year} Task Document"
        )

        filename = TASK_DOCUMENTS[study_year]

        current_document = load_task_document(
            study_year
        )

        if current_document:
            st.success(
                f"{filename} is available."
            )

            st.download_button(
                "Download Current Document",
                current_document,
                file_name=filename,
                key=(
                    f"download_task_doc_"
                    f"{study_year}"
                ),
                use_container_width=True,
            )

            delete_confirmation = st.checkbox(
                "Confirm document deletion",
                key=(
                    f"confirm_task_doc_delete_"
                    f"{study_year}"
                ),
            )

            if st.button(
                "Delete Current Document",
                key=(
                    f"delete_task_doc_"
                    f"{study_year}"
                ),
                use_container_width=True,
            ):
                if not delete_confirmation:
                    st.error(
                        "Confirm deletion first."
                    )
                else:
                    try:
                        delete_storage_file(
                            bucket_name="task-documents",
                            storage_path=filename,
                        )

                        st.success(
                            "Task document deleted."
                        )
                        st.rerun()

                    except Exception as error:
                        st.error(
                            "The task document could not be deleted."
                        )
                        st.code(str(error))
        else:
            st.warning(
                "No document is currently uploaded."
            )

        uploaded_document = st.file_uploader(
            "Upload or replace DOCX",
            type=["docx"],
            key=(
                f"upload_task_doc_"
                f"{study_year}"
            ),
        )

        if st.button(
            f"Save {study_year} Document",
            key=(
                f"save_task_doc_"
                f"{study_year}"
            ),
            type="primary",
            use_container_width=True,
        ):
            if uploaded_document is None:
                st.error(
                    "Choose a DOCX file."
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

                    st.success(
                        "Task document saved."
                    )
                    st.rerun()

                except Exception as error:
                    st.error(
                        "The task document could not be saved."
                    )
                    st.code(str(error))

        st.divider()


# ============================================================
# ADMIN DATA MANAGEMENT
# ============================================================

def render_admin_data_management(
    registration_frame: pd.DataFrame,
) -> None:
    st.warning(
        "Deleted registrations, proof submissions and uploaded "
        "proof files cannot be restored through the portal."
    )

    if registration_frame.empty:
        st.info(
            "No registrations are available."
        )
        return

    options: dict[str, str] = {}

    for _, row in registration_frame.iterrows():
        label = (
            f"{row['application_reference']} | "
            f"{row['registration_number']} | "
            f"{row['full_name']}"
        )

        options[label] = str(row["id"])

    selected_label = st.selectbox(
        "Registration to delete",
        list(options.keys()),
        key="delete_registration_selection",
    )

    registration_id = options[selected_label]

    selected_row = registration_frame[
        registration_frame[
            "id"
        ].astype(str)
        == registration_id
    ].iloc[0]

    st.write(
        f"**Student:** "
        f"{selected_row['full_name']}"
    )

    st.write(
        f"**Registration number:** "
        f"{selected_row['registration_number']}"
    )

    st.write(
        f"**Club:** "
        f"{selected_row['club']}"
    )

    expected_text = str(
        selected_row[
            "registration_number"
        ]
    )

    typed_confirmation = st.text_input(
        f"Type {expected_text} to confirm",
        key="delete_registration_text",
    )

    permanent_confirmation = st.checkbox(
        "I understand that this deletion is permanent.",
        key="delete_registration_checkbox",
    )

    deletion_enabled = (
        permanent_confirmation
        and typed_confirmation.strip().upper()
        == expected_text.strip().upper()
    )

    if st.button(
        "Delete Selected Registration",
        disabled=not deletion_enabled,
        key="delete_selected_registration",
        use_container_width=True,
    ):
        try:
            result = (
                delete_registration_and_related_data(
                    registration_id
                )
            )

            if result["proof_files_failed"] > 0:
                st.warning(
                    "The database record was deleted, but some "
                    "Storage files could not be removed."
                )

            st.success(
                "Registration and associated submission "
                "data were deleted."
            )
            st.rerun()

        except Exception as error:
            st.error(
                "The registration could not be deleted."
            )
            st.code(str(error))

    st.divider()

    with st.expander(
        "Delete All Registration Data"
    ):
        st.error(
            "This action deletes every registration and proof "
            "submission. Task documents are not deleted."
        )

        typed_all = st.text_input(
            "Type DELETE ALL 10X DATA",
            key="delete_all_text",
        )

        confirm_all = st.checkbox(
            "I understand that every registration and submission "
            "will be permanently deleted.",
            key="delete_all_checkbox",
        )

        delete_all_enabled = (
            confirm_all
            and typed_all
            == "DELETE ALL 10X DATA"
        )

        if st.button(
            "Delete All Registration Data",
            disabled=not delete_all_enabled,
            key="delete_all_data",
            use_container_width=True,
        ):
            try:
                result = (
                    delete_all_registration_data()
                )

                st.success(
                    "Deletion process completed. "
                    f"Deleted: "
                    f"{result['registrations_deleted']}; "
                    f"Failed: "
                    f"{result['registrations_failed']}."
                )
                st.rerun()

            except Exception as error:
                st.error(
                    "The bulk deletion process failed."
                )
                st.code(str(error))


# ============================================================
# ROUTER
# ============================================================

if st.query_params.get("home") == "1":
    logout_everyone()
    st.session_state.page = "landing"
    st.query_params.clear()
    st.rerun()


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
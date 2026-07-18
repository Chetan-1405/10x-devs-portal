from __future__ import annotations

import html
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import (
    formataddr,
    make_msgid,
)
from typing import Any

import streamlit as st

from core.constants import (
    STATUS_EMAIL_MESSAGES,
    TASK_DOCUMENTS,
)


DOCX_SUBTYPE = (
    "vnd.openxmlformats-officedocument."
    "wordprocessingml.document"
)


def get_gmail_settings(
) -> tuple[str, str, str, str]:
    gmail_address = str(
        st.secrets.get(
            "GMAIL_ADDRESS",
            "",
        )
    ).strip()

    gmail_app_password = str(
        st.secrets.get(
            "GMAIL_APP_PASSWORD",
            "",
        )
    ).replace(
        " ",
        "",
    ).strip()

    sender_name = str(
        st.secrets.get(
            "GMAIL_SENDER_NAME",
            "10x Devs",
        )
    ).strip()

    if not sender_name:
        sender_name = "10x Devs"

    contact_email = str(
        st.secrets.get(
            "CLUB_CONTACT_EMAIL",
            gmail_address,
        )
    ).strip()

    if not contact_email:
        contact_email = gmail_address

    return (
        gmail_address,
        gmail_app_password,
        sender_name,
        contact_email,
    )


def email_is_configured() -> bool:
    (
        gmail_address,
        gmail_app_password,
        _,
        _,
    ) = get_gmail_settings()

    return bool(
        gmail_address
        and gmail_app_password
    )


def create_base_message(
    subject: str,
    recipient: str,
) -> EmailMessage:
    (
        gmail_address,
        _,
        sender_name,
        contact_email,
    ) = get_gmail_settings()

    message = EmailMessage()

    message[
        "Subject"
    ] = subject

    message[
        "From"
    ] = formataddr(
        (
            sender_name,
            gmail_address,
        )
    )

    message[
        "To"
    ] = recipient

    message[
        "Reply-To"
    ] = contact_email

    message[
        "Message-ID"
    ] = make_msgid(
        domain="gmail.com"
    )

    return message


def send_message(
    message: EmailMessage,
) -> str:
    (
        gmail_address,
        gmail_app_password,
        _,
        _,
    ) = get_gmail_settings()

    if not gmail_address:
        raise RuntimeError(
            "GMAIL_ADDRESS is missing "
            "from Streamlit Secrets."
        )

    if not gmail_app_password:
        raise RuntimeError(
            "GMAIL_APP_PASSWORD is missing "
            "from Streamlit Secrets."
        )

    try:
        with smtplib.SMTP_SSL(
            "smtp.gmail.com",
            465,
            timeout=30,
            context=(
                ssl.create_default_context()
            ),
        ) as smtp_server:
            smtp_server.login(
                gmail_address,
                gmail_app_password,
            )

            refused_recipients = (
                smtp_server.send_message(
                    message
                )
            )

    except smtplib.SMTPAuthenticationError as error:
        raise RuntimeError(
            "Gmail authentication failed. "
            "Use the Google App Password."
        ) from error

    except smtplib.SMTPRecipientsRefused as error:
        raise RuntimeError(
            "Gmail rejected the recipient "
            "email address."
        ) from error

    except smtplib.SMTPException as error:
        raise RuntimeError(
            f"Gmail SMTP error: {error}"
        ) from error

    except OSError as error:
        raise RuntimeError(
            "Could not connect to Gmail SMTP: "
            f"{error}"
        ) from error

    if refused_recipients:
        raise RuntimeError(
            "Gmail refused one or more "
            f"recipients: {refused_recipients}"
        )

    return str(
        message[
            "Message-ID"
        ]
    ).strip(
        "<>"
    )


def send_registration_email(
    student: dict[str, Any],
    task_document: bytes,
) -> str:
    study_year = str(
        student[
            "study_year"
        ]
    )

    message = create_base_message(
        subject=(
            "10x Devs Registration | "
            f"{student['application_reference']}"
        ),
        recipient=str(
            student[
                "email"
            ]
        ),
    )

    message.set_content(
        f"Dear {student['full_name']},\n\n"
        "Your 10x Devs registration was completed "
        "successfully.\n\n"
        f"Club: {student['club']}\n"
        f"Year: {student['study_year']}\n"
        f"Application reference: "
        f"{student['application_reference']}\n"
        f"Candidate number: "
        f"{student['candidate_number']}\n"
        f"Task deadline: "
        f"{student['task_deadline']}\n\n"
        "You must complete the mandatory portfolio task "
        "and at least one eligible specific task. You may "
        "submit multiple specific tasks together in the "
        "same final submission.\n\n"
        "Third-year students may submit only tasks belonging "
        "to their registered club.\n\n"
        "The official task document is attached.\n\n"
        "Regards,\n"
        "10x Devs"
    )

    message.add_attachment(
        task_document,
        maintype="application",
        subtype=DOCX_SUBTYPE,
        filename=TASK_DOCUMENTS[
            study_year
        ],
    )

    return send_message(
        message
    )


def send_submission_under_scrutiny_email(
    student: dict[str, Any],
    mandatory_task: str,
    selected_tasks: list[str],
) -> str:
    message = create_base_message(
        subject=(
            "10x Devs Task Submission "
            "Successful | Under Scrutiny"
        ),
        recipient=str(
            student[
                "email"
            ]
        ),
    )

    task_lines = "\n".join(
        (
            f"{index}. {task_name}"
            for index, task_name
            in enumerate(
                selected_tasks,
                start=1,
            )
        )
    )

    message.set_content(
        f"Dear {student['full_name']},\n\n"
        "Your task submission was completed "
        "successfully.\n\n"
        f"Application reference: "
        f"{student['application_reference']}\n"
        f"Candidate number: "
        f"{student['candidate_number']}\n"
        f"Academic year: "
        f"{student['study_year']}\n"
        f"Registered club: "
        f"{student['club']}\n"
        "Current application status: "
        "Under Scrutiny\n\n"
        f"Mandatory task received:\n"
        f"{mandatory_task}\n\n"
        f"Specific tasks received:\n"
        f"{task_lines}\n\n"
        "Your links, files and submitted evidence "
        "are now available to the evaluation team. "
        "The result will be communicated through "
        "the portal and email.\n\n"
        "Regards,\n"
        "10x Devs"
    )

    safe_task_items = "".join(
        (
            "<li>"
            + html.escape(
                task_name
            )
            + "</li>"
        )
        for task_name
        in selected_tasks
    )

    message.add_alternative(
        f"""
        <div style="
            max-width:700px;
            margin:auto;
            font-family:Arial,sans-serif;
            color:#172033;
            line-height:1.65;
        ">
            <div style="
                background:#151d2e;
                padding:24px 28px;
                color:#ffffff;
                font-size:28px;
                font-weight:800;
            ">
                <span style="color:#ef4052;">
                    10x
                </span>
                Devs
            </div>

            <div style="
                border:1px solid #e2e6ec;
                padding:28px;
            ">
                <h2 style="color:#c9182b;">
                    Task Submission Successful
                </h2>

                <p>
                    Dear
                    {html.escape(str(student['full_name']))},
                </p>

                <p>
                    Your final submission was successful.
                    Your application is now
                    <strong>Under Scrutiny</strong>.
                </p>

                <p>
                    <strong>Application reference:</strong>
                    {html.escape(str(student['application_reference']))}
                </p>

                <p>
                    <strong>Candidate number:</strong>
                    {html.escape(str(student['candidate_number']))}
                </p>

                <p>
                    <strong>Registered club:</strong>
                    {html.escape(str(student['club']))}
                </p>

                <h3>Mandatory task received</h3>

                <p>
                    {html.escape(mandatory_task)}
                </p>

                <h3>Specific tasks received</h3>

                <ol>
                    {safe_task_items}
                </ol>

                <p>
                    Your submitted evidence is now available
                    to the evaluation team.
                </p>
            </div>
        </div>
        """,
        subtype="html",
    )

    return send_message(
        message
    )


def send_status_email(
    student: dict[str, Any],
) -> str:
    application_status = str(
        student.get(
            "application_status",
            "Registered",
        )
    )

    status_message = (
        STATUS_EMAIL_MESSAGES.get(
            application_status,
            (
                "Your application status "
                "has been updated."
            ),
        )
    )

    message = create_base_message(
        subject=(
            "10x Devs Application Status | "
            f"{application_status}"
        ),
        recipient=str(
            student[
                "email"
            ]
        ),
    )

    message.set_content(
        f"Dear {student['full_name']},\n\n"
        f"Application reference: "
        f"{student['application_reference']}\n"
        f"Candidate number: "
        f"{student['candidate_number']}\n"
        f"Club: {student['club']}\n"
        f"Current status: "
        f"{application_status}\n\n"
        f"{status_message}\n\n"
        "Regards,\n"
        "10x Devs"
    )

    message.add_alternative(
        f"""
        <div style="
            max-width:680px;
            margin:auto;
            font-family:Arial,sans-serif;
            color:#172033;
            line-height:1.6;
        ">
            <div style="
                background:#151d2e;
                padding:22px 26px;
                color:#ffffff;
                font-size:26px;
                font-weight:800;
            ">
                <span style="color:#ef4052;">
                    10x
                </span>
                Devs
            </div>

            <div style="
                border:1px solid #e2e6ec;
                padding:26px;
            ">
                <h2 style="color:#c9182b;">
                    Application Status Update
                </h2>

                <p>
                    Dear
                    {html.escape(str(student['full_name']))},
                </p>

                <p>
                    <strong>Application reference:</strong>
                    {html.escape(str(student['application_reference']))}
                </p>

                <p>
                    <strong>Candidate number:</strong>
                    {html.escape(str(student['candidate_number']))}
                </p>

                <p>
                    <strong>Club:</strong>
                    {html.escape(str(student['club']))}
                </p>

                <p>
                    <strong>Current status:</strong>
                    {html.escape(application_status)}
                </p>

                <p>
                    {html.escape(status_message)}
                </p>
            </div>
        </div>
        """,
        subtype="html",
    )

    return send_message(
        message
    )


def send_offer_letter_email(
    student: dict[str, Any],
) -> str:
    application_status = str(
        student.get(
            "application_status",
            "",
        )
    ).strip()

    if application_status != "Selected":
        raise RuntimeError(
            "An offer letter can be sent only "
            "to a selected student."
        )

    message = create_base_message(
        subject=(
            "10x Devs Selection Offer | "
            f"{student['application_reference']}"
        ),
        recipient=str(
            student[
                "email"
            ]
        ),
    )

    message.set_content(
        f"Dear {student['full_name']},\n\n"
        "Congratulations!\n\n"
        "Based on the evaluation of your submitted "
        "work, you have been selected as a member of "
        f"the {student['club']} under 10x Devs.\n\n"
        f"Application reference: "
        f"{student['application_reference']}\n"
        f"Candidate number: "
        f"{student['candidate_number']}\n"
        f"Registration number: "
        f"{student['registration_number']}\n"
        f"Academic year: "
        f"{student['study_year']}\n"
        f"Selected club: "
        f"{student['club']}\n"
        "Offered position: Student Club Member\n"
        "Application status: Selected\n\n"
        "Your specific role, responsibilities, project "
        "allocation, team assignment, reporting structure, "
        "meeting schedule and other relevant information "
        "will be communicated during the onboarding process.\n\n"
        "Regards,\n"
        "10x Devs"
    )

    message.add_alternative(
        f"""
        <div style="
            max-width:700px;
            margin:auto;
            font-family:Arial,sans-serif;
            color:#172033;
            line-height:1.65;
        ">
            <div style="
                background:#151d2e;
                padding:24px 28px;
                color:#ffffff;
                font-size:28px;
                font-weight:800;
            ">
                <span style="color:#ef4052;">
                    10x
                </span>
                Devs
            </div>

            <div style="
                border:1px solid #e2e6ec;
                padding:30px;
            ">
                <div style="
                    color:#c9182b;
                    font-weight:700;
                    text-transform:uppercase;
                ">
                    Selection Offer
                </div>

                <h1>
                    Congratulations,
                    {html.escape(str(student['full_name']))}
                </h1>

                <p>
                    You have been selected as a member of
                    <strong>
                        {html.escape(str(student['club']))}
                    </strong>.
                </p>

                <p>
                    <strong>Application reference:</strong>
                    {html.escape(str(student['application_reference']))}
                </p>

                <p>
                    <strong>Candidate number:</strong>
                    {html.escape(str(student['candidate_number']))}
                </p>

                <p>
                    <strong>Offered position:</strong>
                    Student Club Member
                </p>

                <p>
                    <strong>Status:</strong>
                    Selected
                </p>

                <h3>Onboarding information</h3>

                <p>
                    Your specific role, responsibilities,
                    project allocation, team assignment,
                    reporting structure, meeting schedule
                    and other details will be communicated
                    during onboarding.
                </p>

                <p>
                    Regards,<br>
                    <strong>10x Devs</strong>
                </p>
            </div>
        </div>
        """,
        subtype="html",
    )

    return send_message(
        message
    )
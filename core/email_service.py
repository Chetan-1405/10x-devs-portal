from __future__ import annotations

import html
import smtplib
import socket
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from typing import Any

import streamlit as st

from core.constants import TASK_DOCUMENTS


DOCX_MIME_SUBTYPE = (
    "vnd.openxmlformats-officedocument."
    "wordprocessingml.document"
)


def get_gmail_settings() -> tuple[str, str, str, str]:
    """
    Read Gmail SMTP settings from Streamlit secrets.
    """

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
    ).replace(" ", "").strip()

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
    """
    Return True when Gmail SMTP credentials are available.
    """

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


def send_registration_email(
    student: dict[str, Any],
    task_document: bytes,
) -> str:
    """
    Send the registration email using Gmail SMTP.

    The correct fixed task document is attached based on
    whether the student registered as a 2nd-year or 3rd-year
    student.
    """

    (
        gmail_address,
        gmail_app_password,
        sender_name,
        contact_email,
    ) = get_gmail_settings()

    if not gmail_address:
        raise RuntimeError(
            "GMAIL_ADDRESS is missing from Streamlit secrets."
        )

    if "@" not in gmail_address:
        raise RuntimeError(
            "GMAIL_ADDRESS is not a valid email address."
        )

    if not gmail_app_password:
        raise RuntimeError(
            "GMAIL_APP_PASSWORD is missing from "
            "Streamlit secrets."
        )

    if not task_document:
        raise RuntimeError(
            "The task document is empty and cannot be attached."
        )

    required_fields = [
        "full_name",
        "registration_number",
        "study_year",
        "email",
        "club",
        "application_reference",
        "candidate_number",
        "task_deadline",
    ]

    missing_fields = [
        field
        for field in required_fields
        if student.get(field) in (
            None,
            "",
        )
    ]

    if missing_fields:
        raise RuntimeError(
            "Registration email data is incomplete: "
            + ", ".join(missing_fields)
        )

    study_year = str(
        student["study_year"]
    )

    if study_year not in TASK_DOCUMENTS:
        raise RuntimeError(
            f"No task document is configured for {study_year}."
        )

    task_filename = TASK_DOCUMENTS[
        study_year
    ]

    safe_name = html.escape(
        str(student["full_name"])
    )

    safe_club = html.escape(
        str(student["club"])
    )

    safe_registration_number = html.escape(
        str(student["registration_number"])
    )

    safe_application_reference = html.escape(
        str(student["application_reference"])
    )

    safe_candidate_number = html.escape(
        str(student["candidate_number"])
    )

    safe_study_year = html.escape(
        study_year
    )

    safe_deadline = html.escape(
        str(student["task_deadline"])
    )

    safe_contact_email = html.escape(
        contact_email
    )

    html_body = (
        '<div style="'
        'font-family:Arial,sans-serif;'
        'color:#172033;'
        'line-height:1.65;'
        'max-width:680px;'
        'margin:auto;'
        '">'

        '<div style="'
        'background:#151d2e;'
        'padding:22px 26px;'
        'border-radius:12px 12px 0 0;'
        '">'

        '<div style="'
        'color:#ffffff;'
        'font-size:26px;'
        'font-weight:800;'
        '">'

        '<span style="color:#ef4052;">10x</span> Devs'

        '</div>'
        '</div>'

        '<div style="'
        'border:1px solid #e2e6ec;'
        'border-top:none;'
        'padding:26px;'
        'border-radius:0 0 12px 12px;'
        '">'

        '<h2 style="'
        'color:#c9182b;'
        'margin-top:0;'
        '">'
        'Registration Successful'
        '</h2>'

        f'<p>Dear {safe_name},</p>'

        '<p>'
        'Your registration for '
        f'<strong>{safe_club}</strong> '
        'has been completed successfully.'
        '</p>'

        '<table style="'
        'border-collapse:collapse;'
        'width:100%;'
        'margin:20px 0;'
        '">'

        '<tr>'
        '<td style="'
        'border:1px solid #e2e6ec;'
        'padding:10px;'
        'font-weight:bold;'
        '">'
        'Registration number'
        '</td>'

        '<td style="'
        'border:1px solid #e2e6ec;'
        'padding:10px;'
        '">'
        f'{safe_registration_number}'
        '</td>'
        '</tr>'

        '<tr>'
        '<td style="'
        'border:1px solid #e2e6ec;'
        'padding:10px;'
        'font-weight:bold;'
        '">'
        'Application reference'
        '</td>'

        '<td style="'
        'border:1px solid #e2e6ec;'
        'padding:10px;'
        '">'
        f'{safe_application_reference}'
        '</td>'
        '</tr>'

        '<tr>'
        '<td style="'
        'border:1px solid #e2e6ec;'
        'padding:10px;'
        'font-weight:bold;'
        '">'
        'Candidate number'
        '</td>'

        '<td style="'
        'border:1px solid #e2e6ec;'
        'padding:10px;'
        '">'
        f'{safe_candidate_number}'
        '</td>'
        '</tr>'

        '<tr>'
        '<td style="'
        'border:1px solid #e2e6ec;'
        'padding:10px;'
        'font-weight:bold;'
        '">'
        'Academic year'
        '</td>'

        '<td style="'
        'border:1px solid #e2e6ec;'
        'padding:10px;'
        '">'
        f'{safe_study_year}'
        '</td>'
        '</tr>'

        '<tr>'
        '<td style="'
        'border:1px solid #e2e6ec;'
        'padding:10px;'
        'font-weight:bold;'
        '">'
        'Task deadline'
        '</td>'

        '<td style="'
        'border:1px solid #e2e6ec;'
        'padding:10px;'
        '">'
        f'{safe_deadline}'
        '</td>'
        '</tr>'

        '</table>'

        '<p>'
        'The official task document for your academic year '
        'is attached to this email.'
        '</p>'

        '<p>'
        'Complete the assigned task before the deadline. '
        'After completing it, log in to the 10x Devs portal '
        'and submit the required proof.'
        '</p>'

        '<p>'
        'The proof submission can be completed only once. '
        'Verify every link and file before submitting.'
        '</p>'

        '<p>'
        'For questions regarding the task or submission, '
        f'contact <strong>{safe_contact_email}</strong>.'
        '</p>'

        '<p>'
        'Regards,<br>'
        '<strong>10x Devs</strong>'
        '</p>'

        '</div>'
        '</div>'
    )

    text_body = (
        f"Dear {student['full_name']},\n\n"

        f"Your registration for {student['club']} "
        "has been completed successfully.\n\n"

        f"Registration number: "
        f"{student['registration_number']}\n"

        f"Application reference: "
        f"{student['application_reference']}\n"

        f"Candidate number: "
        f"{student['candidate_number']}\n"

        f"Academic year: "
        f"{student['study_year']}\n"

        f"Task deadline: "
        f"{student['task_deadline']}\n\n"

        "The official task document is attached to this email.\n\n"

        "Complete the task before the deadline and submit "
        "your proof through the 10x Devs portal.\n\n"

        "Proof submission is allowed only once.\n\n"

        "Regards,\n"
        "10x Devs"
    )

    message = EmailMessage()

    generated_message_id = make_msgid(
        domain="gmail.com"
    )

    message["Subject"] = (
        "10x Devs Registration | "
        f"{student['application_reference']}"
    )

    message["From"] = formataddr(
        (
            sender_name,
            gmail_address,
        )
    )

    message["To"] = str(
        student["email"]
    )

    message["Reply-To"] = contact_email

    message["Message-ID"] = (
        generated_message_id
    )

    message.set_content(
        text_body
    )

    message.add_alternative(
        html_body,
        subtype="html",
    )

    message.add_attachment(
        task_document,
        maintype="application",
        subtype=DOCX_MIME_SUBTYPE,
        filename=task_filename,
    )

    try:
        ssl_context = (
            ssl.create_default_context()
        )

        with smtplib.SMTP_SSL(
            "smtp.gmail.com",
            465,
            timeout=30,
            context=ssl_context,
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
            "Gmail authentication failed. Confirm that "
            "2-Step Verification is enabled for "
            "10xdevss@gmail.com and use the 16-character "
            "Google App Password instead of the normal "
            "Gmail password."
        ) from error

    except smtplib.SMTPRecipientsRefused as error:
        raise RuntimeError(
            "Gmail rejected the recipient email address."
        ) from error

    except (
        socket.timeout,
        TimeoutError,
    ) as error:
        raise RuntimeError(
            "The connection to Gmail SMTP timed out."
        ) from error

    except ssl.SSLError as error:
        raise RuntimeError(
            f"Gmail SSL connection error: {error}"
        ) from error

    except smtplib.SMTPException as error:
        raise RuntimeError(
            f"Gmail SMTP error: {error}"
        ) from error

    except OSError as error:
        raise RuntimeError(
            f"Could not connect to Gmail SMTP: {error}"
        ) from error

    if refused_recipients:
        raise RuntimeError(
            "Gmail refused one or more recipients: "
            f"{refused_recipients}"
        )

    return generated_message_id.strip(
        "<>"
    )
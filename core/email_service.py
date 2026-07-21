from __future__ import annotations

import smtplib
from datetime import date, datetime
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from html import escape
from typing import Any

import streamlit as st

from core.constants import (
    DOCX_MIME_TYPE,
    PORTAL_EMAIL,
    PORTAL_NAME,
    STATUS_EMAIL_MESSAGES,
    TASK_DOCUMENTS,
)
from core.pdf_service import generate_offer_letter_docx


# ============================================================
# GMAIL CONFIGURATION
# ============================================================

def get_gmail_settings() -> dict[str, str]:
    return {
        "address": str(
            st.secrets.get(
                "GMAIL_ADDRESS",
                "",
            )
        ).strip(),
        "app_password": str(
            st.secrets.get(
                "GMAIL_APP_PASSWORD",
                "",
            )
        ).replace(" ", "").strip(),
        "sender_name": str(
            st.secrets.get(
                "GMAIL_SENDER_NAME",
                PORTAL_NAME,
            )
        ).strip(),
        "contact_email": str(
            st.secrets.get(
                "CLUB_CONTACT_EMAIL",
                st.secrets.get(
                    "GMAIL_ADDRESS",
                    PORTAL_EMAIL,
                ),
            )
        ).strip(),
    }


def email_is_configured() -> bool:
    settings = get_gmail_settings()

    return bool(
        settings["address"]
        and settings["app_password"]
    )


# ============================================================
# GENERAL EMAIL HELPERS
# ============================================================

def safe_value(
    value: Any,
    fallback: str = "Not available",
) -> str:
    if value is None:
        return fallback

    cleaned_value = str(value).strip()

    return cleaned_value or fallback


def html_value(
    value: Any,
    fallback: str = "Not available",
) -> str:
    return escape(
        safe_value(
            value,
            fallback,
        )
    )


def human_datetime(
    value: Any,
) -> str:
    if value is None:
        return "Not available"

    if isinstance(value, datetime):
        parsed_value = value
    else:
        try:
            parsed_value = datetime.fromisoformat(
                str(value).replace(
                    "Z",
                    "+00:00",
                )
            )
        except ValueError:
            return safe_value(value)

    return parsed_value.strftime(
        "%d %B %Y, %I:%M %p"
    )


def create_email_message(
    recipient_email: str,
    subject: str,
    plain_text: str,
    html_content: str,
) -> EmailMessage:
    settings = get_gmail_settings()

    if not email_is_configured():
        raise RuntimeError(
            "Gmail SMTP is not configured."
        )

    recipient_email = recipient_email.strip()

    if not recipient_email:
        raise ValueError(
            "The recipient email address is missing."
        )

    message = EmailMessage()

    message["From"] = formataddr(
        (
            settings["sender_name"],
            settings["address"],
        )
    )

    message["To"] = recipient_email
    message["Subject"] = subject
    message["Message-ID"] = make_msgid()

    message.set_content(
        plain_text
    )

    message.add_alternative(
        html_content,
        subtype="html",
    )

    return message


def send_message(
    message: EmailMessage,
) -> str:
    settings = get_gmail_settings()

    try:
        with smtplib.SMTP_SSL(
            "smtp.gmail.com",
            465,
            timeout=30,
        ) as smtp:
            smtp.login(
                settings["address"],
                settings["app_password"],
            )

            smtp.send_message(
                message
            )

    except smtplib.SMTPAuthenticationError as error:
        raise RuntimeError(
            "Gmail authentication failed. Check the Gmail "
            "address and Google App Password."
        ) from error

    except smtplib.SMTPException as error:
        raise RuntimeError(
            f"Gmail SMTP error: {error}"
        ) from error

    except OSError as error:
        raise RuntimeError(
            f"Could not connect to Gmail SMTP: {error}"
        ) from error

    return str(
        message["Message-ID"]
    )


def add_binary_attachment(
    message: EmailMessage,
    file_bytes: bytes,
    filename: str,
    mime_type: str,
) -> None:
    if not file_bytes:
        raise ValueError(
            f"The attachment {filename} is empty."
        )

    if "/" not in mime_type:
        raise ValueError(
            "Invalid attachment MIME type."
        )

    maintype, subtype = mime_type.split(
        "/",
        maxsplit=1,
    )

    message.add_attachment(
        file_bytes,
        maintype=maintype,
        subtype=subtype,
        filename=filename,
    )


# ============================================================
# COLOURFUL HTML TEMPLATE
# ============================================================

def build_detail_row(
    label: str,
    value: Any,
) -> str:
    return f"""
    <tr>
        <td style="
            width:42%;
            padding:9px 10px;
            color:#667085;
            font-size:14px;
            font-weight:600;
            vertical-align:top;
            border-bottom:1px solid #E5EAF1;
        ">
            {escape(label)}
        </td>

        <td style="
            padding:9px 10px;
            color:#172033;
            font-size:14px;
            font-weight:700;
            vertical-align:top;
            border-bottom:1px solid #E5EAF1;
        ">
            {html_value(value)}
        </td>
    </tr>
    """


def build_email_html(
    *,
    title: str,
    greeting_name: str,
    introduction_html: str,
    details_html: str = "",
    content_html: str = "",
    badge_text: str = "10X DEVS",
    accent_note_html: str = "",
) -> str:
    settings = get_gmail_settings()

    detail_section = ""

    if details_html:
        detail_section = f"""
        <div style="
            margin:24px 0;
            background:#F8FAFC;
            border:1px solid #E1E7EF;
            border-left:5px solid #EF3340;
            border-radius:12px;
            overflow:hidden;
        ">
            <table role="presentation"
                   width="100%"
                   cellspacing="0"
                   cellpadding="0"
                   border="0">
                {details_html}
            </table>
        </div>
        """

    accent_section = ""

    if accent_note_html:
        accent_section = f"""
        <div style="
            margin-top:24px;
            padding:17px 19px;
            background:#FFF1F3;
            border:1px solid #FFC8CF;
            border-radius:12px;
            color:#9F1E2F;
            font-size:14px;
            line-height:1.65;
        ">
            {accent_note_html}
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        >
        <title>{escape(title)}</title>
    </head>

    <body style="
        margin:0;
        padding:0;
        background:#F4F6F9;
        font-family:Arial, Helvetica, sans-serif;
        color:#172033;
    ">

        <table role="presentation"
               width="100%"
               cellspacing="0"
               cellpadding="0"
               border="0"
               style="background:#F4F6F9;">

            <tr>
                <td align="center"
                    style="padding:30px 12px;">

                    <table role="presentation"
                           width="100%"
                           cellspacing="0"
                           cellpadding="0"
                           border="0"
                           style="
                               max-width:680px;
                               background:#FFFFFF;
                               border:1px solid #E1E7EF;
                               border-radius:18px;
                               overflow:hidden;
                               box-shadow:0 12px 34px
                                   rgba(23,32,51,0.10);
                           ">

                        <tr>
                            <td style="
                                padding:28px 32px;
                                background:#172033;
                                border-bottom:5px solid #EF3340;
                            ">

                                <table role="presentation"
                                       width="100%"
                                       cellspacing="0"
                                       cellpadding="0"
                                       border="0">

                                    <tr>
                                        <td valign="middle">
                                            <div style="
                                                color:#FFFFFF;
                                                font-size:29px;
                                                font-weight:800;
                                                letter-spacing:-1px;
                                            ">
                                                <span style="
                                                    color:#EF3340;
                                                ">10x</span> Devs
                                            </div>

                                            <div style="
                                                margin-top:6px;
                                                color:#C9D2E0;
                                                font-size:13px;
                                            ">
                                                Student Technical Community
                                            </div>
                                        </td>

                                        <td align="right"
                                            valign="middle">

                                            <span style="
                                                display:inline-block;
                                                padding:8px 12px;
                                                background:
                                                    rgba(239,51,64,0.18);
                                                border:1px solid
                                                    rgba(255,120,134,0.55);
                                                border-radius:999px;
                                                color:#FFD7DC;
                                                font-size:11px;
                                                font-weight:700;
                                                letter-spacing:0.45px;
                                            ">
                                                {escape(badge_text)}
                                            </span>
                                        </td>
                                    </tr>

                                </table>
                            </td>
                        </tr>

                        <tr>
                            <td style="padding:34px;">

                                <h1 style="
                                    margin:0 0 18px;
                                    color:#172033;
                                    font-size:25px;
                                    line-height:1.3;
                                ">
                                    {escape(title)}
                                </h1>

                                <p style="
                                    margin:0 0 18px;
                                    color:#344054;
                                    font-size:16px;
                                    line-height:1.7;
                                ">
                                    Dear {html_value(greeting_name, "Student")},
                                </p>

                                <div style="
                                    margin:0 0 20px;
                                    color:#556176;
                                    font-size:15px;
                                    line-height:1.75;
                                ">
                                    {introduction_html}
                                </div>

                                {detail_section}

                                <div style="
                                    color:#445067;
                                    font-size:15px;
                                    line-height:1.75;
                                ">
                                    {content_html}
                                </div>

                                {accent_section}

                                <p style="
                                    margin:28px 0 0;
                                    color:#556176;
                                    font-size:15px;
                                    line-height:1.7;
                                ">
                                    Warm regards,<br>
                                    <strong style="color:#172033;">
                                        10x Devs
                                    </strong>
                                </p>
                            </td>
                        </tr>

                        <tr>
                            <td align="center"
                                style="
                                    padding:18px 24px;
                                    background:#172033;
                                    color:#AEB9C9;
                                    font-size:12px;
                                    line-height:1.6;
                                ">

                                This is an official communication
                                from 10x Devs.

                                <br>

                                Contact:
                                <a href="mailto:{escape(settings['contact_email'])}"
                                   style="
                                       color:#FF7A88;
                                       text-decoration:none;
                                   ">
                                    {escape(settings['contact_email'])}
                                </a>
                            </td>
                        </tr>

                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """


# ============================================================
# REGISTRATION EMAIL
# ============================================================

def send_registration_email(
    student: dict[str, Any],
    task_document: bytes,
) -> str:
    student_name = safe_value(
        student.get("full_name"),
        "Student",
    )

    recipient_email = safe_value(
        student.get("email"),
        "",
    )

    study_year = safe_value(
        student.get("study_year")
    )

    application_reference = safe_value(
        student.get("application_reference")
    )

    candidate_number = safe_value(
        student.get("candidate_number")
    )

    club = safe_value(
        student.get("club")
    )

    task_deadline = safe_value(
        student.get("task_deadline")
    )

    subject = (
        f"10x Devs Registration Successful | "
        f"{application_reference}"
    )

    plain_text = f"""
Dear {student_name},

Your 10x Devs registration was completed successfully.

Club: {club}
Academic year: {study_year}
Application reference: {application_reference}
Candidate number: {candidate_number}
Task deadline: {task_deadline}

Complete the mandatory portfolio task and at least one eligible
specific task.

The official task document is attached.

Warm regards,
10x Devs
""".strip()

    details_html = (
        build_detail_row(
            "Registered club",
            club,
        )
        + build_detail_row(
            "Academic year",
            study_year,
        )
        + build_detail_row(
            "Application reference",
            application_reference,
        )
        + build_detail_row(
            "Candidate number",
            candidate_number,
        )
        + build_detail_row(
            "Submission deadline",
            task_deadline,
        )
    )

    html_content = build_email_html(
        title="Registration Successful",
        greeting_name=student_name,
        introduction_html=(
            "Your registration for the 10x Devs recruitment "
            "process has been completed successfully."
        ),
        details_html=details_html,
        content_html="""
            <p style="margin:0 0 12px;">
                Complete the mandatory portfolio task and at least
                one eligible specific task before the deadline.
            </p>

            <p style="margin:0;">
                Multiple eligible specific tasks may be included in
                one final proof submission.
            </p>
        """,
        badge_text="REGISTRATION",
        accent_note_html=(
            "The official task document is attached. Keep your "
            "application reference and candidate number for future "
            "communication."
        ),
    )

    message = create_email_message(
        recipient_email=recipient_email,
        subject=subject,
        plain_text=plain_text,
        html_content=html_content,
    )

    filename = TASK_DOCUMENTS.get(
        study_year,
        "10x_devs_tasks.docx",
    )

    add_binary_attachment(
        message=message,
        file_bytes=task_document,
        filename=filename,
        mime_type=DOCX_MIME_TYPE,
    )

    return send_message(
        message
    )


# ============================================================
# PASSWORD RESET OTP EMAIL
# ============================================================

def send_password_reset_otp_email(
    student: dict[str, Any],
    otp: str,
    validity_minutes: int,
) -> str:
    student_name = safe_value(
        student.get("full_name"),
        "Student",
    )

    recipient_email = safe_value(
        student.get("email"),
        "",
    )

    registration_number = safe_value(
        student.get("registration_number")
    )

    subject = "10x Devs Password Reset OTP"

    plain_text = f"""
Dear {student_name},

A password reset was requested for registration number
{registration_number}.

Your OTP is: {otp}

This OTP is valid for {validity_minutes} minutes.
Do not share this OTP with anyone.

Warm regards,
10x Devs
""".strip()

    details_html = (
        build_detail_row(
            "Registration number",
            registration_number,
        )
        + build_detail_row(
            "OTP validity",
            f"{validity_minutes} minutes",
        )
    )

    html_content = build_email_html(
        title="Password Reset OTP",
        greeting_name=student_name,
        introduction_html=(
            "A password-reset request was received for your "
            "10x Devs student account."
        ),
        details_html=details_html,
        content_html=f"""
            <div style="
                margin:22px 0;
                padding:18px;
                text-align:center;
                background:#172033;
                border-radius:12px;
            ">
                <div style="
                    color:#C9D2E0;
                    font-size:12px;
                    letter-spacing:1px;
                    margin-bottom:7px;
                ">
                    YOUR ONE-TIME PASSWORD
                </div>

                <div style="
                    color:#FFFFFF;
                    font-size:32px;
                    font-weight:800;
                    letter-spacing:7px;
                ">
                    {escape(otp)}
                </div>
            </div>
        """,
        badge_text="SECURITY",
        accent_note_html=(
            "Do not share this OTP with anyone. 10x Devs will "
            "never ask you to provide your OTP by phone or message."
        ),
    )

    message = create_email_message(
        recipient_email=recipient_email,
        subject=subject,
        plain_text=plain_text,
        html_content=html_content,
    )

    return send_message(
        message
    )


# ============================================================
# FINAL SUBMISSION EMAIL
# ============================================================

def send_submission_under_scrutiny_email(
    student: dict[str, Any],
    mandatory_task: str,
    selected_tasks: list[str],
    receipt_pdf: bytes | None = None,
    receipt_filename: str | None = None,
) -> str:
    student_name = safe_value(
        student.get("full_name"),
        "Student",
    )

    recipient_email = safe_value(
        student.get("email"),
        "",
    )

    application_reference = safe_value(
        student.get("application_reference")
    )

    task_list_text = "\n".join(
        f"- {task}"
        for task in selected_tasks
    )

    task_list_html = "".join(
        f"""
        <li style="
            margin-bottom:7px;
            color:#344054;
        ">
            {escape(task)}
        </li>
        """
        for task in selected_tasks
    )

    subject = (
        f"10x Devs Submission Received | "
        f"{application_reference}"
    )

    plain_text = f"""
Dear {student_name},

Your final proof submission was received successfully.

Application reference: {application_reference}
Current status: Under Scrutiny
Mandatory task: {mandatory_task}

Specific tasks:
{task_list_text}

Your work is now being reviewed.

Warm regards,
10x Devs
""".strip()

    details_html = (
        build_detail_row(
            "Application reference",
            application_reference,
        )
        + build_detail_row(
            "Current status",
            "Under Scrutiny",
        )
        + build_detail_row(
            "Mandatory task",
            mandatory_task,
        )
        + build_detail_row(
            "Specific tasks submitted",
            len(selected_tasks),
        )
    )

    html_content = build_email_html(
        title="Final Submission Received",
        greeting_name=student_name,
        introduction_html=(
            "Your mandatory task and selected specific tasks were "
            "submitted successfully. Your application has moved to "
            "<strong>Under Scrutiny</strong>."
        ),
        details_html=details_html,
        content_html=f"""
            <p style="margin:0 0 12px;">
                The following specific tasks were included:
            </p>

            <ul style="
                margin:0;
                padding-left:22px;
            ">
                {task_list_html}
            </ul>
        """,
        badge_text="UNDER SCRUTINY",
        accent_note_html=(
            "The evaluation team will review your implementation, "
            "documentation, links and submitted evidence."
        ),
    )

    message = create_email_message(
        recipient_email=recipient_email,
        subject=subject,
        plain_text=plain_text,
        html_content=html_content,
    )

    if receipt_pdf and receipt_filename:
        add_binary_attachment(
            message=message,
            file_bytes=receipt_pdf,
            filename=receipt_filename,
            mime_type="application/pdf",
        )

    return send_message(
        message
    )


# ============================================================
# APPLICATION STATUS EMAIL
# ============================================================

def send_status_email(
    student: dict[str, Any],
) -> str:
    student_name = safe_value(
        student.get("full_name"),
        "Student",
    )

    recipient_email = safe_value(
        student.get("email"),
        "",
    )

    application_reference = safe_value(
        student.get("application_reference")
    )

    club = safe_value(
        student.get("club")
    )

    status = safe_value(
        student.get("application_status"),
        "Registered",
    )

    status_message = STATUS_EMAIL_MESSAGES.get(
        status,
        (
            "Your application status was updated. Refer to the "
            "student portal for the latest information."
        ),
    )

    subject = (
        f"10x Devs Status: {status} | "
        f"{application_reference}"
    )

    plain_text = f"""
Dear {student_name},

Your 10x Devs application status has been updated.

Application reference: {application_reference}
Club: {club}
Current status: {status}

{status_message}

Warm regards,
10x Devs
""".strip()

    details_html = (
        build_detail_row(
            "Application reference",
            application_reference,
        )
        + build_detail_row(
            "Registered club",
            club,
        )
        + build_detail_row(
            "Current status",
            status,
        )
    )

    html_content = build_email_html(
        title="Application Status Update",
        greeting_name=student_name,
        introduction_html=(
            "There has been an update to your 10x Devs "
            "application."
        ),
        details_html=details_html,
        content_html=f"""
            <p style="margin:0;">
                {escape(status_message)}
            </p>
        """,
        badge_text=status.upper(),
        accent_note_html=(
            "This email reflects the application status at the "
            "time it was sent."
        ),
    )

    message = create_email_message(
        recipient_email=recipient_email,
        subject=subject,
        plain_text=plain_text,
        html_content=html_content,
    )

    return send_message(
        message
    )


# ============================================================
# PERSONALIZED DOCX OFFER LETTER EMAIL
# ============================================================

def send_offer_letter_email(
    student: dict[str, Any],
    template_bytes: bytes,
) -> dict[str, Any]:
    if safe_value(
        student.get("application_status"),
        "",
    ) != "Selected":
        raise ValueError(
            "Offer letters can be sent only to students whose "
            "application status is Selected."
        )

    (
        offer_letter_bytes,
        offer_letter_filename,
        document_number,
    ) = generate_offer_letter_docx(
        student=student,
        template_bytes=template_bytes,
        issue_date=date.today(),
    )

    student_name = safe_value(
        student.get("full_name"),
        "Student",
    )

    recipient_email = safe_value(
        student.get("email"),
        "",
    )

    application_reference = safe_value(
        student.get("application_reference")
    )

    candidate_number = safe_value(
        student.get("candidate_number")
    )

    registration_number = safe_value(
        student.get("registration_number")
    )

    club = safe_value(
        student.get("club")
    )

    subject = (
        f"10x Devs Selection Offer | "
        f"{registration_number}"
    )

    plain_text = f"""
Dear {student_name},

Congratulations.

You have been selected for {club} under 10x Devs.

Registration number: {registration_number}
Application reference: {application_reference}
Candidate number: {candidate_number}
Document number: {document_number}

Your personalized offer letter is attached.

Warm regards,
10x Devs
""".strip()

    details_html = (
        build_detail_row(
            "Registration number",
            registration_number,
        )
        + build_detail_row(
            "Application reference",
            application_reference,
        )
        + build_detail_row(
            "Candidate number",
            candidate_number,
        )
        + build_detail_row(
            "Selected club",
            club,
        )
        + build_detail_row(
            "Document number",
            document_number,
        )
    )

    html_content = build_email_html(
        title="Congratulations — You Are Selected",
        greeting_name=student_name,
        introduction_html=(
            "We are pleased to inform you that you have been "
            "selected based on the evaluation of your submitted work."
        ),
        details_html=details_html,
        content_html="""
            <p style="margin:0 0 12px;">
                Your personalized official offer letter is attached
                to this email as a DOCX document.
            </p>

            <p style="margin:0;">
                Your role, responsibilities, project allocation,
                team assignment and onboarding schedule will be
                communicated separately.
            </p>
        """,
        badge_text="SELECTED",
        accent_note_html=(
            "Please download and keep the attached offer letter. "
            "Monitor your registered email and the portal for "
            "onboarding instructions."
        ),
    )

    message = create_email_message(
        recipient_email=recipient_email,
        subject=subject,
        plain_text=plain_text,
        html_content=html_content,
    )

    add_binary_attachment(
        message=message,
        file_bytes=offer_letter_bytes,
        filename=offer_letter_filename,
        mime_type=DOCX_MIME_TYPE,
    )

    message_id = send_message(
        message
    )

    return {
        "message_id": message_id,
        "document_bytes": offer_letter_bytes,
        "filename": offer_letter_filename,
        "document_number": document_number,
    }


# ============================================================
# ANNOUNCEMENT EMAIL
# ============================================================

def send_announcement_email(
    student: dict[str, Any],
    announcement: dict[str, Any],
) -> str:
    student_name = safe_value(
        student.get("full_name"),
        "Student",
    )

    recipient_email = safe_value(
        student.get("email"),
        "",
    )

    announcement_title = safe_value(
        announcement.get("title"),
        "10x Devs Announcement",
    )

    announcement_body = safe_value(
        announcement.get("body"),
        "",
    )

    priority = safe_value(
        announcement.get("priority"),
        "Normal",
    )

    subject = (
        f"10x Devs Announcement: "
        f"{announcement_title}"
    )

    plain_text = f"""
Dear {student_name},

{announcement_title}

{announcement_body}

Priority: {priority}

Warm regards,
10x Devs
""".strip()

    html_content = build_email_html(
        title=announcement_title,
        greeting_name=student_name,
        introduction_html=(
            "A new announcement has been published for you."
        ),
        details_html=build_detail_row(
            "Priority",
            priority,
        ),
        content_html=f"""
            <p style="
                margin:0;
                white-space:pre-line;
            ">
                {escape(announcement_body)}
            </p>
        """,
        badge_text=priority.upper(),
        accent_note_html=(
            "Log in to the student portal to view other "
            "announcements and application updates."
        ),
    )

    message = create_email_message(
        recipient_email=recipient_email,
        subject=subject,
        plain_text=plain_text,
        html_content=html_content,
    )

    return send_message(
        message
    )


# ============================================================
# DEADLINE REMINDER EMAIL
# ============================================================

def send_deadline_reminder_email(
    student: dict[str, Any],
    reminder_type: str,
) -> str:
    student_name = safe_value(
        student.get("full_name"),
        "Student",
    )

    recipient_email = safe_value(
        student.get("email"),
        "",
    )

    deadline = safe_value(
        student.get("task_deadline")
    )

    application_reference = safe_value(
        student.get("application_reference")
    )

    subject = (
        f"10x Devs Submission Deadline Reminder | "
        f"{application_reference}"
    )

    plain_text = f"""
Dear {student_name},

This is a {reminder_type} reminder for your 10x Devs task deadline.

Application reference: {application_reference}
Task deadline: {deadline}

Log in to the portal and complete your submission before the
deadline.

Warm regards,
10x Devs
""".strip()

    details_html = (
        build_detail_row(
            "Application reference",
            application_reference,
        )
        + build_detail_row(
            "Task deadline",
            deadline,
        )
        + build_detail_row(
            "Reminder type",
            reminder_type,
        )
    )

    html_content = build_email_html(
        title="Submission Deadline Reminder",
        greeting_name=student_name,
        introduction_html=(
            "This is a reminder regarding your 10x Devs task "
            "submission deadline."
        ),
        details_html=details_html,
        content_html="""
            <p style="margin:0;">
                Log in to the portal, review your saved draft and
                complete your final proof submission before the
                deadline.
            </p>
        """,
        badge_text="DEADLINE",
        accent_note_html=(
            "A saved draft is not treated as a final submission. "
            "Use the Final Submit option after verifying all links "
            "and evidence."
        ),
    )

    message = create_email_message(
        recipient_email=recipient_email,
        subject=subject,
        plain_text=plain_text,
        html_content=html_content,
    )

    return send_message(
        message
    )


# ============================================================
# INTERVIEW SCHEDULE EMAIL
# ============================================================

def send_interview_schedule_email(
    student: dict[str, Any],
    interview: dict[str, Any],
) -> str:
    student_name = safe_value(
        student.get("full_name"),
        "Student",
    )

    recipient_email = safe_value(
        student.get("email"),
        "",
    )

    scheduled_at = human_datetime(
        interview.get("scheduled_at")
    )

    interview_mode = safe_value(
        interview.get("interview_mode")
    )

    venue_or_link = safe_value(
        interview.get("venue_or_link")
    )

    duration = safe_value(
        interview.get("duration_minutes"),
        "20",
    )

    instructions = safe_value(
        interview.get("instructions"),
        "No additional instructions.",
    )

    subject = "10x Devs Interview Schedule"

    plain_text = f"""
Dear {student_name},

Your 10x Devs interview has been scheduled.

Date and time: {scheduled_at}
Mode: {interview_mode}
Venue or link: {venue_or_link}
Duration: {duration} minutes

Instructions:
{instructions}

Warm regards,
10x Devs
""".strip()

    details_html = (
        build_detail_row(
            "Date and time",
            scheduled_at,
        )
        + build_detail_row(
            "Interview mode",
            interview_mode,
        )
        + build_detail_row(
            "Venue or meeting link",
            venue_or_link,
        )
        + build_detail_row(
            "Duration",
            f"{duration} minutes",
        )
    )

    html_content = build_email_html(
        title="Interview Scheduled",
        greeting_name=student_name,
        introduction_html=(
            "Your interview for the 10x Devs recruitment process "
            "has been scheduled."
        ),
        details_html=details_html,
        content_html=f"""
            <p style="margin:0;">
                <strong>Instructions:</strong><br>
                {escape(instructions)}
            </p>
        """,
        badge_text="INTERVIEW",
        accent_note_html=(
            "Join or report at least 10 minutes before the "
            "scheduled time."
        ),
    )

    message = create_email_message(
        recipient_email=recipient_email,
        subject=subject,
        plain_text=plain_text,
        html_content=html_content,
    )

    return send_message(
        message
    )


# ============================================================
# ONBOARDING EMAIL
# ============================================================

def send_onboarding_email(
    student: dict[str, Any],
    onboarding_message: str,
) -> str:
    student_name = safe_value(
        student.get("full_name"),
        "Student",
    )

    recipient_email = safe_value(
        student.get("email"),
        "",
    )

    club = safe_value(
        student.get("club")
    )

    subject = "10x Devs Onboarding Information"

    plain_text = f"""
Dear {student_name},

You have received an onboarding update for {club}.

{onboarding_message}

Warm regards,
10x Devs
""".strip()

    html_content = build_email_html(
        title="Onboarding Information",
        greeting_name=student_name,
        introduction_html=(
            "You have received an onboarding update for your "
            "selected club."
        ),
        details_html=build_detail_row(
            "Club",
            club,
        ),
        content_html=f"""
            <p style="
                margin:0;
                white-space:pre-line;
            ">
                {escape(onboarding_message)}
            </p>
        """,
        badge_text="ONBOARDING",
        accent_note_html=(
            "Log in to the student portal to confirm your "
            "onboarding attendance."
        ),
    )

    message = create_email_message(
        recipient_email=recipient_email,
        subject=subject,
        plain_text=plain_text,
        html_content=html_content,
    )

    return send_message(
        message
    )


# ============================================================
# SUPPORT RESPONSE EMAIL
# ============================================================

def send_support_response_email(
    support_request: dict[str, Any],
) -> str:
    recipient_name = safe_value(
        support_request.get("full_name"),
        "Student",
    )

    recipient_email = safe_value(
        support_request.get("email"),
        "",
    )

    subject_text = safe_value(
        support_request.get("subject"),
        "Support Request",
    )

    admin_response = safe_value(
        support_request.get("admin_response"),
        "",
    )

    subject = (
        f"10x Devs Support Response: "
        f"{subject_text}"
    )

    plain_text = f"""
Dear {recipient_name},

Your support request has received a response.

Subject: {subject_text}

Response:
{admin_response}

Warm regards,
10x Devs
""".strip()

    html_content = build_email_html(
        title="Support Request Response",
        greeting_name=recipient_name,
        introduction_html=(
            "The administration team has responded to your "
            "support request."
        ),
        details_html=build_detail_row(
            "Support subject",
            subject_text,
        ),
        content_html=f"""
            <p style="
                margin:0;
                white-space:pre-line;
            ">
                {escape(admin_response)}
            </p>
        """,
        badge_text="SUPPORT",
        accent_note_html=(
            "Reply to this email or submit another support request "
            "through the portal if further assistance is required."
        ),
    )

    message = create_email_message(
        recipient_email=recipient_email,
        subject=subject,
        plain_text=plain_text,
        html_content=html_content,
    )

    return send_message(
        message
    )
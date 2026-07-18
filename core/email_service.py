from __future__ import annotations

import smtplib
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from html import escape
from typing import Any

import streamlit as st

from core.constants import (
    STATUS_EMAIL_MESSAGES,
    TASK_DOCUMENTS,
)


# ============================================================
# GMAIL SETTINGS
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
                "10x Devs",
            )
        ).strip(),
        "contact_email": str(
            st.secrets.get(
                "CLUB_CONTACT_EMAIL",
                st.secrets.get(
                    "GMAIL_ADDRESS",
                    "",
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
# COMMON EMAIL HELPERS
# ============================================================

def safe_value(
    value: Any,
    fallback: str = "Not available",
) -> str:
    if value is None:
        return fallback

    clean_value = str(value).strip()

    return clean_value or fallback


def create_base_message(
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

    if not recipient_email.strip():
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

    message["To"] = recipient_email.strip()
    message["Subject"] = subject
    message["Message-ID"] = make_msgid(
        domain="10xdevs"
    )

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
            "Gmail authentication failed. Verify the Gmail "
            "address and Google App Password."
        ) from error

    except smtplib.SMTPException as error:
        raise RuntimeError(
            f"Gmail SMTP error: {error}"
        ) from error

    return str(
        message["Message-ID"]
    )


# ============================================================
# HTML EMAIL TEMPLATE
# ============================================================

def build_email_html(
    title: str,
    greeting_name: str,
    introduction: str,
    details_html: str,
    message_html: str,
    badge_text: str,
    footer_note: str,
) -> str:
    settings = get_gmail_settings()

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport"
              content="width=device-width, initial-scale=1.0">
        <title>{escape(title)}</title>
    </head>

    <body style="
        margin:0;
        padding:0;
        background:#f4f6f9;
        font-family:Arial, Helvetica, sans-serif;
        color:#172033;
    ">

        <table role="presentation"
               width="100%"
               cellspacing="0"
               cellpadding="0"
               border="0"
               style="background:#f4f6f9;">

            <tr>
                <td align="center"
                    style="padding:32px 14px;">

                    <table role="presentation"
                           width="100%"
                           cellspacing="0"
                           cellpadding="0"
                           border="0"
                           style="
                               max-width:680px;
                               background:#ffffff;
                               border-radius:18px;
                               overflow:hidden;
                               border:1px solid #e2e7ef;
                               box-shadow:0 12px 34px
                                   rgba(23,32,51,0.10);
                           ">

                        <tr>
                            <td style="
                                padding:28px 34px;
                                background:linear-gradient(
                                    135deg,
                                    #172033,
                                    #283650
                                );
                                border-bottom:5px solid #ef3340;
                            ">

                                <table role="presentation"
                                       width="100%"
                                       cellspacing="0"
                                       cellpadding="0"
                                       border="0">

                                    <tr>
                                        <td>
                                            <div style="
                                                color:#ffffff;
                                                font-size:28px;
                                                font-weight:800;
                                                letter-spacing:-1px;
                                            ">
                                                <span style="
                                                    color:#ef3340;
                                                ">10x</span> Devs
                                            </div>

                                            <div style="
                                                margin-top:6px;
                                                color:#cbd4e2;
                                                font-size:13px;
                                            ">
                                                Student Technical Community
                                            </div>
                                        </td>

                                        <td align="right"
                                            valign="middle">

                                            <span style="
                                                display:inline-block;
                                                padding:8px 13px;
                                                background:
                                                    rgba(239,51,64,0.18);
                                                border:1px solid
                                                    rgba(255,112,126,0.50);
                                                border-radius:999px;
                                                color:#ffd6db;
                                                font-size:11px;
                                                font-weight:700;
                                                letter-spacing:0.5px;
                                            ">
                                                {escape(badge_text)}
                                            </span>

                                        </td>
                                    </tr>
                                </table>

                            </td>
                        </tr>

                        <tr>
                            <td style="
                                padding:34px;
                            ">

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
                                    Dear {escape(greeting_name)},
                                </p>

                                <p style="
                                    margin:0 0 24px;
                                    color:#556176;
                                    font-size:15px;
                                    line-height:1.75;
                                ">
                                    {introduction}
                                </p>

                                <div style="
                                    margin:0 0 24px;
                                    padding:20px;
                                    background:#f8fafc;
                                    border:1px solid #e1e7ef;
                                    border-left:5px solid #ef3340;
                                    border-radius:12px;
                                ">
                                    {details_html}
                                </div>

                                <div style="
                                    margin:0 0 24px;
                                    color:#445067;
                                    font-size:15px;
                                    line-height:1.75;
                                ">
                                    {message_html}
                                </div>

                                <div style="
                                    margin-top:28px;
                                    padding:17px 19px;
                                    background:#fff1f3;
                                    border:1px solid #ffcbd1;
                                    border-radius:12px;
                                    color:#9f1e2f;
                                    font-size:14px;
                                    line-height:1.65;
                                ">
                                    {footer_note}
                                </div>

                                <p style="
                                    margin:28px 0 0;
                                    color:#556176;
                                    font-size:15px;
                                    line-height:1.7;
                                ">
                                    Regards,<br>
                                    <strong style="
                                        color:#172033;
                                    ">
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
                                    color:#aeb9c9;
                                    font-size:12px;
                                    line-height:1.6;
                                ">

                                This is an official communication from
                                10x Devs.

                                <br>

                                Contact:
                                <a href="mailto:{escape(settings['contact_email'])}"
                                   style="
                                       color:#ff7886;
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


def detail_row(
    label: str,
    value: Any,
) -> str:
    return f"""
    <table role="presentation"
           width="100%"
           cellspacing="0"
           cellpadding="0"
           border="0"
           style="margin-bottom:9px;">
        <tr>
            <td style="
                width:185px;
                color:#667085;
                font-size:14px;
                font-weight:600;
                vertical-align:top;
                padding-right:12px;
            ">
                {escape(label)}
            </td>

            <td style="
                color:#172033;
                font-size:14px;
                font-weight:700;
                vertical-align:top;
            ">
                {escape(safe_value(value))}
            </td>
        </tr>
    </table>
    """


# ============================================================
# REGISTRATION EMAIL
# ============================================================

def send_registration_email(
    student: dict,
    task_document: bytes,
) -> str:
    student_name = safe_value(
        student.get("full_name"),
        "Student",
    )

    email = safe_value(
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
        f"10x Devs Registration | "
        f"{application_reference}"
    )

    plain_text = f"""
Dear {student_name},

Your 10x Devs registration was completed successfully.

Club: {club}
Year: {study_year}
Application reference: {application_reference}
Candidate number: {candidate_number}
Task deadline: {task_deadline}

You must complete the mandatory portfolio task and at least one
eligible specific task. You may submit multiple specific tasks
together in the same final submission.

Third-year students may submit only tasks belonging to their
registered club.

The official task document is attached.

Regards,
10x Devs
""".strip()

    details_html = (
        detail_row(
            "Club",
            club,
        )
        + detail_row(
            "Academic year",
            study_year,
        )
        + detail_row(
            "Application reference",
            application_reference,
        )
        + detail_row(
            "Candidate number",
            candidate_number,
        )
        + detail_row(
            "Task deadline",
            task_deadline,
        )
    )

    message_html = """
    <p style="margin:0 0 14px;">
        Complete the mandatory portfolio task and at least one
        eligible specific task. Multiple eligible specific tasks
        may be submitted together in the same final submission.
    </p>

    <p style="margin:0;">
        Third-year students must submit only tasks belonging to
        their registered club.
    </p>
    """

    html_content = build_email_html(
        title="Registration Successful",
        greeting_name=student_name,
        introduction=(
            "Your 10x Devs registration has been completed "
            "successfully. Your application details are shown below."
        ),
        details_html=details_html,
        message_html=message_html,
        badge_text="REGISTRATION",
        footer_note=(
            "The official task document is attached to this email. "
            "Keep your application reference and candidate number "
            "for future communication."
        ),
    )

    message = create_base_message(
        recipient_email=email,
        subject=subject,
        plain_text=plain_text,
        html_content=html_content,
    )

    filename = TASK_DOCUMENTS.get(
        study_year,
        "10x_devs_tasks.docx",
    )

    message.add_attachment(
        task_document,
        maintype="application",
        subtype=(
            "vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
        filename=filename,
    )

    return send_message(
        message
    )


# ============================================================
# SUBMISSION EMAIL
# ============================================================

def send_submission_under_scrutiny_email(
    student: dict,
    mandatory_task: str,
    selected_tasks: list[str],
) -> str:
    student_name = safe_value(
        student.get("full_name"),
        "Student",
    )

    email = safe_value(
        student.get("email"),
        "",
    )

    application_reference = safe_value(
        student.get("application_reference")
    )

    task_items_html = "".join(
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

    selected_tasks_text = "\n".join(
        f"- {task}"
        for task in selected_tasks
    )

    subject = (
        "10x Devs Submission Received | "
        f"{application_reference}"
    )

    plain_text = f"""
Dear {student_name},

Your final proof submission was received successfully.

Application reference: {application_reference}
Current status: Under Scrutiny
Mandatory task: {mandatory_task}

Specific tasks:
{selected_tasks_text}

Your work is now being reviewed by the evaluation team.

Regards,
10x Devs
""".strip()

    details_html = (
        detail_row(
            "Application reference",
            application_reference,
        )
        + detail_row(
            "Current status",
            "Under Scrutiny",
        )
        + detail_row(
            "Mandatory task",
            mandatory_task,
        )
        + detail_row(
            "Specific tasks submitted",
            len(selected_tasks),
        )
    )

    message_html = f"""
    <p style="margin:0 0 12px;">
        The following specific tasks were included:
    </p>

    <ul style="
        margin:0;
        padding-left:22px;
    ">
        {task_items_html}
    </ul>
    """

    html_content = build_email_html(
        title="Submission Received",
        greeting_name=student_name,
        introduction=(
            "Your final proof submission was received successfully. "
            "Your application has automatically moved to "
            "<strong>Under Scrutiny</strong>."
        ),
        details_html=details_html,
        message_html=message_html,
        badge_text="UNDER SCRUTINY",
        footer_note=(
            "The evaluation team will review your implementation, "
            "documentation, links and submitted evidence."
        ),
    )

    message = create_base_message(
        recipient_email=email,
        subject=subject,
        plain_text=plain_text,
        html_content=html_content,
    )

    return send_message(
        message
    )


# ============================================================
# STATUS EMAIL
# ============================================================

def send_status_email(
    student: dict,
) -> str:
    student_name = safe_value(
        student.get("full_name"),
        "Student",
    )

    email = safe_value(
        student.get("email"),
        "",
    )

    status = safe_value(
        student.get("application_status"),
        "Registered",
    )

    application_reference = safe_value(
        student.get("application_reference")
    )

    club = safe_value(
        student.get("club")
    )

    status_message = STATUS_EMAIL_MESSAGES.get(
        status,
        (
            "Your application status has been updated. "
            "Please refer to the student portal for details."
        ),
    )

    subject = (
        f"10x Devs Application Status: {status} | "
        f"{application_reference}"
    )

    plain_text = f"""
Dear {student_name},

Your 10x Devs application status has been updated.

Application reference: {application_reference}
Club: {club}
Current status: {status}

{status_message}

Regards,
10x Devs
""".strip()

    details_html = (
        detail_row(
            "Application reference",
            application_reference,
        )
        + detail_row(
            "Club",
            club,
        )
        + detail_row(
            "Current status",
            status,
        )
    )

    message_html = f"""
    <p style="margin:0;">
        {escape(status_message)}
    </p>
    """

    html_content = build_email_html(
        title="Application Status Update",
        greeting_name=student_name,
        introduction=(
            "There has been an update to your 10x Devs application."
        ),
        details_html=details_html,
        message_html=message_html,
        badge_text=status.upper(),
        footer_note=(
            "This email reflects your current application status "
            "at the time it was sent."
        ),
    )

    message = create_base_message(
        recipient_email=email,
        subject=subject,
        plain_text=plain_text,
        html_content=html_content,
    )

    return send_message(
        message
    )


# ============================================================
# OFFER LETTER EMAIL
# ============================================================

def send_offer_letter_email(
    student: dict,
) -> str:
    status = safe_value(
        student.get("application_status")
    )

    if status != "Selected":
        raise ValueError(
            "Offer letters can be sent only to students "
            "whose application status is Selected."
        )

    student_name = safe_value(
        student.get("full_name"),
        "Student",
    )

    email = safe_value(
        student.get("email"),
        "",
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

    subject = (
        f"10x Devs Selection Offer | "
        f"{application_reference}"
    )

    plain_text = f"""
Dear {student_name},

Congratulations.

You have been selected for 10x Devs.

Application reference: {application_reference}
Candidate number: {candidate_number}
Selected club: {club}
Application status: Selected

Your specific role, responsibilities, project allocation, team
assignment, reporting structure, meeting schedule and other relevant
information will be communicated during onboarding.

Regards,
10x Devs
""".strip()

    details_html = (
        detail_row(
            "Application reference",
            application_reference,
        )
        + detail_row(
            "Candidate number",
            candidate_number,
        )
        + detail_row(
            "Selected club",
            club,
        )
        + detail_row(
            "Application status",
            "Selected",
        )
    )

    message_html = """
    <p style="margin:0 0 14px;">
        Congratulations on your selection for
        <strong>10x Devs</strong>.
    </p>

    <p style="margin:0;">
        Your specific role, responsibilities, project allocation,
        team assignment, reporting structure, meeting schedule and
        other relevant information will be communicated during
        onboarding.
    </p>
    """

    html_content = build_email_html(
        title="Congratulations — You Are Selected",
        greeting_name=student_name,
        introduction=(
            "We are pleased to inform you that you have been "
            "selected based on the evaluation of your submitted work."
        ),
        details_html=details_html,
        message_html=message_html,
        badge_text="SELECTED",
        footer_note=(
            "Please watch your registered email for onboarding "
            "instructions and further communication."
        ),
    )

    message = create_base_message(
        recipient_email=email,
        subject=subject,
        plain_text=plain_text,
        html_content=html_content,
    )

    return send_message(
        message
    )
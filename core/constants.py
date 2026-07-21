from __future__ import annotations

from typing import Final


# ============================================================
# PORTAL IDENTITY
# ============================================================

PORTAL_NAME: Final[str] = "10x Devs"

PORTAL_FULL_NAME: Final[str] = (
    "10x Devs Student Club Registration Portal"
)

PORTAL_EMAIL: Final[str] = "10xdevss@gmail.com"

INAUGURATION_DATE: Final[str] = "25 January 2025"


# ============================================================
# CLUBS AND ACADEMIC YEARS
# ============================================================

CLUBS: Final[list[str]] = [
    "Computer Vision Club",
    "Web Development Club",
    "ML Club",
]


YEARS: Final[list[str]] = [
    "2nd Year",
    "3rd Year",
]


# ============================================================
# LEADERSHIP
# ============================================================

LEADERSHIP: Final[list[dict[str, str]]] = [
    {
        "role": "Inaugurated By",
        "name": "Dr. Ravi Kadiyala",
        "position": "Principal",
    },
    {
        "role": "President",
        "name": "Dr. Ch. Suresh Babu",
        "position": "HOD, CSE (AI & ML)",
    },
    {
        "role": "Secretary",
        "name": "A. Sri Chaitanya",
        "position": "Ph.D.",
    },
    {
        "role": "Coordinator",
        "name": "Chetan Ventrapragada",
        "position": "Final-Year Student",
    },
]


# ============================================================
# STORAGE BUCKETS
# ============================================================

TASK_DOCUMENT_BUCKET: Final[str] = (
    "task-documents"
)

PROOF_SUBMISSION_BUCKET: Final[str] = (
    "proof-submissions"
)

GENERATED_DOCUMENT_BUCKET: Final[str] = (
    "generated-documents"
)

CLUB_PROJECT_MEDIA_BUCKET: Final[str] = (
    "club-project-media"
)

OFFER_LETTER_TEMPLATE_BUCKET: Final[str] = (
    "offer-letter-templates"
)


# ============================================================
# FIXED STORAGE PATHS
# ============================================================

OFFER_LETTER_TEMPLATE_PATH: Final[str] = (
    "official_offer_letter_template.docx"
)

OFFER_LETTER_TEMPLATE_DISPLAY_NAME: Final[str] = (
    "Official 10x Devs Offer Letter Template"
)


# ============================================================
# FILE MIME TYPES
# ============================================================

DOCX_MIME_TYPE: Final[str] = (
    "application/vnd.openxmlformats-officedocument."
    "wordprocessingml.document"
)

PDF_MIME_TYPE: Final[str] = "application/pdf"

ZIP_MIME_TYPE: Final[str] = "application/zip"

PNG_MIME_TYPE: Final[str] = "image/png"

JPEG_MIME_TYPE: Final[str] = "image/jpeg"

WEBP_MIME_TYPE: Final[str] = "image/webp"


# ============================================================
# TASK DOCUMENTS
# ============================================================

TASK_DOCUMENTS: Final[dict[str, str]] = {
    "2nd Year": "second_year_tasks.docx",
    "3rd Year": "third_year_tasks.docx",
}


# ============================================================
# MANDATORY TASKS
# ============================================================

MANDATORY_TASKS: Final[dict[str, str]] = {
    "2nd Year": "Basic Portfolio Website",
    "3rd Year": "Full-Stack Portfolio Website",
}


# ============================================================
# SECOND-YEAR SPECIFIC TASKS
# ============================================================

SECOND_YEAR_TASKS: Final[list[str]] = [
    "Student Marks Calculator Website",
    "Quiz Application",
    "To-Do List",
    "Student Information Form",
    "Basic Calculator",
    "Number Guessing Game",
]


# ============================================================
# THIRD-YEAR CLUB-SPECIFIC TASKS
# ============================================================

THIRD_YEAR_TASKS: Final[dict[str, list[str]]] = {
    "ML Club": [
        "Club Member Skill Recommender",
        "Club Resource Recommendation System",
        "Student Feedback Analyzer",
        "Club Information Chatbot",
    ],

    "Computer Vision Club": [
        "Club Event Photo Organizer",
        "Hand Gesture Controller",
        "Attendance Image Capture System",
        "Object Detection and Counting Application",
    ],

    "Web Development Club": [
        "Club Announcement Board",
        "Club Member Directory",
        "Club Task Tracker",
        "Club Resource Sharing Platform",
    ],
}


# ============================================================
# CLUB INFORMATION
# ============================================================

CLUB_INFORMATION: Final[dict[str, dict[str, object]]] = {
    "Computer Vision Club": {
        "code": "CV CLUB",
        "short_name": "Computer Vision",
        "domain_name": "Computer Vision",
        "description": (
            "Build practical applications involving images, video, "
            "object detection, gesture recognition, attendance and "
            "visual automation."
        ),
        "technologies": [
            "Python",
            "OpenCV",
            "YOLO",
            "MediaPipe",
            "Deep Learning",
        ],
    },

    "Web Development Club": {
        "code": "WEB CLUB",
        "short_name": "Web Development",
        "domain_name": "Web Development",
        "description": (
            "Design and develop responsive web interfaces, backend "
            "services, databases, APIs and deployable full-stack "
            "applications."
        ),
        "technologies": [
            "HTML",
            "CSS",
            "JavaScript",
            "Python",
            "Databases",
        ],
    },

    "ML Club": {
        "code": "ML CLUB",
        "short_name": "Machine Learning",
        "domain_name": "Machine Learning",
        "description": (
            "Develop data-driven applications involving machine "
            "learning, natural language processing, recommendations "
            "and intelligent automation."
        ),
        "technologies": [
            "Python",
            "Scikit-learn",
            "NLP",
            "Pandas",
            "Deep Learning",
        ],
    },
}


CLUB_DOMAIN_NAMES: Final[dict[str, str]] = {
    "Computer Vision Club": "Computer Vision",
    "Web Development Club": "Web Development",
    "ML Club": "Machine Learning",
}


# ============================================================
# APPLICATION STATUSES
# ============================================================

APPLICATION_STATUSES: Final[list[str]] = [
    "Registered",
    "Proof Submitted",
    "Under Scrutiny",
    "Shortlisted",
    "Rejected",
    "Selected",
]


# ============================================================
# SUBMISSION STATES
# ============================================================

SUBMISSION_STATES: Final[list[str]] = [
    "Draft",
    "Final",
    "Reopened",
]


# ============================================================
# EVALUATION PROGRESS
# ============================================================

EVALUATION_PROGRESS_OPTIONS: Final[list[str]] = [
    "Not Reviewed",
    "In Review",
    "Completed",
]


# ============================================================
# INTERVIEW SETTINGS
# ============================================================

INTERVIEW_STATUSES: Final[list[str]] = [
    "Not Scheduled",
    "Scheduled",
    "Completed",
    "Cancelled",
    "Rescheduled",
]


INTERVIEW_SCHEDULE_STATUSES: Final[list[str]] = [
    "Scheduled",
    "Completed",
    "Cancelled",
    "Rescheduled",
]


INTERVIEW_MODES: Final[list[str]] = [
    "Online",
    "Offline",
    "Hybrid",
]


DEFAULT_INTERVIEW_DURATION_MINUTES: Final[int] = 20

MINIMUM_INTERVIEW_DURATION_MINUTES: Final[int] = 5

MAXIMUM_INTERVIEW_DURATION_MINUTES: Final[int] = 240


# ============================================================
# ONBOARDING SETTINGS
# ============================================================

ONBOARDING_STATUSES: Final[list[str]] = [
    "Not Started",
    "Invited",
    "Confirmed",
    "Completed",
    "Absent",
]


ATTENDANCE_STATUSES: Final[list[str]] = [
    "Pending",
    "Invited",
    "Confirmed",
    "Attended",
    "Absent",
]


# ============================================================
# SUPPORT REQUEST SETTINGS
# ============================================================

SUPPORT_REQUEST_STATUSES: Final[list[str]] = [
    "Open",
    "In Progress",
    "Resolved",
    "Closed",
]


# ============================================================
# CONTACT SETTINGS
# ============================================================

PREFERRED_CONTACT_MODES: Final[list[str]] = [
    "Email",
    "Mobile",
    "Both",
]


# ============================================================
# ANNOUNCEMENT SETTINGS
# ============================================================

ANNOUNCEMENT_PRIORITIES: Final[list[str]] = [
    "Normal",
    "Important",
    "Urgent",
]


ANNOUNCEMENT_AUDIENCES: Final[list[str]] = [
    "All",
    "Year",
    "Club",
    "Year and Club",
    "Selected Students",
    "Shortlisted Students",
]


ANNOUNCEMENT_DELIVERY_STATUSES: Final[list[str]] = [
    "Pending",
    "Sent",
    "Failed",
]


# ============================================================
# PROJECT SHOWCASE SETTINGS
# ============================================================

PROJECT_STATUSES: Final[list[str]] = [
    "Draft",
    "Published",
    "Archived",
]


PROJECT_LINK_FIELDS: Final[list[str]] = [
    "github_url",
    "live_url",
    "demo_url",
]


DEFAULT_PROJECTS_PER_CLUB: Final[int] = 6


# ============================================================
# EVALUATION CRITERIA
# ============================================================

EVALUATION_CRITERIA: Final[dict[str, dict[str, int]]] = {
    "2nd Year": {
        "Mandatory Basic Portfolio": 25,
        "Completed Specific Tasks": 35,
        "Functionality and Validation": 20,
        "Explanation and Submitted Evidence": 20,
    },

    "3rd Year": {
        "Mandatory Full-Stack Portfolio": 25,
        "Club-Specific Technical Tasks": 40,
        "Code Quality and Documentation": 20,
        "Demo, Screenshots and Deployment": 15,
    },
}


MAXIMUM_EVALUATION_SCORE: Final[int] = 100


# ============================================================
# PROOF FILE-UPLOAD SETTINGS
# ============================================================

ALLOWED_PROOF_EXTENSIONS: Final[list[str]] = [
    "pdf",
    "docx",
    "zip",
    "png",
    "jpg",
    "jpeg",
    "webp",
]


ALLOWED_PROJECT_IMAGE_EXTENSIONS: Final[list[str]] = [
    "png",
    "jpg",
    "jpeg",
    "webp",
]


ALLOWED_OFFER_TEMPLATE_EXTENSIONS: Final[list[str]] = [
    "docx",
]


MAX_PROOF_FILES: Final[int] = 15

MAX_TOTAL_PROOF_SIZE: Final[int] = (
    40 * 1024 * 1024
)

MAX_PROJECT_IMAGE_SIZE: Final[int] = (
    5 * 1024 * 1024
)

MAX_GENERATED_DOCUMENT_SIZE: Final[int] = (
    10 * 1024 * 1024
)

MAX_OFFER_TEMPLATE_SIZE: Final[int] = (
    10 * 1024 * 1024
)


# ============================================================
# MOBILE NUMBER SETTINGS
# ============================================================

DEFAULT_PHONE_REGION: Final[str] = "IN"

MIN_MOBILE_DIGITS: Final[int] = 10

MAX_MOBILE_DIGITS: Final[int] = 15


# ============================================================
# PASSWORD SETTINGS
# ============================================================

MINIMUM_PASSWORD_LENGTH: Final[int] = 8

MAXIMUM_PASSWORD_BYTES: Final[int] = 72


# ============================================================
# OTP SETTINGS
# ============================================================

OTP_LENGTH: Final[int] = 6

OTP_VALIDITY_MINUTES: Final[int] = 10

OTP_MAXIMUM_ATTEMPTS: Final[int] = 5

OTP_RESEND_COOLDOWN_SECONDS: Final[int] = 60


# ============================================================
# DEADLINE SETTINGS
# ============================================================

DEFAULT_TASK_DEADLINE_DAYS: Final[int] = 2


DEADLINE_REMINDER_TYPES: Final[dict[int, str]] = {
    3: "Three Days",
    1: "One Day",
    0: "Deadline Day",
    -1: "Overdue",
}


# ============================================================
# GENERATED DOCUMENT SETTINGS
# ============================================================

GENERATED_DOCUMENT_TYPES: Final[list[str]] = [
    "Offer Letter",
    "Submission Receipt",
    "Selection Certificate",
    "Other",
]


OFFER_LETTER_DOCUMENT_PREFIX: Final[str] = (
    "10X-OFFER"
)

SUBMISSION_RECEIPT_DOCUMENT_PREFIX: Final[str] = (
    "10X-RECEIPT"
)

SELECTION_CERTIFICATE_DOCUMENT_PREFIX: Final[str] = (
    "10X-CERT"
)

PDF_PAGE_SIZE: Final[str] = "A4"


# ============================================================
# OFFER-LETTER TEMPLATE PLACEHOLDERS
# ============================================================

OFFER_TEMPLATE_PLACEHOLDERS: Final[set[str]] = {
    "{{FULL_NAME}}",
    "{{REGISTRATION_NUMBER}}",
    "{{APPLICATION_REFERENCE}}",
    "{{CANDIDATE_NUMBER}}",
    "{{ACADEMIC_YEAR}}",
    "{{CLUB_NAME}}",
    "{{CLUB_DOMAIN}}",
    "{{ISSUE_DATE}}",
    "{{DOCUMENT_NUMBER}}",
}


REQUIRED_OFFER_TEMPLATE_PLACEHOLDERS: Final[set[str]] = {
    "{{FULL_NAME}}",
    "{{REGISTRATION_NUMBER}}",
    "{{CLUB_NAME}}",
    "{{CLUB_DOMAIN}}",
    "{{ISSUE_DATE}}",
}


OPTIONAL_OFFER_TEMPLATE_PLACEHOLDERS: Final[set[str]] = {
    "{{APPLICATION_REFERENCE}}",
    "{{CANDIDATE_NUMBER}}",
    "{{ACADEMIC_YEAR}}",
    "{{DOCUMENT_NUMBER}}",
}


# ============================================================
# EMAIL DELIVERY STATUSES
# ============================================================

EMAIL_DELIVERY_STATUSES: Final[list[str]] = [
    "Not Sent",
    "Pending",
    "Sent",
    "Failed",
]


# ============================================================
# STATUS EMAIL CONTENT
# ============================================================

STATUS_EMAIL_MESSAGES: Final[dict[str, str]] = {
    "Registered": (
        "Your registration has been received successfully. Complete "
        "the mandatory portfolio task and at least one eligible "
        "specific task before submitting your final proof."
    ),

    "Proof Submitted": (
        "Your mandatory-task and specific-task proof has been "
        "submitted successfully."
    ),

    "Under Scrutiny": (
        "Your submitted work is currently under scrutiny. The "
        "evaluation team is reviewing your implementation, "
        "documentation and submitted evidence."
    ),

    "Shortlisted": (
        "Congratulations. You have been shortlisted based on the "
        "initial evaluation of your submitted work. Further "
        "information will be communicated separately."
    ),

    "Rejected": (
        "Thank you for participating in the 10x Devs recruitment "
        "process. Your application was not selected for the current "
        "recruitment cycle."
    ),

    "Selected": (
        "Congratulations. You have been selected for the club. Your "
        "role, responsibilities and other relevant information will "
        "be communicated during onboarding."
    ),
}


# ============================================================
# ACTIVITY LOG ACTIONS
# ============================================================

ACTIVITY_ACTIONS: Final[dict[str, str]] = {
    "student_created": (
        "Student registration created"
    ),
    "student_updated": (
        "Student registration updated"
    ),
    "student_deleted": (
        "Student registration deleted"
    ),
    "password_reset_requested": (
        "Password reset requested"
    ),
    "password_reset_completed": (
        "Password reset completed"
    ),
    "draft_saved": (
        "Submission draft saved"
    ),
    "proof_finalized": (
        "Proof submission finalized"
    ),
    "submission_reopened": (
        "Submission reopened"
    ),
    "evaluation_saved": (
        "Evaluation saved"
    ),
    "status_changed": (
        "Application status changed"
    ),
    "status_email_sent": (
        "Status email sent"
    ),
    "offer_letter_generated": (
        "Offer letter generated"
    ),
    "offer_letter_sent": (
        "Offer letter sent"
    ),
    "offer_template_uploaded": (
        "Offer-letter template uploaded"
    ),
    "offer_template_replaced": (
        "Offer-letter template replaced"
    ),
    "offer_template_deleted": (
        "Offer-letter template deleted"
    ),
    "task_document_uploaded": (
        "Task document uploaded"
    ),
    "task_document_deleted": (
        "Task document deleted"
    ),
    "announcement_created": (
        "Announcement created"
    ),
    "announcement_sent": (
        "Announcement email sent"
    ),
    "project_created": (
        "Club project created"
    ),
    "project_updated": (
        "Club project updated"
    ),
    "project_deleted": (
        "Club project deleted"
    ),
    "interview_scheduled": (
        "Interview scheduled"
    ),
    "onboarding_updated": (
        "Onboarding status updated"
    ),
    "support_updated": (
        "Support request updated"
    ),
    "settings_updated": (
        "Portal settings updated"
    ),
}


# ============================================================
# ACTIVITY ACTOR TYPES
# ============================================================

ACTIVITY_ACTOR_TYPES: Final[list[str]] = [
    "Admin",
    "Evaluator",
    "Student",
    "System",
]


# ============================================================
# EVALUATOR DEFAULT PERMISSIONS
# ============================================================

DEFAULT_EVALUATOR_PERMISSIONS: Final[dict[str, bool]] = {
    "view_submissions": True,
    "evaluate_submissions": True,
    "change_application_status": False,
    "send_emails": False,
    "manage_students": False,
}


# ============================================================
# DEFAULT PORTAL SETTINGS
# ============================================================

DEFAULT_PORTAL_SETTINGS: Final[dict[str, dict]] = {
    "maintenance_mode": {
        "enabled": False,
        "message": (
            "The portal is temporarily under maintenance."
        ),
    },

    "registration_settings": {
        "open": True,
        "allowed_years": YEARS,
    },

    "submission_settings": {
        "open": True,
        "allow_drafts": True,
        "enforce_deadline": True,
    },

    "deadline_settings": {
        "default_days": DEFAULT_TASK_DEADLINE_DAYS,
        "reminder_days": [
            3,
            1,
            0,
        ],
    },

    "project_showcase_settings": {
        "enabled": True,
        "show_featured_first": True,
        "maximum_home_projects_per_club": (
            DEFAULT_PROJECTS_PER_CLUB
        ),
    },

    "support_settings": {
        "enabled": True,
        "contact_email": PORTAL_EMAIL,
    },

    "onboarding_settings": {
        "confirmation_enabled": True,
    },

    "offer_letter_settings": {
        "template_bucket": (
            OFFER_LETTER_TEMPLATE_BUCKET
        ),
        "template_path": (
            OFFER_LETTER_TEMPLATE_PATH
        ),
        "attach_docx": True,
        "allow_pdf_certificate": True,
    },
}
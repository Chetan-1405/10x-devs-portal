from __future__ import annotations


# ============================================================
# CLUBS AND ACADEMIC YEARS
# ============================================================

CLUBS = [
    "Computer Vision Club",
    "Web Development Club",
    "ML Club",
]


YEARS = [
    "2nd Year",
    "3rd Year",
]


# ============================================================
# YEAR-WISE TASK DOCUMENTS
# These filenames must match the files stored in Supabase.
# ============================================================

TASK_DOCUMENTS = {
    "2nd Year": "second_year_tasks.docx",
    "3rd Year": "third_year_tasks.docx",
}


# ============================================================
# MANDATORY TASKS
# ============================================================

MANDATORY_TASKS = {
    "2nd Year": "Basic Portfolio Website",
    "3rd Year": "Full-Stack Portfolio Website",
}


# ============================================================
# SECOND-YEAR SPECIFIC TASKS
# Common to students of all three clubs.
# ============================================================

SECOND_YEAR_TASKS = [
    "Student Marks Calculator Website",
    "Quiz Application",
    "To-Do List",
    "Student Information Form",
    "Basic Calculator",
    "Number Guessing Game",
]


# ============================================================
# THIRD-YEAR CLUB-SPECIFIC TASKS
# Students can submit only tasks from their registered club.
# ============================================================

THIRD_YEAR_TASKS = {
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
# APPLICATION STATUSES
# ============================================================

APPLICATION_STATUSES = [
    "Registered",
    "Proof Submitted",
    "Under Scrutiny",
    "Shortlisted",
    "Rejected",
    "Selected",
]


# ============================================================
# ADMIN-ONLY EVALUATION CRITERIA
# Students do not see the criterion-wise marks.
# ============================================================

EVALUATION_CRITERIA = {
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


# ============================================================
# PROOF-UPLOAD SETTINGS
# ============================================================

ALLOWED_PROOF_EXTENSIONS = [
    "pdf",
    "docx",
    "zip",
    "png",
    "jpg",
    "jpeg",
]


MAX_PROOF_FILES = 15


MAX_TOTAL_PROOF_SIZE = (
    40 * 1024 * 1024
)


# ============================================================
# STATUS EMAIL CONTENT
# ============================================================

STATUS_EMAIL_MESSAGES = {
    "Registered": (
        "Your registration has been received successfully. "
        "Complete the mandatory portfolio task and at least one "
        "eligible specific task before submitting your proof."
    ),

    "Proof Submitted": (
        "Your mandatory-task and specific-task proof has been "
        "submitted successfully."
    ),

    "Under Scrutiny": (
        "Your submitted work is currently under scrutiny. "
        "The evaluation team is reviewing your implementation, "
        "documentation and submitted evidence."
    ),

    "Shortlisted": (
        "Congratulations. You have been shortlisted based on "
        "the initial evaluation of your submitted work. "
        "Further information will be communicated separately."
    ),

    "Rejected": (
        "Thank you for participating in the 10x Devs recruitment "
        "process. Your application was not selected for the "
        "current recruitment cycle."
    ),

    "Selected": (
        "Congratulations. You have been selected for the club. "
        "Your role, responsibilities and other relevant details "
        "will be communicated during onboarding."
    ),
}
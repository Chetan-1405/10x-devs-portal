from __future__ import annotations

from typing import Any, Final


DEFAULT_CLUB_PROJECTS: Final[list[dict[str, Any]]] = [
    {
        "id": "presentation-ai-voice-assistant",
        "club": "ML Club",
        "title": "AI-Powered Voice Assistant",
        "short_description": (
            "A voice-enabled academic assistant that answers faculty "
            "and timetable questions using natural voice commands."
        ),
        "detailed_description": (
            "The system converts speech to text, understands the user's "
            "academic query, retrieves relevant faculty or timetable "
            "information from a database, and responds through both text "
            "and synthesized voice."
        ),
        "technologies": [
            "Python",
            "Speech-to-Text",
            "Natural Language Processing",
            "Database",
            "Text-to-Speech",
        ],
        "student_names": [
            "Chetan Ventrapragada",
            "V.Nainisha",
            "K.Akash",
            "Ch.Bhashitha",
            "G.Madhusri Ashvitha"],
        "academic_year": "2025–2026",
        "github_url": None,
        "live_url": None,
        "demo_url": None,
        "local_thumbnail": "assets/projects/ai_voice_assistant.png",
        "project_status": "Published",
        "featured": True,
        "display_order": 1,
        "source": "10x Devs Project Club Orientation",
    },
    {
        "id": "presentation-smart-helmet-echallan",
        "club": "Computer Vision Club",
        "title": (
            "Smart Helmet Violation Detection and "
            "Automated E-Challan System"
        ),
        "short_description": (
            "An AI traffic-monitoring system that detects helmet "
            "violations, reads licence plates and generates e-challans."
        ),
        "detailed_description": (
            "Two YOLOv8 models detect riders without helmets and locate "
            "licence plates. EasyOCR extracts plate numbers, SQLite stores "
            "violation details, and the system creates a PDF challan with "
            "the violation image and sends it through email. A Gradio "
            "interface supports demonstration and operation."
        ),
        "technologies": [
            "YOLOv8",
            "EasyOCR",
            "OpenCV",
            "SQLite",
            "Gradio",
            "PDF Generation",
        ],
        "student_names": [
            "K.Srija",
            "Chetan Ventrapragada",
            "Ch.Trinaya",
            "Srivalli",
            "K. Sasank Sai"],
        "academic_year": "2024–2025",
        "github_url": None,
        "live_url": None,
        "demo_url": None,
        "local_thumbnail": "assets/projects/smart_helmet_echallan.png",
        "project_status": "Published",
        "featured": True,
        "display_order": 2,
        "source": "10x Devs Project Presentations",
    },
    {
        "id": "presentation-club-resource-portal",
        "club": "Web Development Club",
        "title": "Club Portal for Resource Sharing",
        "short_description": (
            "A web portal that allows club members to organise and share "
            "learning resources, project material and announcements."
        ),
        "detailed_description": (
            "The portal supports a structured club workspace where members "
            "can publish useful resources, access shared project material "
            "and collaborate through a central web application."
        ),
        "technologies": [
            "Frontend Development",
            "Backend Development",
            "Database",
            "Resource Management",
        ],
        "student_names": [],
        "academic_year": "2025–2026",
        "github_url": None,
        "live_url": None,
        "demo_url": None,
        "local_thumbnail": "assets/projects/club_resource_portal.png",
        "project_status": "Published",
        "featured": True,
        "display_order": 3,
        "source": "10x Devs Project Club Orientation",
    },
    {
        "id": "presentation-ai-social-media-platform",
        "club": "ML Club",
        "title": "AI Social Media Content and Posting Platform",
        "short_description": (
            "A full-stack machine-learning web application that creates, "
            "schedules and publishes AI-generated social posts."
        ),
        "detailed_description": (
            "Users provide prompts to generate post content through an AI "
            "API, schedule the generated content, and publish it to platforms "
            "such as LinkedIn and Reddit from one application."
        ),
        "technologies": [
            "Full Stack",
            "Machine Learning",
            "OpenAI API",
            "LinkedIn",
            "Reddit",
            "Scheduling",
        ],
        "student_names": [
            "P. Gopal",
            "M. Sandeep",
            "T. Nagarjuna",
            "Y. Syavanth",
            "K. Mahani Koushal",
        ],
        "academic_year": "2024–2025",
        "github_url": None,
        "live_url": None,
        "demo_url": None,
        "local_thumbnail": "assets/projects/ai_social_media_platform.png",
        "project_status": "Published",
        "featured": False,
        "display_order": 4,
        "source": "10x Devs Project Presentations",
    },
    {
        "id": "presentation-honeypot-threat-detection",
        "club": "Web Development Club",
        "title": "Honeypot Web Application for Threat Detection",
        "short_description": (
            "A Flask-based security application that detects and records "
            "malicious interactions through a realistic decoy portal."
        ),
        "detailed_description": (
            "The application presents a fake student-login interface, "
            "detects suspicious patterns such as SQL injection, XSS and "
            "path traversal, and records or emails security alerts."
        ),
        "technologies": [
            "Flask",
            "Cybersecurity",
            "SQL Injection Detection",
            "XSS Detection",
            "Email Alerts",
        ],
        "student_names": [
            "G. Vignesh",
            "Ch. Akash Reddy",
            "Md. Arif",
            "M. Lakshman",
            "Srinivas",
        ],
        "academic_year": "2024–2025",
        "github_url": None,
        "live_url": None,
        "demo_url": None,
        "local_thumbnail": "assets/projects/honeypot_threat_detection.png",
        "project_status": "Published",
        "featured": False,
        "display_order": 5,
        "source": "10x Devs Project Presentations",
    },
    {
        "id": "presentation-virustotal-file-scanner",
        "club": "Web Development Club",
        "title": "VirusTotal File Scanner and Phishing Detection Portal",
        "short_description": (
            "A Django web application that checks uploaded files for "
            "malware and presents an understandable threat report."
        ),
        "detailed_description": (
            "The platform accepts a file, uses its hash with the VirusTotal "
            "API, and returns a detailed safety report. A React-based loading "
            "indicator provides a clear and user-friendly scanning workflow."
        ),
        "technologies": [
            "Django",
            "VirusTotal API",
            "React",
            "File Hashing",
            "Malware Detection",
        ],
        "student_names": [
            "Ch. Abhiram",
            "Raju Siriyala",
            "Charan Sai",
            "K. Anusha Devi",
            "G. Dhanvi",
            "A. Maha Lakshmi",
        ],
        "academic_year": "2024–2025",
        "github_url": None,
        "live_url": None,
        "demo_url": None,
        "local_thumbnail": "assets/projects/virustotal_file_scanner.png",
        "project_status": "Published",
        "featured": False,
        "display_order": 6,
        "source": "10x Devs Project Presentations",
    },
    {
        "id": "presentation-gradient-boosting-ensemble",
        "club": "ML Club",
        "title": "Ensemble Learning with Gradient Boosting Classifier",
        "short_description": (
            "A machine-learning study using Gradient Boosting to build "
            "a strong predictor from sequential weak learners."
        ),
        "detailed_description": (
            "The project studies ensemble learning, preprocessing and "
            "hyperparameter optimisation. The presentation reports training "
            "and testing accuracy of 1.0 and a five-fold average "
            "cross-validation score of 0.9417."
        ),
        "technologies": [
            "Python",
            "Scikit-learn",
            "Gradient Boosting",
            "Cross-Validation",
            "Hyperparameter Tuning",
        ],
        "student_names": [
            "I. Harsha",
            "T. Teja",
            "Jitendra",
            "Muhammad",
            "Y. Sasi",
        ],
        "academic_year": "2024–2025",
        "github_url": None,
        "live_url": None,
        "demo_url": None,
        "local_thumbnail": "assets/projects/gradient_boosting_ensemble.png",
        "project_status": "Published",
        "featured": False,
        "display_order": 7,
        "source": "10x Devs Project Presentations",
    },
]


def project_identity(project: dict[str, Any]) -> str:
    """Return a stable comparison key for merging built-in and database projects."""
    return (
        f"{project.get('club', '')}|{project.get('title', '')}"
        .strip()
        .casefold()
    )


def merge_project_catalogues(
    database_projects: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Merge the presentation projects with projects managed in Supabase.

    A published database project with the same club and title overrides
    the built-in presentation record, allowing administrators to add
    real links, uploaded thumbnails and corrected contributor details.
    """
    merged = {
        project_identity(project): dict(project)
        for project in DEFAULT_CLUB_PROJECTS
    }

    for project in database_projects:
        if project.get("project_status") != "Published":
            continue

        merged[project_identity(project)] = dict(project)

    projects = list(merged.values())

    return sorted(
        projects,
        key=lambda project: (
            not bool(project.get("featured")),
            int(project.get("display_order", 999)),
            str(project.get("title", "")).casefold(),
        ),
    )

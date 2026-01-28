"""
Configuration module for loading user profile and settings.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import yaml


@dataclass
class Personal:
    first_name: str = ""
    last_name: str = ""
    full_name: str = ""
    email: str = ""
    phone: str = ""
    linkedin: str = ""
    github: str = ""
    portfolio: str = ""


@dataclass
class Location:
    address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    country: str = ""
    willing_to_relocate: bool = True


@dataclass
class WorkAuthorization:
    authorized_to_work: bool = True
    require_sponsorship: bool = False
    visa_status: str = ""


@dataclass
class Experience:
    years_of_experience: int = 0
    current_company: str = ""
    current_title: str = ""


@dataclass
class Education:
    highest_degree: str = ""
    field_of_study: str = ""
    university: str = ""
    graduation_year: int = 0


@dataclass
class Resume:
    path: str = ""
    _profile_dir: Optional[Path] = field(default=None, repr=False)

    def get_absolute_path(self) -> Optional[Path]:
        """Return absolute path to resume file.

        Resolution order:
        1. If path is set and absolute, use it directly
        2. If path is set and relative, resolve relative to profile directory
        3. If path is empty, look for resume.pdf in profile directory
        """
        # Try explicit path first
        if self.path:
            expanded = os.path.expanduser(self.path)
            path = Path(expanded)
            # If relative and profile_dir is set, resolve relative to profile dir
            if not path.is_absolute() and self._profile_dir:
                path = self._profile_dir / path
            if path.exists():
                return path.absolute()

        # Auto-detect resume.pdf in profile directory
        if self._profile_dir:
            for filename in ["resume.pdf", "Resume.pdf", "resume.PDF"]:
                auto_path = self._profile_dir / filename
                if auto_path.exists():
                    return auto_path.absolute()

        return None


@dataclass
class Salary:
    expected_salary: str = ""
    salary_range_min: str = ""
    salary_range_max: str = ""
    currency: str = "USD"


@dataclass
class Availability:
    start_date: str = ""
    available_immediately: bool = False


@dataclass
class Diversity:
    gender: str = ""
    race: str = ""  # Explicit race field (e.g., "Asian")
    ethnicity: str = ""  # Combined race/ethnicity field
    hispanic_latino: str = ""  # Hispanic/Latino question (Yes/No)
    veteran_status: str = ""
    disability_status: str = ""


@dataclass
class Profile:
    """Complete user profile for job applications."""
    personal: Personal = field(default_factory=Personal)
    location: Location = field(default_factory=Location)
    work_authorization: WorkAuthorization = field(default_factory=WorkAuthorization)
    experience: Experience = field(default_factory=Experience)
    education: Education = field(default_factory=Education)
    resume: Resume = field(default_factory=Resume)
    salary: Salary = field(default_factory=Salary)
    availability: Availability = field(default_factory=Availability)
    diversity: Diversity = field(default_factory=Diversity)
    default_answers: dict = field(default_factory=dict)

    def get_field_value(self, field_type: str) -> Optional[str]:
        """Get value for a semantic field type."""
        field_map = {
            # Personal
            "first_name": self.personal.first_name,
            "last_name": self.personal.last_name,
            "full_name": self.personal.full_name,
            "email": self.personal.email,
            "phone": self.personal.phone,
            "linkedin": self.personal.linkedin,
            "github": self.personal.github,
            "portfolio": self.personal.portfolio,
            # Location
            "address": self.location.address,
            "city": self.location.city,
            "state": self.location.state,
            "zip_code": self.location.zip_code,
            "country": self.location.country,
            "willing_to_relocate": "Yes" if self.location.willing_to_relocate else "No",
            # Work Authorization
            "authorized_to_work": "Yes" if self.work_authorization.authorized_to_work else "No",
            "require_sponsorship": "Yes" if self.work_authorization.require_sponsorship else "No",
            "visa_status": self.work_authorization.visa_status,
            # Experience
            "years_of_experience": str(self.experience.years_of_experience),
            "current_company": self.experience.current_company,
            "current_title": self.experience.current_title,
            # Education
            "highest_degree": self.education.highest_degree,
            "field_of_study": self.education.field_of_study,
            "university": self.education.university,
            "graduation_year": str(self.education.graduation_year),
            # Salary
            "expected_salary": self.salary.expected_salary,
            "salary_range_min": self.salary.salary_range_min,
            "salary_range_max": self.salary.salary_range_max,
            # Availability
            "start_date": self.availability.start_date,
            "available_immediately": "Yes" if self.availability.available_immediately else "No",
            # Diversity/EEO
            "gender": self.diversity.gender,
            "race": self.diversity.race,
            "ethnicity": self.diversity.ethnicity or self.diversity.race,  # Fallback to race
            "hispanic_latino": self.diversity.hispanic_latino,
            "veteran_status": self.diversity.veteran_status,
            "disability_status": self.diversity.disability_status,
        }
        return field_map.get(field_type)


def get_available_profiles() -> List[str]:
    """Get list of available profile names."""
    profiles_dir = Path(__file__).parent.parent / "config" / "profiles"
    if not profiles_dir.exists():
        return []
    return [p.name for p in profiles_dir.iterdir() if p.is_dir() and (p / "profile.yaml").exists()]


def load_profile(profile_name: Optional[str] = None, config_path: Optional[str] = None) -> Profile:
    """Load user profile from YAML file.

    Args:
        profile_name: Name of the profile directory (e.g., "default", "Ming").
                      If provided, loads from config/profiles/{profile_name}/profile.yaml
        config_path: Direct path to profile YAML file. Overrides profile_name if provided.

    Returns:
        Loaded Profile object.
    """
    profiles_dir = Path(__file__).parent.parent / "config" / "profiles"

    if config_path is not None:
        config_path = Path(config_path)
    elif profile_name is not None:
        config_path = profiles_dir / profile_name / "profile.yaml"
    else:
        # Default to "default" profile
        config_path = profiles_dir / "default" / "profile.yaml"

    if not config_path.exists():
        available = get_available_profiles()
        if available:
            raise FileNotFoundError(
                f"Profile config not found: {config_path}\n"
                f"Available profiles: {', '.join(available)}"
            )
        else:
            raise FileNotFoundError(f"Profile config not found: {config_path}")

    with open(config_path, "r") as f:
        data = yaml.safe_load(f)

    # Get profile directory for resume auto-detection
    profile_dir = config_path.parent

    # Build Resume with profile directory for auto-detection
    resume_data = data.get("resume", {})
    resume = Resume(**resume_data)
    resume._profile_dir = profile_dir

    # Build profile from YAML data
    profile = Profile(
        personal=Personal(**data.get("personal", {})),
        location=Location(**data.get("location", {})),
        work_authorization=WorkAuthorization(**data.get("work_authorization", {})),
        experience=Experience(**data.get("experience", {})),
        education=Education(**data.get("education", {})),
        resume=resume,
        salary=Salary(**data.get("salary", {})),
        availability=Availability(**data.get("availability", {})),
        diversity=Diversity(**data.get("diversity", {})),
        default_answers=data.get("default_answers", {}),
    )

    # Override with environment variables if present
    if os.getenv("HERMES_EMAIL"):
        profile.personal.email = os.getenv("HERMES_EMAIL")
    if os.getenv("HERMES_PHONE"):
        profile.personal.phone = os.getenv("HERMES_PHONE")

    return profile


# ============================================================================
# Custom Answers System - Learn from unanswered questions
# ============================================================================

@dataclass
class CustomAnswer:
    """A saved question-answer pair."""
    question: str
    answer: str
    options: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)


@dataclass
class PendingQuestion:
    """An unanswered question waiting for user input."""
    question: str
    options: List[str] = field(default_factory=list)
    answer: str = ""
    encountered_at: str = ""
    job: str = ""


def _normalize_question(text: str) -> str:
    """Normalize question text for matching."""
    import re
    # Lowercase
    text = text.lower()
    # Remove punctuation except spaces
    text = re.sub(r'[^\w\s]', '', text)
    # Normalize whitespace
    text = ' '.join(text.split())
    return text


def _extract_keywords(text: str) -> List[str]:
    """Extract important keywords from question text."""
    # Common question keywords to look for
    important_patterns = [
        "non-compete", "noncompete", "non-solicitation",
        "worked for", "worked at", "ever worked", "previously worked",
        "currently work", "employed by", "employment",
        "authorized", "sponsorship", "visa",
        "relocate", "remote", "hybrid", "onsite",
        "salary", "compensation", "pay",
        "start date", "available", "notice period",
        "clearance", "security", "background check",
        "disability", "veteran", "gender", "race", "ethnicity",
        "referred", "hear about", "how did you find",
        "years of experience", "experience with",
    ]

    text_lower = text.lower()
    found = []
    for pattern in important_patterns:
        if pattern in text_lower:
            found.append(pattern)
    return found


def get_profile_path(profile_name: str) -> Path:
    """Get path to profile.yaml for a profile."""
    profiles_dir = Path(__file__).parent.parent / "config" / "profiles"
    return profiles_dir / profile_name / "profile.yaml"


def load_custom_answers(profile_name: str) -> Tuple[List[CustomAnswer], List[PendingQuestion]]:
    """Load custom answers from profile.yaml's custom_answers section.

    Returns:
        Tuple of (answered_questions, pending_questions)
    """
    profile_path = get_profile_path(profile_name)

    if not profile_path.exists():
        return [], []

    try:
        with open(profile_path, "r") as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        print(f"Warning: Could not load profile: {e}")
        return [], []

    # Get custom_answers section from profile
    custom_data = data.get("custom_answers", {})

    answered = []
    for item in custom_data.get("answered", []):
        if item.get("question") and item.get("answer"):
            answered.append(CustomAnswer(
                question=item["question"],
                answer=item["answer"],
                options=item.get("options", []),
                keywords=item.get("keywords", _extract_keywords(item["question"])),
            ))

    pending = []
    for item in custom_data.get("pending", []):
        if item.get("question"):
            pending.append(PendingQuestion(
                question=item["question"],
                options=item.get("options", []),
                answer=item.get("answer", ""),
                encountered_at=item.get("encountered_at", ""),
                job=item.get("job", ""),
            ))

    return answered, pending


def find_custom_answer(
    question: str,
    options: List[str],
    answered: List[CustomAnswer]
) -> Optional[str]:
    """Find a matching answer for a question.

    Uses multiple matching strategies:
    1. Exact normalized match
    2. Keyword overlap
    3. Substring match

    Returns:
        The answer string if found, None otherwise.
    """
    if not answered:
        return None

    question_normalized = _normalize_question(question)
    question_keywords = set(_extract_keywords(question))

    best_match = None
    best_score = 0

    for ca in answered:
        score = 0
        ca_normalized = _normalize_question(ca.question)

        # Exact match (after normalization)
        if question_normalized == ca_normalized:
            return ca.answer

        # High overlap in normalized text
        if ca_normalized in question_normalized or question_normalized in ca_normalized:
            score += 50

        # Keyword matching
        ca_keywords = set(ca.keywords) if ca.keywords else set(_extract_keywords(ca.question))
        if question_keywords and ca_keywords:
            overlap = question_keywords & ca_keywords
            if overlap:
                score += len(overlap) * 20

        # Check if answer is valid for current options
        if options and ca.answer:
            answer_lower = ca.answer.lower()
            option_match = any(
                answer_lower in opt.lower() or opt.lower().startswith(answer_lower)
                for opt in options
            )
            if option_match:
                score += 10
            else:
                # Answer doesn't match available options, reduce score
                score -= 20

        if score > best_score:
            best_score = score
            best_match = ca.answer

    # Only return if we have a reasonably confident match
    if best_score >= 30:
        return best_match

    return None


def save_pending_question(
    profile_name: str,
    question: str,
    options: List[str],
    job_info: str = ""
) -> bool:
    """Save an unanswered question to profile.yaml's custom_answers.pending list.

    Args:
        profile_name: Name of the profile
        question: The question text
        options: Available options (for dropdowns)
        job_info: Optional job description for context

    Returns:
        True if saved successfully
    """
    from datetime import datetime

    profile_path = get_profile_path(profile_name)

    if not profile_path.exists():
        print(f"  Warning: Profile not found: {profile_path}")
        return False

    # Load existing profile
    try:
        with open(profile_path, "r") as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        print(f"  Warning: Could not load profile: {e}")
        return False

    # Initialize custom_answers section if needed
    if "custom_answers" not in data:
        data["custom_answers"] = {"answered": [], "pending": []}
    if "answered" not in data["custom_answers"]:
        data["custom_answers"]["answered"] = []
    if "pending" not in data["custom_answers"]:
        data["custom_answers"]["pending"] = []

    custom_data = data["custom_answers"]

    # Check if question already exists (in answered or pending)
    question_normalized = _normalize_question(question)

    for item in custom_data.get("answered", []):
        if _normalize_question(item.get("question", "")) == question_normalized:
            # Already answered, skip
            return False

    for item in custom_data.get("pending", []):
        if _normalize_question(item.get("question", "")) == question_normalized:
            # Already pending, skip
            return False

    # Add to pending (only include options if non-empty)
    new_pending = {
        "question": question,
        "answer": "",  # User fills this in
        "encountered_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "job": job_info,
    }
    # Only add options field if there are actual options
    if options and len(options) > 0:
        new_pending["options"] = options

    custom_data["pending"].append(new_pending)

    # Save profile back
    try:
        with open(profile_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        print(f"  Saved pending question to profile: {question[:50]}...")
        return True
    except Exception as e:
        print(f"  Warning: Could not save pending question: {e}")
        return False


def promote_pending_to_answered(profile_name: str) -> int:
    """Move pending questions with answers to the answered section in profile.yaml.

    Returns:
        Number of questions promoted
    """
    profile_path = get_profile_path(profile_name)

    if not profile_path.exists():
        return 0

    try:
        with open(profile_path, "r") as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return 0

    custom_data = data.get("custom_answers", {})
    if "pending" not in custom_data or "answered" not in custom_data:
        return 0

    promoted = 0
    remaining_pending = []

    for item in custom_data["pending"]:
        if item.get("answer"):
            # Has an answer, move to answered
            answered_item = {
                "question": item["question"],
                "answer": item["answer"],
                "keywords": _extract_keywords(item["question"]),
            }
            # Only include options if non-empty
            if item.get("options"):
                answered_item["options"] = item["options"]
            custom_data["answered"].append(answered_item)
            promoted += 1
        else:
            remaining_pending.append(item)

    if promoted > 0:
        custom_data["pending"] = remaining_pending
        data["custom_answers"] = custom_data
        try:
            with open(profile_path, "w") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        except Exception:
            pass

    return promoted

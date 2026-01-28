"""
Field mapping module for semantic field identification.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class FieldType(Enum):
    """Semantic field types for job applications."""
    # Personal Information
    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"
    FULL_NAME = "full_name"
    EMAIL = "email"
    PHONE = "phone"

    # Online Presence
    LINKEDIN = "linkedin"
    GITHUB = "github"
    PORTFOLIO = "portfolio"
    WEBSITE = "website"

    # Location
    ADDRESS = "address"
    CITY = "city"
    STATE = "state"
    ZIP_CODE = "zip_code"
    COUNTRY = "country"
    WILLING_TO_RELOCATE = "willing_to_relocate"

    # Work Authorization (HIGH RISK)
    AUTHORIZED_TO_WORK = "authorized_to_work"
    REQUIRE_SPONSORSHIP = "require_sponsorship"
    VISA_STATUS = "visa_status"

    # Experience
    YEARS_OF_EXPERIENCE = "years_of_experience"
    CURRENT_COMPANY = "current_company"
    CURRENT_TITLE = "current_title"

    # Education
    HIGHEST_DEGREE = "highest_degree"
    FIELD_OF_STUDY = "field_of_study"
    UNIVERSITY = "university"
    GRADUATION_YEAR = "graduation_year"

    # Resume
    RESUME = "resume"
    COVER_LETTER = "cover_letter"

    # Salary
    EXPECTED_SALARY = "expected_salary"
    SALARY_RANGE_MIN = "salary_range_min"
    SALARY_RANGE_MAX = "salary_range_max"

    # Availability
    START_DATE = "start_date"
    AVAILABLE_IMMEDIATELY = "available_immediately"

    # EEOC/Diversity (HIGH RISK - EEO Fields)
    GENDER = "gender"
    ETHNICITY = "ethnicity"  # Race/ethnicity combined field
    RACE = "race"  # Explicit race field
    HISPANIC_LATINO = "hispanic_latino"  # Hispanic/Latino question (Yes/No)
    VETERAN_STATUS = "veteran_status"
    DISABILITY_STATUS = "disability_status"

    # Other
    HOW_DID_YOU_HEAR = "how_did_you_hear"
    REFERRAL = "referral"
    CUSTOM_QUESTION = "custom_question"
    UNKNOWN = "unknown"


# High-risk fields that require human confirmation
HIGH_RISK_FIELDS = {
    FieldType.AUTHORIZED_TO_WORK,
    FieldType.REQUIRE_SPONSORSHIP,
    FieldType.VISA_STATUS,
    FieldType.GENDER,
    FieldType.ETHNICITY,
    FieldType.RACE,
    FieldType.HISPANIC_LATINO,
    FieldType.VETERAN_STATUS,
    FieldType.DISABILITY_STATUS,
    FieldType.EXPECTED_SALARY,
    FieldType.SALARY_RANGE_MIN,
    FieldType.SALARY_RANGE_MAX,
}

# EEO (Equal Employment Opportunity) fields - require special handling
# These fields are legally voluntary but technically fragile
EEO_FIELD_TYPES = {
    FieldType.GENDER,
    FieldType.ETHNICITY,
    FieldType.RACE,
    FieldType.HISPANIC_LATINO,
    FieldType.VETERAN_STATUS,
    FieldType.DISABILITY_STATUS,
}

# Keywords that indicate an EEO field
EEO_KEYWORDS = [
    "race", "ethnicity", "gender", "sex", "disability", "veteran",
    "eeo", "equal employment", "hispanic", "latino", "eeoc",
    "voluntary self-identification", "demographic",
]

# Decline/skip options for EEO fields (in order of preference)
EEO_DECLINE_OPTIONS = [
    "i do not wish to disclose",
    "decline to answer",
    "prefer not to say",
    "decline to self-identify",
    "i don't wish to answer",
    "choose not to disclose",
    "decline",
    "prefer not to answer",
    "i choose not to disclose",
]


def is_eeo_field(field_type: FieldType) -> bool:
    """Check if a field type is an EEO field."""
    return field_type in EEO_FIELD_TYPES


def is_eeo_keyword_in_text(text: str) -> bool:
    """Check if text contains EEO-related keywords."""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in EEO_KEYWORDS)


@dataclass
class FieldPattern:
    """Pattern for matching form fields."""
    field_type: FieldType
    label_patterns: List[str]  # Regex patterns for labels
    name_patterns: List[str]   # Patterns for input name/id attributes
    placeholder_patterns: List[str]  # Patterns for placeholder text


# Common field patterns (case-insensitive)
FIELD_PATTERNS = [
    FieldPattern(
        field_type=FieldType.FIRST_NAME,
        label_patterns=[r"first\s*name", r"given\s*name", r"^name$"],
        name_patterns=[r"first_?name", r"fname", r"given_?name"],
        placeholder_patterns=[r"first\s*name", r"john"],
    ),
    FieldPattern(
        field_type=FieldType.LAST_NAME,
        label_patterns=[r"last\s*name", r"family\s*name", r"surname"],
        name_patterns=[r"last_?name", r"lname", r"surname", r"family_?name"],
        placeholder_patterns=[r"last\s*name", r"doe"],
    ),
    FieldPattern(
        field_type=FieldType.FULL_NAME,
        label_patterns=[r"full\s*name", r"^name$", r"your\s*name"],
        name_patterns=[r"full_?name", r"^name$"],
        placeholder_patterns=[r"full\s*name", r"john doe"],
    ),
    FieldPattern(
        field_type=FieldType.EMAIL,
        label_patterns=[r"e-?mail", r"email\s*address"],
        name_patterns=[r"e-?mail", r"email_?address"],
        placeholder_patterns=[r"e-?mail", r"@", r"example\.com"],
    ),
    FieldPattern(
        field_type=FieldType.PHONE,
        label_patterns=[r"phone", r"telephone", r"mobile", r"cell"],
        name_patterns=[r"phone", r"tel", r"mobile", r"cell"],
        placeholder_patterns=[r"phone", r"\(\d{3}\)", r"\+1"],
    ),
    FieldPattern(
        field_type=FieldType.LINKEDIN,
        label_patterns=[r"linkedin", r"linked\s*in"],
        name_patterns=[r"linkedin"],
        placeholder_patterns=[r"linkedin\.com", r"linkedin"],
    ),
    FieldPattern(
        field_type=FieldType.GITHUB,
        label_patterns=[r"github"],
        name_patterns=[r"github"],
        placeholder_patterns=[r"github\.com", r"github"],
    ),
    FieldPattern(
        field_type=FieldType.PORTFOLIO,
        label_patterns=[r"portfolio", r"personal\s*website", r"website"],
        name_patterns=[r"portfolio", r"website", r"url"],
        placeholder_patterns=[r"https?://", r"\.com"],
    ),
    FieldPattern(
        field_type=FieldType.ADDRESS,
        label_patterns=[r"street\s*address", r"^address$", r"address\s*line"],
        name_patterns=[r"address", r"street"],
        placeholder_patterns=[r"street", r"address"],
    ),
    FieldPattern(
        field_type=FieldType.CITY,
        label_patterns=[r"^city$", r"location.*city", r"city.*location"],
        name_patterns=[r"^city$", r"location.*city"],
        placeholder_patterns=[r"city", r"san francisco"],
    ),
    FieldPattern(
        field_type=FieldType.STATE,
        label_patterns=[r"^state$", r"province"],
        name_patterns=[r"^state$", r"province"],
        placeholder_patterns=[r"state", r"^ca$", r"california"],
    ),
    FieldPattern(
        field_type=FieldType.ZIP_CODE,
        label_patterns=[r"zip", r"postal\s*code"],
        name_patterns=[r"zip", r"postal"],
        placeholder_patterns=[r"zip", r"\d{5}"],
    ),
    FieldPattern(
        field_type=FieldType.COUNTRY,
        label_patterns=[r"^country$"],
        name_patterns=[r"^country$"],
        placeholder_patterns=[r"country", r"united states"],
    ),
    FieldPattern(
        field_type=FieldType.AUTHORIZED_TO_WORK,
        label_patterns=[r"authorized\s*to\s*work", r"legally\s*(authorized|eligible)"],
        name_patterns=[r"authorized", r"work_auth"],
        placeholder_patterns=[],
    ),
    FieldPattern(
        field_type=FieldType.REQUIRE_SPONSORSHIP,
        label_patterns=[r"sponsorship", r"require.*visa", r"need.*sponsorship"],
        name_patterns=[r"sponsor", r"visa"],
        placeholder_patterns=[],
    ),
    FieldPattern(
        field_type=FieldType.VISA_STATUS,
        label_patterns=[r"visa\s*status", r"immigration\s*status", r"work\s*status"],
        name_patterns=[r"visa", r"immigration"],
        placeholder_patterns=[],
    ),
    FieldPattern(
        field_type=FieldType.YEARS_OF_EXPERIENCE,
        label_patterns=[r"years?\s*(of)?\s*experience", r"experience\s*\(years\)"],
        name_patterns=[r"experience", r"years"],
        placeholder_patterns=[r"\d+\s*years?"],
    ),
    FieldPattern(
        field_type=FieldType.CURRENT_COMPANY,
        label_patterns=[r"current\s*(company|employer)", r"employer", r"^company\s*name", r"company$"],
        name_patterns=[r"company", r"employer", r"organization"],
        placeholder_patterns=[r"company", r"employer"],
    ),
    FieldPattern(
        field_type=FieldType.CURRENT_TITLE,
        label_patterns=[r"current\s*(title|position|role)", r"job\s*title", r"^title\*?$", r"position"],
        name_patterns=[r"title", r"position", r"role", r"job_title"],
        placeholder_patterns=[r"title", r"position"],
    ),
    FieldPattern(
        field_type=FieldType.HIGHEST_DEGREE,
        label_patterns=[r"(highest\s*)?degree", r"education\s*level", r"^degree\*?$"],
        name_patterns=[r"degree", r"education", r"edu_degree"],
        placeholder_patterns=[r"degree", r"bachelor", r"master"],
    ),
    FieldPattern(
        field_type=FieldType.UNIVERSITY,
        label_patterns=[r"university", r"school", r"institution", r"college", r"^school\*?$"],
        name_patterns=[r"university", r"school", r"college", r"institution", r"edu_school"],
        placeholder_patterns=[r"school", r"university"],
    ),
    FieldPattern(
        field_type=FieldType.RESUME,
        label_patterns=[r"resume", r"cv", r"curriculum\s*vitae", r"^attach$", r"attach.*resume", r"upload.*resume"],
        name_patterns=[r"resume", r"cv", r"data_compliance\[resume", r"resume_file"],
        placeholder_patterns=[],
    ),
    FieldPattern(
        field_type=FieldType.COVER_LETTER,
        label_patterns=[r"cover\s*letter"],
        name_patterns=[r"cover", r"letter", r"cover_letter"],
        placeholder_patterns=[],
    ),
    FieldPattern(
        field_type=FieldType.EXPECTED_SALARY,
        label_patterns=[r"(expected|desired)\s*salary", r"salary\s*expectation"],
        name_patterns=[r"salary"],
        placeholder_patterns=[],
    ),
    FieldPattern(
        field_type=FieldType.START_DATE,
        label_patterns=[r"start\s*date", r"(available|availability)\s*date", r"when.*start"],
        name_patterns=[r"start", r"available"],
        placeholder_patterns=[],
    ),
    FieldPattern(
        field_type=FieldType.GENDER,
        label_patterns=[r"^gender:?$", r"gender\s*identity", r"^gender\s*:"],
        name_patterns=[r"gender"],
        placeholder_patterns=[],
    ),
    FieldPattern(
        field_type=FieldType.HISPANIC_LATINO,
        label_patterns=[r"hispanic.*latino", r"latino.*hispanic", r"are you hispanic"],
        name_patterns=[r"hispanic", r"latino"],
        placeholder_patterns=[],
    ),
    FieldPattern(
        field_type=FieldType.RACE,
        label_patterns=[r"^race$", r"^race:"],
        name_patterns=[r"^race$"],
        placeholder_patterns=[],
    ),
    FieldPattern(
        field_type=FieldType.ETHNICITY,
        label_patterns=[r"ethnicity", r"ethnic"],
        name_patterns=[r"ethnicity", r"ethnic"],
        placeholder_patterns=[],
    ),
    FieldPattern(
        field_type=FieldType.VETERAN_STATUS,
        label_patterns=[r"veteran", r"military"],
        name_patterns=[r"veteran", r"military"],
        placeholder_patterns=[],
    ),
    FieldPattern(
        field_type=FieldType.DISABILITY_STATUS,
        label_patterns=[r"disability", r"disabled"],
        name_patterns=[r"disability"],
        placeholder_patterns=[],
    ),
    FieldPattern(
        field_type=FieldType.HOW_DID_YOU_HEAR,
        label_patterns=[r"how\s*did\s*you\s*(hear|find)", r"source", r"referral\s*source"],
        name_patterns=[r"source", r"hear", r"referral"],
        placeholder_patterns=[],
    ),
]


def get_field_pattern(field_type: FieldType) -> Optional[FieldPattern]:
    """Get pattern for a specific field type."""
    for pattern in FIELD_PATTERNS:
        if pattern.field_type == field_type:
            return pattern
    return None


def is_high_risk_field(field_type: FieldType) -> bool:
    """Check if a field type is high-risk."""
    return field_type in HIGH_RISK_FIELDS

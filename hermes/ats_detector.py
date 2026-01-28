"""
ATS (Applicant Tracking System) detector module.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ATSType(Enum):
    """Known ATS platforms."""
    LEVER = "lever"
    GREENHOUSE = "greenhouse"
    ASHBY = "ashby"
    WORKDAY = "workday"
    ICIMS = "icims"
    TALEO = "taleo"
    BAMBOOHR = "bamboohr"
    JOBVITE = "jobvite"
    SMARTRECRUITERS = "smartrecruiters"
    UNKNOWN = "unknown"


@dataclass
class ATSDetectionResult:
    """Result of ATS detection."""
    ats_type: ATSType
    confidence: float  # 0.0 to 1.0
    detection_method: str  # "url" or "dom"


# URL patterns for ATS detection
URL_PATTERNS = {
    ATSType.LEVER: [
        r"jobs\.lever\.co",
        r"lever\.co/[^/]+/jobs",
    ],
    ATSType.GREENHOUSE: [
        r"boards\.greenhouse\.io",
        r"greenhouse\.io/[^/]+/jobs",
        r"/greenhouse/",
    ],
    ATSType.ASHBY: [
        r"jobs\.ashbyhq\.com",
        r"ashbyhq\.com/[^/]+/jobs",
    ],
    ATSType.WORKDAY: [
        r"myworkdayjobs\.com",
        r"\.workday\.com",
        r"/workday/",
    ],
    ATSType.ICIMS: [
        r"careers-[^.]+\.icims\.com",
        r"\.icims\.com",
    ],
    ATSType.TALEO: [
        r"\.taleo\.net",
        r"taleo\.com",
    ],
    ATSType.BAMBOOHR: [
        r"[^.]+\.bamboohr\.com/jobs",
    ],
    ATSType.JOBVITE: [
        r"jobs\.jobvite\.com",
        r"\.jobvite\.com",
    ],
    ATSType.SMARTRECRUITERS: [
        r"jobs\.smartrecruiters\.com",
        r"\.smartrecruiters\.com",
    ],
}

# DOM markers for fallback detection
DOM_MARKERS = {
    ATSType.LEVER: [
        "lever-jobs-container",
        "lever-application-form",
        'data-lever',
    ],
    ATSType.GREENHOUSE: [
        "greenhouse-job-board",
        "#grnhse_app",
        'data-greenhouse',
    ],
    ATSType.ASHBY: [
        "ashby-job-posting",
        "_ashby_",
    ],
    ATSType.WORKDAY: [
        "workday-application",
        "wd-",
        "workday",
    ],
    ATSType.ICIMS: [
        "icims",
        "iCIMS",
    ],
}


def detect_ats_from_url(url: str) -> Optional[ATSDetectionResult]:
    """Detect ATS type from URL patterns."""
    url_lower = url.lower()

    for ats_type, patterns in URL_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, url_lower):
                return ATSDetectionResult(
                    ats_type=ats_type,
                    confidence=0.95,
                    detection_method="url",
                )
    return None


def detect_ats_from_dom(html_content: str) -> Optional[ATSDetectionResult]:
    """Detect ATS type from DOM markers."""
    html_lower = html_content.lower()

    for ats_type, markers in DOM_MARKERS.items():
        for marker in markers:
            if marker.lower() in html_lower:
                return ATSDetectionResult(
                    ats_type=ats_type,
                    confidence=0.75,
                    detection_method="dom",
                )
    return None


def detect_ats(url: str, html_content: Optional[str] = None) -> ATSDetectionResult:
    """
    Detect ATS platform from URL and optionally DOM content.

    Args:
        url: The job application URL
        html_content: Optional HTML content for DOM-based detection

    Returns:
        ATSDetectionResult with detected type and confidence
    """
    # Try URL detection first (higher confidence)
    url_result = detect_ats_from_url(url)
    if url_result:
        return url_result

    # Fall back to DOM detection
    if html_content:
        dom_result = detect_ats_from_dom(html_content)
        if dom_result:
            return dom_result

    # Unknown ATS
    return ATSDetectionResult(
        ats_type=ATSType.UNKNOWN,
        confidence=0.0,
        detection_method="none",
    )

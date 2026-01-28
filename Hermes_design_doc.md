# Job Application Agent – Design Document

## 1. Overview

This document describes the design of a **Job Application Agent** that automatically opens job application links and fills out application forms using **Playwright attached to a human-authenticated Chrome session**.

The primary goal is to **reduce manual effort** in repetitive job applications while maintaining:
- Low bot-detection risk
- High correctness on sensitive fields (visa, EEOC, authorization)
- Human-in-the-loop safety

This system is designed for **personal job search automation**, not bulk scraping or abusive behavior.

---

## 2. Goals & Non-Goals

### 2.1 Goals

- Open application links from a predefined job list
- Reuse an existing, logged-in Chrome profile (cookies, MFA, sessions)
- Automatically fill common ATS application fields
- Support multiple ATS platforms (Lever, Greenhouse, Workday, Ashby)
- Allow human confirmation before submission
- Log evidence of each application (status, screenshots)

### 2.2 Non-Goals

- No backend API submission to ATS platforms
- No headless or stealth browser automation
- No concurrent or high-frequency submissions
- No scraping of job postings beyond provided URLs

---

## 3. High-Level Architecture

```
┌────────────┐
│ Job List   │  (JSON / YAML)
└─────┬──────┘
      ↓
┌────────────┐
│ Orchestrator│  (job loop, state, retries)
└─────┬──────┘
      ↓
┌──────────────────────────┐
│ Browser Agent (Playwright)
│ - Attach via CDP         │
│ - Existing Chrome profile│
└─────┬────────────────────┘
      ↓
┌──────────────────────────┐
│ Form Understanding Agent │
│ - DOM → semantic fields  │
│ - Rule-based + LLM       │
└─────┬────────────────────┘
      ↓
┌──────────────────────────┐
│ Human Confirmation Layer │
│ - High-risk fields check │
└─────┬────────────────────┘
      ↓
┌──────────────────────────┐
│ Submission & Logging     │
│ - Screenshots            │
│ - Status                 │
└──────────────────────────┘
```

---

## 4. Input Specifications

### 4.1 Job List

The agent consumes a structured job list, e.g.:

```json
{
  "company": "Spotify",
  "title": "Research Scientist - Music",
  "url": "https://jobs.lever.co/spotify/3738dd16-b387-4daa-bed7-312b2be39418",
  "location": "United States",
  "source": "lever"
}
```

Each job entry must include:
- `url`: Direct application link
- `company`
- `title`
- `source` (if known; optional)

---

### 4.2 User Profile Config

```yaml
profile:
  name: Seraph Shen
  email: xxx@gmail.com
  phone: xxx
  linkedin: https://linkedin.com/in/...
  github: https://github.com/...

work_authorization:
  authorized_in_us: true
  require_sponsorship: false

resume:
  path: ./resume.pdf
```

Sensitive fields are treated as **high-risk** and require confirmation.

---

## 5. Browser Strategy

### 5.1 Chrome Attachment (Required)

- User manually launches Chrome with:

```bash
chrome --remote-debugging-port=9222 --user-data-dir=chrome-agent-profile
```

- User completes all logins and MFA manually
- Playwright attaches via CDP

```python
browser = await p.chromium.connect_over_cdp("http://localhost:9222")
context = browser.contexts[0]
page = await context.new_page()
```

This avoids:
- Login automation
- CAPTCHA challenges
- Device trust issues

---

## 6. ATS Detection (Lightweight)

ATS platform is inferred using:

- URL patterns (`jobs.lever.co`, `boards.greenhouse.io`)
- DOM markers (meta tags, form structure)

This is used only for **heuristics**, not hard dependencies.

---

## 7. Form Filling Strategy

### 7.1 Field Identification

Priority order:
1. `<label for>` associations
2. Placeholder / aria-label
3. Nearby text nodes

Each field is normalized into:

```json
{
  "semantic_field": "email",
  "selector": "input#email",
  "confidence": 0.92
}
```

---

### 7.2 Rule-based First, LLM Fallback

- Common fields (name, email, phone): rule-based
- Ambiguous or verbose questions: LLM-assisted

LLM receives:
- Field label
- Question text
- Allowed options

LLM outputs:

```json
{
  "field": "authorized_in_us",
  "value": "Yes",
  "confidence": "high"
}
```

---

## 8. High-Risk Field Handling

High-risk fields include:
- Work authorization
- Visa / sponsorship
- Criminal history
- EEOC demographics

Policy:
- Never auto-submit without confirmation
- Optional: hard-coded answers only

---

## 9. Human-in-the-Loop Confirmation

Before submission:

```
Company: Spotify
Role: Research Scientist – Music
Fields filled: 21
High-risk fields:
- Work authorization: Yes
- Sponsorship required: No

Submit? [Y/N]
```

---

## 10. Logging & Auditing

For each application:

- Timestamp
- Job metadata
- Submission status
- Screenshot of confirmation page
- HTML snapshot (optional)

This enables:
- Deduplication
- Follow-ups
- Debugging failures

---

## 11. Failure Modes & Recovery

| Failure | Strategy |
|-------|----------|
| Page load timeout | Retry once, then skip |
| Unexpected form layout | Pause for manual review |
| Validation error | Capture error + screenshot |
| CAPTCHA | Abort and notify user |

---

## 12. Security Considerations

- Chrome profile is local-only
- Config stored in `.env` / ignored by git
- No credential injection into LLM beyond required fields

---

## 13. Ethical & Legal Considerations

- Single-user automation
- No scraping
- No impersonation
- No bypassing access controls

This agent simulates **normal user behavior** at human scale.

---

## 14. Future Extensions

- ATS-specific adapters
- Resume versioning per role
- Application status tracking
- Cover letter generation module

---

## 15. Summary

This design prioritizes:
- Stability over cleverness
- Safety over scale
- Human control over full autonomy

It is suitable for serious job seekers who want leverage without unnecessary risk.


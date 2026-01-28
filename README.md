# Hermes - Job Application Automation Agent

Hermes is a job application automation agent that connects to an existing Chrome browser via CDP (Chrome DevTools Protocol) and auto-fills job application forms with human-in-the-loop confirmation.

> **⚠️ IMPORTANT: Human Review Recommended**
>
> This tool is in active development. **We highly recommend reviewing all filled forms before submission.** Always use the default mode (without `--auto-pilot`) and manually verify:
> - All fields are filled correctly
> - No sensitive information is misplaced
> - Work authorization and EEOC fields match your preferences
>
> The `--auto-pilot` mode is provided for convenience but should only be used after thorough testing with your profile.

## Features

- **Browser Integration**: Connects to existing Chrome browser via CDP
- **ATS Detection**: Automatically detects common ATS platforms (Lever, Greenhouse, Ashby, Workday, etc.)
- **Smart Field Mapping**: Uses pattern matching to identify form fields semantically
- **LLM Fallback**: Uses Claude API for ambiguous or custom questions
- **Human-in-the-Loop**: Always pauses for confirmation before submission
- **High-Risk Field Flagging**: Special handling for work authorization, EEOC, and salary fields
- **Screenshot Evidence**: Captures screenshots at key stages for audit trail
- **Session Logging**: JSON logs with detailed application history

## Installation

```bash
cd Hermes
pip install -r requirements.txt
playwright install chromium
```

## Configuration

### 1. Set up your profile

Create your personal profile by copying the default template:

```bash
# Copy the default profile
cp -r config/profiles/default config/profiles/YourName

# Edit with your real information
nano config/profiles/YourName/profile.yaml

# Place your resume in the profile folder
cp ~/Documents/resume.pdf config/profiles/YourName/resume.pdf
```

Profile structure:
```
config/profiles/YourName/
├── profile.yaml    # Your personal info
├── resume.pdf      # Your resume (auto-detected)
└── jobs/
    └── jobs.json   # Job listings to apply to
```

**Resume Auto-Detection**: Place `resume.pdf` in your profile folder and it will be automatically detected. Alternatively, specify an absolute path in `profile.yaml`.

The profile includes fields for:
- Personal info (name, email, phone, LinkedIn, GitHub)
- Location and relocation preferences
- Work authorization status
- Experience and education
- Salary expectations
- EEOC/Diversity responses (optional)
- Custom Q&A for company-specific questions

### Custom Q&A Learning System

Hermes learns from questions it can't answer:

1. **During run**: Unknown questions are saved to `custom_answers.pending` in your profile
2. **After run**: Open `profile.yaml` and fill in the `answer` field for pending questions
3. **Next run**: Answered questions are automatically promoted to `custom_answers.answered`

```yaml
custom_answers:
  answered:
    - question: "Have you worked for this company before?"
      answer: "No"
      keywords: ["worked for", "employed by"]  # Auto-matched in future

  pending:
    - question: "What is your notice period?"
      answer: ""  # Fill this in!
      encountered_at: "2024-01-15 10:30"
      job: "Software Engineer at Acme"
```

### 2. Set up API key (optional, for LLM features)

**Option A: Using `.env` file (recommended)**

```bash
# Copy the example file
cp .env.example .env

# Edit .env and add your API key
```

Your `.env` file:
```
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx

# Optional: Override profile values at runtime
HERMES_EMAIL=override@example.com
HERMES_PHONE=555-999-8888
```

**Option B: Using environment variable**

```bash
export ANTHROPIC_API_KEY="your-api-key"
```

### Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `ANTHROPIC_API_KEY` | Claude API key for LLM-assisted form filling | Optional |
| `HERMES_EMAIL` | Override profile email at runtime | Optional |
| `HERMES_PHONE` | Override profile phone at runtime | Optional |

### 3. Launch Chrome with debugging

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir=/tmp/chrome-hermes
```

On Linux:
```bash
google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-hermes
```

On Windows:
```cmd
"C:\Program Files\Google\Chrome\Application\chrome.exe" ^
  --remote-debugging-port=9222 ^
  --user-data-dir=%TEMP%\chrome-hermes
```

## Usage

### Running Modes

Hermes has two main modes controlled by the `--auto-pilot` flag:

| Mode | Command | Behavior |
|------|---------|----------|
| **Default** | `python run.py --profile YourName` | Fill form → Human reviews → Human clicks submit |
| **Auto-Pilot** | `python run.py --profile YourName --auto-pilot` | Fill form → Auto-submit (no human review) |

### LLM Helper (Optional)

LLM helper uses Claude API to answer questions that can't be filled from your profile:

| Mode | Setup | Behavior |
|------|-------|----------|
| **With LLM** | Set `ANTHROPIC_API_KEY` in `.env` | Profile → Custom Answers → LLM fallback |
| **Without LLM** | No API key (or comment it out) | Profile → Custom Answers only |

To disable LLM temporarily, comment out the key in `.env`:
```bash
# ANTHROPIC_API_KEY=sk-ant-...  (commented = LLM disabled)
```

### Mode Comparison

| Scenario | Auto-Pilot | LLM | Command |
|----------|------------|-----|---------|
| **Recommended** | No | Yes | `python run.py --profile YourName` (with API key) |
| Safe testing | No | No | `python run.py --profile YourName` |
| Full automation | Yes | Yes | `python run.py --profile YourName --auto-pilot` |

> **💡 Tip**: Start with the recommended mode (no auto-pilot, with LLM) until you're confident the tool works well with your profile and target job sites.

### Quick Start Examples

```bash
# 1. Default mode (human review, no LLM)
#    - Comment out ANTHROPIC_API_KEY in .env
python run.py --profile YourName

# 2. Default mode with LLM helper
#    - Set ANTHROPIC_API_KEY in .env
python run.py --profile YourName

# 3. Auto-pilot mode (NOT recommended until thoroughly tested!)
#    ⚠️  Always test with human review first before using auto-pilot
python run.py --profile YourName --auto-pilot

# 4. Batch mode with job list
python run.py --profile YourName --jobs config/profiles/YourName/jobs/jobs.json
```

### Interactive Mode

Navigate to a job application page in Chrome, then run:

```bash
python run.py --profile YourName
```

Hermes will detect the current page and fill the form.

### Batch Mode

Add job listings to your profile's jobs.json:

```json
[
  {
    "url": "https://jobs.lever.co/company/job-id",
    "title": "Software Engineer",
    "company": "Acme Inc"
  },
  {
    "url": "https://boards.greenhouse.io/company/jobs/123",
    "title": "Senior Developer",
    "company": "Tech Corp"
  }
]
```

Then run:

```bash
# Using your profile's job list
python run.py --profile YourName --jobs config/profiles/YourName/jobs/jobs.json

# Or specify any jobs file
python run.py --profile YourName --jobs path/to/jobs.json
```

### Command Line Options

```
usage: run.py [-h] [--jobs JOBS_FILE] [--profile PROFILE_NAME] [--profile-path PATH]
              [--cdp-url CDP_URL] [--auto-pilot] [--list-profiles]

Hermes - Job Application Automation Agent

options:
  -h, --help              Show this help message and exit
  --jobs, -j JOBS_FILE    Path to JSON file with job listings
  --profile, -p NAME      Profile name (e.g., 'default', 'John')
  --profile-path PATH     Direct path to profile YAML file (overrides --profile)
  --cdp-url CDP_URL       Chrome DevTools Protocol URL (default: http://localhost:9222)
  --auto-pilot            Auto-submit after filling (use with caution)
  --list-profiles         List available profiles and exit
```

### List Available Profiles

```bash
python run.py --list-profiles
```

## How It Works

1. **Connect**: Hermes connects to your Chrome browser via CDP
2. **Navigate**: Opens the job application URL
3. **Detect**: Identifies the ATS platform (Greenhouse, Lever, Ashby, etc.)
4. **Extract**: Finds all form fields, including those in embedded iframes
5. **Map**: Matches fields to 43 semantic types (name, email, phone, etc.)
6. **Fill**: Populates fields using tiered lookup:
   - Profile values (exact field type match)
   - Custom answers (keyword matching)
   - LLM fallback (if API key set)
7. **Dynamic Fields**: Re-scans for fields that appear after initial fill
8. **Review**: Shows summary with high-risk fields highlighted
9. **Confirm**: Waits for your approval before submitting (unless --auto-pilot)

## Supported ATS Platforms

- Lever
- Greenhouse
- Ashby
- Workday
- iCIMS
- Taleo
- BambooHR
- Jobvite
- SmartRecruiters
- Generic forms

## High-Risk Fields

The following fields are flagged for extra attention:

- Work authorization status
- Visa sponsorship requirements
- Salary expectations
- EEOC/Diversity questions (gender, ethnicity, veteran status, disability)

### EEOC/Diversity Field Handling

EEOC fields are legally voluntary. Hermes uses a safe handling strategy:

1. **Preferred value**: If your profile value matches an option, it's selected
2. **Decline fallback**: If no match, looks for "Decline to answer" options
3. **Skip if unsafe**: If no safe option found, field is left untouched

Decline options recognized (in order of preference):
- "I do not wish to disclose"
- "Decline to answer"
- "Prefer not to say"
- "Decline to self-identify"

## Logs

Session logs are stored in `logs/<YYYYMMDD_HHMMSS>/`:

- `session.json` - Detailed JSON log with all field values and status
- `*.png` - Screenshots at key stages (initial, after_apply, after_fill, pre_submit, after_submit)

**Auto-cleanup**: Only the last 10 session logs are kept. Older sessions are automatically deleted.

## Project Structure

```
Hermes/
├── hermes/
│   ├── __init__.py         # Package init
│   ├── config.py           # Profile loading
│   ├── browser.py          # CDP connection
│   ├── ats_detector.py     # ATS detection
│   ├── field_mapping.py    # Semantic field patterns
│   ├── form_filler.py      # Form filling logic
│   ├── llm_helper.py       # Claude integration
│   ├── confirmation.py     # CLI confirmation UI
│   └── logger.py           # Session logging
├── config/
│   └── profiles/
│       ├── default/        # Template profile (copy this!)
│       │   ├── profile.yaml
│       │   ├── resume.pdf  # Place your resume here
│       │   └── jobs/
│       │       └── jobs.json
│       └── YourName/       # Your personal profile
│           ├── profile.yaml
│           ├── resume.pdf
│           └── jobs/
│               └── jobs.json
├── logs/                   # Session logs (auto-cleanup, keeps last 10)
├── run.py                  # Main entry point
├── requirements.txt
├── .env.example            # Environment template
└── README.md
```

## Safety Features

- **Human Review by Default**: Requires confirmation before submit (unless --auto-pilot)
- **Rule-Based First**: Profile → Custom Answers → LLM (minimizes API calls)
- **High-Risk Flagging**: Alerts on sensitive fields (work auth, salary, EEOC)
- **Screenshot Audit**: Visual record of filled forms at each stage
- **Graceful Degradation**: Skips problematic jobs, continues with others
- **EEO Safe Handling**: Falls back to "Decline to answer" for sensitive questions

## Troubleshooting

### "Failed to connect to Chrome"

Make sure Chrome is running with the `--remote-debugging-port=9222` flag.

### "No form fields detected"

The page might require interaction (clicking "Apply" button, etc.). Navigate to the actual application form and try again.

### LLM features not working

Add your API key to `.env` file or set the `ANTHROPIC_API_KEY` environment variable.

## License

MIT

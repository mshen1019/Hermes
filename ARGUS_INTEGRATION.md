# Argus Integration Guide

This guide explains how to use Hermes with job listings collected by Argus.

## Overview

The `apply_argus_jobs.py` script processes job listings from your Argus `job_results` directory and applies to them company by company using Hermes.

## Prerequisites

1. **Chrome with CDP enabled**
   ```bash
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
     --remote-debugging-port=9222 \
     --user-data-dir=/tmp/chrome-hermes
   ```

2. **Hermes profile configured**
   - Make sure your profile exists in `config/profiles/YourName/`
   - Profile should have your resume and all required info

3. **API key (optional but recommended)**
   - Set `ANTHROPIC_API_KEY` in `.env` file for LLM-assisted filling

## Quick Start

### 1. List all available companies

```bash
python apply_argus_jobs.py /Users/mingshen/workspace/Argus/job_results/Ming --list
```

This shows:
- All companies with job listings
- Number of jobs per company
- Total jobs available

### 2. Test with a few jobs

Start with a small test to verify everything works:

```bash
python apply_argus_jobs.py \
  /Users/mingshen/workspace/Argus/job_results/Ming \
  --profile Ming \
  --max-jobs 2 \
  --companies Anthropic
```

This applies to only 2 jobs at Anthropic.

### 3. Apply to specific companies

```bash
python apply_argus_jobs.py \
  /Users/mingshen/workspace/Argus/job_results/Ming \
  --profile Ming \
  --companies Google Anthropic OpenAI Meta
```

### 4. Interactive mode (recommended)

Use interactive mode to have control between companies:

```bash
python apply_argus_jobs.py \
  /Users/mingshen/workspace/Argus/job_results/Ming \
  --profile Ming \
  --interactive
```

This will:
- Show you a summary of all companies
- Ask for confirmation before starting
- Ask for confirmation before each company
- Let you stop at any time

### 5. Apply to all companies

```bash
python apply_argus_jobs.py \
  /Users/mingshen/workspace/Argus/job_results/Ming \
  --profile Ming
```

## Command Line Options

```
usage: apply_argus_jobs.py [-h] [--profile PROFILE_NAME] [--profile-path PATH]
                           [--cdp-url CDP_URL] [--auto-pilot]
                           [--companies COMPANY [COMPANY ...]]
                           [--max-jobs N] [--interactive] [--list]
                           argus_dir

positional arguments:
  argus_dir             Path to Argus job_results directory

optional arguments:
  -h, --help            Show help message
  --profile, -p         Profile name (e.g., 'Ming')
  --profile-path        Direct path to profile YAML file
  --cdp-url             Chrome DevTools Protocol URL (default: http://localhost:9222)
  --auto-pilot          Auto-submit after filling (NOT recommended)
  --companies, -c       Only apply to specific companies
  --max-jobs N          Maximum jobs per company (useful for testing)
  --interactive, -i     Ask for confirmation before each company
  --list                List all companies and exit
```

## How It Works

1. **Discovery**: Scans the Argus directory structure:
   ```
   Argus/job_results/Ming/
   ├── 2026-01-24/
   │   ├── Google/
   │   │   └── jobs.json
   │   ├── Anthropic/
   │   │   └── jobs.json
   │   └── ...
   └── 2026-01-25/
       ├── Meta/
       │   └── jobs.json
       └── ...
   ```

2. **Processing**: For each company:
   - Loads all jobs from `jobs.json`
   - Applies to each job sequentially
   - Captures screenshots and logs results

3. **Review**: For each job (unless `--auto-pilot`):
   - Hermes fills the form
   - Shows you a summary with high-risk fields highlighted
   - Waits for you to review and manually submit

4. **Logging**: Creates session logs in `logs/YYYYMMDD_HHMMSS/`:
   - `session.json` - Detailed application log
   - Screenshots at each stage
   - Success/failure status for each job

## Workflow Examples

### Testing Workflow (Recommended First Time)

```bash
# 1. List companies
python apply_argus_jobs.py /Users/mingshen/workspace/Argus/job_results/Ming --list

# 2. Test with 1 company, 2 jobs max
python apply_argus_jobs.py \
  /Users/mingshen/workspace/Argus/job_results/Ming \
  --profile Ming \
  --companies Anthropic \
  --max-jobs 2

# 3. Review the logs/screenshots to verify quality

# 4. Expand to more companies once confident
python apply_argus_jobs.py \
  /Users/mingshen/workspace/Argus/job_results/Ming \
  --profile Ming \
  --companies Anthropic OpenAI Google \
  --max-jobs 5
```

### Production Workflow

```bash
# Apply to all top-tier companies with human review
python apply_argus_jobs.py \
  /Users/mingshen/workspace/Argus/job_results/Ming \
  --profile Ming \
  --companies Anthropic OpenAI Google Meta DeepMind \
  --interactive
```

### Batch Processing (Advanced)

For processing many companies, split into sessions:

```bash
# Session 1: Top AI companies
python apply_argus_jobs.py \
  /Users/mingshen/workspace/Argus/job_results/Ming \
  --profile Ming \
  --companies Anthropic OpenAI Google DeepMind xAI

# Session 2: Tech giants
python apply_argus_jobs.py \
  /Users/mingshen/workspace/Argus/job_results/Ming \
  --profile Ming \
  --companies Meta Amazon Microsoft

# Session 3: Startups
python apply_argus_jobs.py \
  /Users/mingshen/workspace/Argus/job_results/Ming \
  --profile Ming \
  --companies Scale_AI Perplexity_AI Mistral_AI
```

## Tips

1. **Start small**: Always test with `--max-jobs 2` first
2. **Use interactive mode**: Gives you control to stop/skip companies
3. **Review logs**: Check `logs/` after each session to verify quality
4. **Monitor Chrome**: Keep Chrome visible to see what's happening
5. **Take breaks**: The script adds delays between jobs and companies
6. **Check custom answers**: Unknown questions are saved to `profile.yaml` for next time

## Troubleshooting

### No companies found
```bash
# Verify the directory structure
ls /Users/mingshen/workspace/Argus/job_results/Ming/2026-*/*/jobs.json
```

### Browser connection failed
```bash
# Restart Chrome with CDP
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir=/tmp/chrome-hermes
```

### Jobs not loading
- Check that `jobs.json` files have the correct format
- Each job should have: `company`, `title`, `url`

### Form not filling
- Some job sites may have changed their structure
- Check the logs to see which fields were detected
- Try navigating to the form manually first

## Safety Features

- **Human review by default**: You must manually submit unless `--auto-pilot`
- **High-risk flagging**: Work auth, EEOC, salary fields are highlighted
- **Screenshot audit**: Every job gets screenshots for review
- **Session logging**: Full JSON logs of all applications
- **Graceful errors**: Failed jobs don't stop the entire batch

## Logs and Results

After running, check:

```bash
# View latest session
ls -lt logs/ | head -5

# Open session directory
open logs/20260129_143022/

# View session report
cat logs/20260129_143022/session.json | jq .
```

Each session contains:
- `session.json` - Structured log with all applications
- `*.png` - Screenshots for each job (initial, after_fill, etc.)
- Success/failure status for each application

## Performance

- **Speed**: ~2-3 minutes per job (with human review)
- **Accuracy**: Depends on ATS platform and form complexity
- **Batch size**: Process 20-30 jobs per session comfortably
- **Breaks**: Script adds 3s between jobs, 5s between companies

## Auto-Pilot Mode (Not Recommended)

If you're confident everything works, you can use auto-pilot:

```bash
python apply_argus_jobs.py \
  /Users/mingshen/workspace/Argus/job_results/Ming \
  --profile Ming \
  --auto-pilot
```

**Warning**: This will auto-submit all forms without review. Only use after extensive testing!

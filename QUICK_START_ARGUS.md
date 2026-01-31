# Quick Start: Argus + Hermes Integration

## Setup (One-time)

1. **Start Chrome with CDP**
   ```bash
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
     --remote-debugging-port=9222 \
     --user-data-dir=/tmp/chrome-hermes
   ```

2. **Verify your profile**
   ```bash
   python3 run.py --list-profiles
   ```

## Usage

### See what's available
```bash
python3 apply_argus_jobs.py /Users/mingshen/workspace/Argus/job_results/Ming --list
```

### Apply to specific companies (recommended)
```bash
python3 apply_argus_jobs.py \
  /Users/mingshen/workspace/Argus/job_results/Ming \
  --profile Ming \
  --companies Anthropic OpenAI
```

### Apply with interactive confirmations
```bash
python3 apply_argus_jobs.py \
  /Users/mingshen/workspace/Argus/job_results/Ming \
  --profile Ming \
  --interactive
```

### Test with limited jobs
```bash
python3 apply_argus_jobs.py \
  /Users/mingshen/workspace/Argus/job_results/Ming \
  --profile Ming \
  --companies Anthropic \
  --max-jobs 2
```

## What Happens

1. Script loads all jobs for selected companies
2. For each job:
   - Navigates to application page
   - Detects ATS platform
   - Fills form fields
   - Shows you a summary
   - **YOU review and manually submit**
3. Logs everything with screenshots

## Your Companies (712 jobs total)

### Top AI Labs
- **Anthropic**: 19 jobs
- **OpenAI**: 23 jobs
- **DeepMind**: 12 jobs
- **xAI**: 6 jobs
- **Mistral AI**: 2 jobs
- **Perplexity AI**: 3 jobs

### Big Tech
- **Google**: 75 jobs
- **Meta**: 105 jobs
- **Amazon**: 69 jobs
- **TikTok**: 227 jobs

### AI Infrastructure
- **Scale AI**: 13 jobs
- **Databricks**: 6 jobs
- **Snowflake**: 3 jobs

### Tech Companies
- **Uber**: 23 jobs
- **Airbnb**: 3 jobs
- **DoorDash**: 7 jobs
- **Instacart**: 12 jobs
- **Lyft**: 12 jobs
- **Spotify**: 1 job
- **Roblox**: 29 jobs
- **Pinterest**: 13 jobs

### Fintech
- **Stripe**: 8 jobs
- **Plaid**: 6 jobs
- **Coinbase**: 9 jobs
- **Block**: 18 jobs
- **Brex**: 1 job
- **SoFi**: 4 jobs

### Other
- **Confluent**: 1 job
- **MongoDB**: 1 job
- **Jane Street**: 1 job

## Recommended Strategy

### Day 1: Test + Top Priority (AI Labs)
```bash
# Test run (2 jobs)
python3 apply_argus_jobs.py \
  /Users/mingshen/workspace/Argus/job_results/Ming \
  --profile Ming \
  --companies Anthropic \
  --max-jobs 2

# If successful, do AI labs
python3 apply_argus_jobs.py \
  /Users/mingshen/workspace/Argus/job_results/Ming \
  --profile Ming \
  --companies Anthropic OpenAI DeepMind xAI \
  --interactive
```

### Day 2: Big Tech
```bash
python3 apply_argus_jobs.py \
  /Users/mingshen/workspace/Argus/job_results/Ming \
  --profile Ming \
  --companies Google Meta \
  --max-jobs 10 \
  --interactive
```

### Day 3: Infrastructure + Startups
```bash
python3 apply_argus_jobs.py \
  /Users/mingshen/workspace/Argus/job_results/Ming \
  --profile Ming \
  --companies Scale_AI Databricks Snowflake Perplexity_AI Mistral_AI
```

### Day 4: Tech Companies
```bash
python3 apply_argus_jobs.py \
  /Users/mingshen/workspace/Argus/job_results/Ming \
  --profile Ming \
  --companies Uber Airbnb DoorDash Roblox Pinterest
```

### Day 5: Fintech
```bash
python3 apply_argus_jobs.py \
  /Users/mingshen/workspace/Argus/job_results/Ming \
  --profile Ming \
  --companies Stripe Plaid Coinbase Block
```

## Tips

- ✅ Start with `--max-jobs 2` to test
- ✅ Use `--interactive` for control
- ✅ Review logs after each session
- ✅ Keep Chrome window visible
- ❌ Don't use `--auto-pilot` until thoroughly tested
- 💡 Unknown questions are saved to profile for future use

## Check Results

```bash
# View latest session
ls -lt logs/ | head -5

# Open session folder
open logs/$(ls -t logs/ | head -1)/

# View session JSON
cat logs/$(ls -t logs/ | head -1)/session.json | python3 -m json.tool
```

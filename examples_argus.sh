#!/bin/bash
# Example commands for using Hermes with Argus job listings
# Make sure Chrome is running with CDP first!

ARGUS_DIR="/Users/mingshen/workspace/Argus/job_results/Ming"
PROFILE="Ming"

# =============================================================================
# DISCOVERY - What jobs are available?
# =============================================================================

echo "=== List all companies ==="
python3 apply_argus_jobs.py "$ARGUS_DIR" --list

echo -e "\n=== AI companies only ==="
python3 generate_company_list.py "$ARGUS_DIR" --category ai

echo -e "\n=== Big tech companies ==="
python3 generate_company_list.py "$ARGUS_DIR" --category bigtech

echo -e "\n=== Fintech companies ==="
python3 generate_company_list.py "$ARGUS_DIR" --category fintech

echo -e "\n=== Companies with ML/Research roles ==="
python3 generate_company_list.py "$ARGUS_DIR" --keywords ML Research --show-jobs

echo -e "\n=== Companies with 10+ jobs ==="
python3 generate_company_list.py "$ARGUS_DIR" --min-jobs 10

# =============================================================================
# TESTING - Start small to verify everything works
# =============================================================================

echo -e "\n=== Test: Apply to 2 jobs at Anthropic ==="
python3 apply_argus_jobs.py "$ARGUS_DIR" \
  --profile "$PROFILE" \
  --companies Anthropic \
  --max-jobs 2

# =============================================================================
# SELECTIVE APPLICATION - Apply to specific companies
# =============================================================================

echo -e "\n=== Top AI labs ==="
python3 apply_argus_jobs.py "$ARGUS_DIR" \
  --profile "$PROFILE" \
  --companies Anthropic OpenAI DeepMind xAI \
  --interactive

echo -e "\n=== AI infrastructure companies ==="
python3 apply_argus_jobs.py "$ARGUS_DIR" \
  --profile "$PROFILE" \
  --companies Scale_AI Databricks

echo -e "\n=== Top tech companies (with job limit) ==="
python3 apply_argus_jobs.py "$ARGUS_DIR" \
  --profile "$PROFILE" \
  --companies Google Meta Amazon \
  --max-jobs 10 \
  --interactive

echo -e "\n=== Fintech companies ==="
python3 apply_argus_jobs.py "$ARGUS_DIR" \
  --profile "$PROFILE" \
  --companies Stripe Plaid Coinbase Block Brex

# =============================================================================
# BATCH PROCESSING - Process multiple companies
# =============================================================================

echo -e "\n=== Interactive mode (ask before each company) ==="
python3 apply_argus_jobs.py "$ARGUS_DIR" \
  --profile "$PROFILE" \
  --interactive

echo -e "\n=== All companies (no confirmation) ==="
python3 apply_argus_jobs.py "$ARGUS_DIR" \
  --profile "$PROFILE"

# =============================================================================
# ADVANCED - Custom company lists
# =============================================================================

echo -e "\n=== Generate custom list and use it ==="
python3 generate_company_list.py "$ARGUS_DIR" \
  --category ai \
  --min-jobs 5 \
  --output /tmp/ai_companies.txt

# Read companies from file and apply
python3 apply_argus_jobs.py "$ARGUS_DIR" \
  --profile "$PROFILE" \
  --companies $(cat /tmp/ai_companies.txt)

# =============================================================================
# MONITORING - Check results
# =============================================================================

echo -e "\n=== View latest session logs ==="
ls -lt logs/ | head -10

echo -e "\n=== Open latest session folder ==="
open "logs/$(ls -t logs/ | head -1)/"

echo -e "\n=== View session summary ==="
cat "logs/$(ls -t logs/ | head -1)/session.json" | python3 -m json.tool | grep -A5 "summary"

# =============================================================================
# DAILY WORKFLOW EXAMPLES
# =============================================================================

echo -e "\n=== Day 1: Test + Priority AI companies ==="
# Morning: Test run
python3 apply_argus_jobs.py "$ARGUS_DIR" \
  --profile "$PROFILE" \
  --companies Anthropic \
  --max-jobs 2

# Afternoon: Full AI labs
python3 apply_argus_jobs.py "$ARGUS_DIR" \
  --profile "$PROFILE" \
  --companies Anthropic OpenAI DeepMind xAI Perplexity_AI Mistral_AI \
  --interactive

echo -e "\n=== Day 2: Big Tech (limited) ==="
python3 apply_argus_jobs.py "$ARGUS_DIR" \
  --profile "$PROFILE" \
  --companies Google Meta Amazon \
  --max-jobs 15 \
  --interactive

echo -e "\n=== Day 3: AI Infrastructure ==="
python3 apply_argus_jobs.py "$ARGUS_DIR" \
  --profile "$PROFILE" \
  --companies Scale_AI Databricks Snowflake

echo -e "\n=== Day 4: Tech Companies ==="
python3 apply_argus_jobs.py "$ARGUS_DIR" \
  --profile "$PROFILE" \
  --companies Uber Airbnb DoorDash Instacart Lyft Roblox Pinterest

echo -e "\n=== Day 5: Fintech ==="
python3 apply_argus_jobs.py "$ARGUS_DIR" \
  --profile "$PROFILE" \
  --companies Stripe Plaid Coinbase Block Brex SoFi

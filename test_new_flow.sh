#!/bin/bash
# Test the new automatic submission detection flow

echo "=========================================="
echo "  Testing New Flow (No Terminal Prompt)"
echo "=========================================="
echo ""
echo "This will test the new workflow:"
echo "  1. Form fills automatically"
echo "  2. Summary shows in terminal"
echo "  3. You click Submit in Chrome"
echo "  4. Script auto-detects and moves to next job"
echo ""
echo "Testing with 2 Anthropic jobs..."
echo ""
sleep 2

cd /Users/mingshen/workspace/Hermes
python3 apply_argus_jobs.py \
  /Users/mingshen/workspace/Argus/job_results/Ming \
  --profile Ming \
  --companies Anthropic \
  --max-jobs 2

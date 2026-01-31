#!/bin/bash
cd /Users/mingshen/workspace/Hermes

echo "=========================================="
echo "  Starting Job Applications"
echo "=========================================="
echo ""
echo "Chrome is running at: http://localhost:9222"
echo "Profile: Ming"
echo "Companies: Anthropic (2 jobs for testing)"
echo ""
echo "For each job, you will:"
echo "  1. See the form being filled"
echo "  2. Review a summary of all fields"
echo "  3. Confirm to proceed (type 'y')"
echo "  4. MANUALLY click Submit in the browser"
echo ""
echo "Starting in 3 seconds..."
sleep 3

python3 apply_argus_jobs.py \
  /Users/mingshen/workspace/Argus/job_results/Ming \
  --profile Ming \
  --companies Anthropic \
  --max-jobs 2

echo ""
echo "=========================================="
echo "  Application session complete!"
echo "=========================================="
echo ""
echo "Check logs at: logs/$(ls -t logs/ | head -1)"

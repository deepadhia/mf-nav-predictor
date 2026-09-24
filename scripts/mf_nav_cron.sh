#!/usr/bin/env bash
# ==============================================================================
# Mutual Fund Intraday NAV Predictor - Automated Cron Execution Wrapper
# Runs on Oracle Cloud VM at 2:00 PM & 2:15 PM IST (08:30 & 08:45 UTC) Monday-Friday
# ==============================================================================

set -e

# Determine script directory & project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

# Create logs directory if it doesn't exist
mkdir -p "${PROJECT_ROOT}/logs"
LOG_FILE="${PROJECT_ROOT}/logs/nav_$(date +'%Y-%m-%d').log"

echo "==================================================================" >> "${LOG_FILE}"
echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Starting MF NAV Intraday Predictor" >> "${LOG_FILE}"
echo "==================================================================" >> "${LOG_FILE}"

# Activate virtual environment
if [ -f "${PROJECT_ROOT}/.venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source "${PROJECT_ROOT}/.venv/bin/activate"
else
    echo "ERROR: Virtual environment not found at ${PROJECT_ROOT}/.venv" >> "${LOG_FILE}"
    exit 1
fi

# Run predictor
python src/main.py >> "${LOG_FILE}" 2>&1
EXIT_CODE=$?

echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Completed with exit code ${EXIT_CODE}" >> "${LOG_FILE}"
echo "" >> "${LOG_FILE}"

exit ${EXIT_CODE}

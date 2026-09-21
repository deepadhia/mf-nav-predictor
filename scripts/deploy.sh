#!/usr/bin/env bash
# ==============================================================================
# One-Command Pull & Deploy Script for MF NAV Predictor on Oracle Cloud VM
# Usage: ./scripts/deploy.sh [--test-telegram]
# ==============================================================================

set -e

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

echo -e "${CYAN}==================================================================${NC}"
echo -e "${CYAN}  PULL & DEPLOY: MUTUAL FUND INTRADAY NAV PREDICTOR               ${NC}"
echo -e "${CYAN}==================================================================${NC}\n"

# 1. Pull latest changes from origin main
echo -e "${YELLOW}[1/4] Pulling latest code from origin main...${NC}"
git pull origin main

# 2. Run automated server setup (venv, deps, crontabs, Groww seeding)
echo -e "\n${YELLOW}[2/4] Running setup & updating crontab schedules...${NC}"
chmod +x "${PROJECT_ROOT}/scripts/setup_oracle.sh"
chmod +x "${PROJECT_ROOT}/scripts/mf_nav_cron.sh"
"${PROJECT_ROOT}/scripts/setup_oracle.sh"

# 3. Test Telegram connection if requested or as verification
if [ "$1" == "--test-telegram" ] || [ "$1" == "-t" ]; then
    echo -e "\n${YELLOW}[3/4] Dispatching test notification to Telegram...${NC}"
    "${PROJECT_ROOT}/.venv/bin/python" "${PROJECT_ROOT}/scripts/test_telegram.py"
else
    echo -e "\n${YELLOW}[3/4] Testing Telegram bot connection...${NC}"
    "${PROJECT_ROOT}/.venv/bin/python" "${PROJECT_ROOT}/scripts/test_telegram.py"
fi

# 4. Status summary
echo -e "\n${GREEN}==================================================================${NC}"
echo -e "${GREEN}  DEPLOYMENT SUCCESSFUL & FULLY ACTIVE!                           ${NC}"
echo -e "${GREEN}==================================================================${NC}\n"
echo -e "• ${CYAN}Check 1:${NC} 1:00 PM IST (07:30 UTC) Mon–Fri"
echo -e "• ${CYAN}Check 2:${NC} 1:45 PM IST (08:15 UTC) Mon–Fri"
echo -e "• ${CYAN}Auto-Refresh Disclosures:${NC} Every 10 days (1st, 11th, 21st at 06:00 UTC)"
echo -e "• ${CYAN}Logs:${NC} ${PROJECT_ROOT}/logs/nav_\$(date +'%Y-%m-%d').log\n"

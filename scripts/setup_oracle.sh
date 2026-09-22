#!/usr/bin/env bash
# ==============================================================================
# Oracle Cloud Instance Setup Script for Mutual Fund Intraday NAV Predictor
# ==============================================================================

set -e

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}==================================================================${NC}"
echo -e "${CYAN}  MUTUAL FUND NAV TRACKER - ORACLE SERVER SETUP SCRIPT           ${NC}"
echo -e "${CYAN}==================================================================${NC}\n"

# 1. Check Python installation
echo -e "${YELLOW}[1/5] Checking Python 3 and venv...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python 3 is not installed. Installing python3 and python3-venv...${NC}"
    sudo apt update && sudo apt install -y python3 python3-venv python3-pip cron
fi

# Ensure python3-venv is installed on Debian/Ubuntu
if ! dpkg -s python3-venv &> /dev/null && [ -f /etc/debian_version ]; then
    echo -e "${YELLOW}Installing python3-venv package...${NC}"
    sudo apt update && sudo apt install -y python3-venv python3-pip
fi

# 2. Set up virtual environment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

echo -e "${YELLOW}[2/5] Creating Python virtual environment in .venv...${NC}"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 3. Create required directories
echo -e "${YELLOW}[3/5] Setting up directories & permissions...${NC}"
mkdir -p "${PROJECT_ROOT}/logs"
mkdir -p "${PROJECT_ROOT}/cache"
chmod +x "${PROJECT_ROOT}/scripts/mf_nav_cron.sh"

# 4. Check .env configuration
echo -e "${YELLOW}[4/5] Checking configuration (.env)...${NC}"
if [ ! -f "${PROJECT_ROOT}/.env" ]; then
    if [ -f "${PROJECT_ROOT}/.env.example" ]; then
        cp "${PROJECT_ROOT}/.env.example" "${PROJECT_ROOT}/.env"
        echo -e "${YELLOW}Created .env from .env.example. Please edit .env with your credentials.${NC}"
    else
        echo -e "${RED}Warning: .env file missing! Create .env in ${PROJECT_ROOT}${NC}"
    fi
else
    echo -e "${GREEN}[OK] .env file detected.${NC}"
fi

# Seed initial mutual fund disclosures from Groww
echo -e "${YELLOW}Fetching initial live portfolio disclosures from Groww...${NC}"
python3 src/holdings_scraper.py --fund all || true

# 5. Configure Crontab:
#    (a) Run 1: 1:30 PM IST (08:00 UTC Mon-Fri) - Early Pulse Check
#    (b) Run 2: 2:30 PM IST (09:00 UTC Mon-Fri) - Final Check before 3:00 PM Same-Day Cutoff
#    (c) Nightly Accuracy Reconciliation: 11:30 PM IST (18:00 UTC Mon-Fri) - Audits actual published NAVs
#    (d) Disclosures Auto-Refresher every 10 days (1st, 11th, 21st of each month at 06:00 UTC)
#    Note: Telegram alert only fires if movement >= 1.0% (zero spam on normal days)
echo -e "${YELLOW}[5/5] Configuring Crontab schedules (1:30 PM, 2:30 PM Cutoff & 11:30 PM Nightly Reconciler)...${NC}"
CRON_RUN1_SCHEDULE="0 8 * * 1-5"
CRON_RUN2_SCHEDULE="0 9 * * 1-5"
CRON_DAILY_CMD="${PROJECT_ROOT}/scripts/mf_nav_cron.sh"

CRON_RECONCILE_SCHEDULE="0 18 * * 1-5"
CRON_RECONCILE_CMD="${PROJECT_ROOT}/.venv/bin/python ${PROJECT_ROOT}/src/reconciler.py >> ${PROJECT_ROOT}/logs/reconciler_\$(date +\\%Y-\\%m).log 2>&1"

CRON_REFRESH_SCHEDULE="0 6 1,11,21 * *"
CRON_REFRESH_CMD="${PROJECT_ROOT}/.venv/bin/python ${PROJECT_ROOT}/src/holdings_scraper.py --fund all >> ${PROJECT_ROOT}/logs/scraper_\$(date +\\%Y-\\%m).log 2>&1"

CURRENT_CRON=$(crontab -l 2>/dev/null || true)
NEW_CRON="${CURRENT_CRON}"

# Remove any old schedules
NEW_CRON=$(echo "${NEW_CRON}" | grep -v "mf_nav_cron.sh" | grep -v "holdings_scraper.py" | grep -v "reconciler.py" || true)

NEW_CRON=$(echo -e "${NEW_CRON}\n# Run 1: MF Intraday Predictor at 1:30 PM IST (Mon-Fri)\n${CRON_RUN1_SCHEDULE} ${CRON_DAILY_CMD}\n# Run 2: MF Intraday Predictor at 2:30 PM IST (Mon-Fri) - Final Cutoff Check\n${CRON_RUN2_SCHEDULE} ${CRON_DAILY_CMD}\n# Nightly NAV Accuracy Reconciler at 11:30 PM IST (Mon-Fri)\n${CRON_RECONCILE_SCHEDULE} ${CRON_RECONCILE_CMD}\n# Auto-refresh mutual fund disclosures every 10 days (1st, 11th, 21st)\n${CRON_REFRESH_SCHEDULE} ${CRON_REFRESH_CMD}")

echo -e "${GREEN}[OK] Added Crontab Check 1 (1:30 PM IST / 08:00 UTC)${NC}"
echo -e "${GREEN}[OK] Added Crontab Check 2 (2:30 PM IST / 09:00 UTC)${NC}"
echo -e "${GREEN}[OK] Added Nightly Accuracy Reconciler (11:30 PM IST / 18:00 UTC)${NC}"
echo -e "${GREEN}[OK] Added Disclosures Auto-Refresh (Every 10 days: 1st, 11th, 21st of month)${NC}"

echo "${NEW_CRON}" | sed '/^$/N;/^\n$/D' | crontab -


# Ensure cron daemon is running
if command -v systemctl &> /dev/null; then
    sudo systemctl enable cron || true
    sudo systemctl start cron || true
fi


echo -e "\n${GREEN}==================================================================${NC}"
echo -e "${GREEN}  DEPLOYMENT SETUP COMPLETE!                                      ${NC}"
echo -e "${GREEN}==================================================================${NC}\n"
echo -e "You can test a manual execution anytime using:"
echo -e "  ${CYAN}${PROJECT_ROOT}/scripts/mf_nav_cron.sh${NC}\n"
echo -e "To view execution logs:"
echo -e "  ${CYAN}cat ${PROJECT_ROOT}/logs/nav_\$(date +'%Y-%m-%d').log${NC}\n"

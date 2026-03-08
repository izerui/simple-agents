#!/bin/bash

# Kill LangGraph Development Server
# This script stops any existing server on port 2024

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Checking for processes on port 2024...${NC}"

if lsof -i tcp:2024 >/dev/null 2>&1; then
    echo -e "${YELLOW}Found process(es) using port 2024:${NC}"
    lsof -i tcp:2024
    echo ""
    echo -e "${YELLOW}Terminating...${NC}"
    lsof -ti tcp:2024 | xargs kill -9
    sleep 1

    if lsof -i tcp:2024 >/dev/null 2>&1; then
        echo -e "${RED}Failed to kill process on port 2024${NC}"
        exit 1
    else
        echo -e "${GREEN}✓ Process(es) terminated, port 2024 is now free${NC}"
    fi
else
    echo -e "${GREEN}✓ No process using port 2024${NC}"
fi

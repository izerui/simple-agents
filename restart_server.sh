#!/bin/bash

# LangGraph Development Server - Kill & Restart
# This script stops any existing server on port 2024 and starts a fresh one

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Print banner
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  LangGraph Development Server${NC}"
echo -e "${BLUE}  Kill & Restart${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# ========================================
# Step 1: Kill existing process on port 2024
# ========================================
echo -e "${YELLOW}[Step 1/2] Checking for processes on port 2024...${NC}"

if lsof -i tcp:2024 >/dev/null 2>&1; then
    echo -e "${YELLOW}Found process(es) using port 2024:${NC}"
    lsof -i tcp:2024
    echo ""
    echo -e "${YELLOW}Terminating...${NC}"
    lsof -ti tcp:2024 | xargs kill -9
    echo -e "${GREEN}✓ Process(es) terminated${NC}"
    echo ""

    # Wait a moment for port to be released
    sleep 1

    echo -e "${YELLOW}Verifying port is free...${NC}"
    if lsof -i tcp:2024 >/dev/null 2>&1; then
        echo -e "${RED}✗ Port 2024 still in use!${NC}"
        echo -e "${RED}Please check manually and try again.${NC}"
        exit 1
    else
        echo -e "${GREEN}✓ Port 2024 is now free${NC}"
    fi
else
    echo -e "${GREEN}✓ No process using port 2024${NC}"
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo ""

# ========================================
# Step 2: Start the server
# ========================================
echo -e "${YELLOW}[Step 2/2] Starting server...${NC}"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found!${NC}"
    echo -e "${YELLOW}Please create a .env file with your configuration.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ .env file found${NC}"

# Check if langgraph.json exists
if [ ! -f langgraph.json ]; then
    echo -e "${RED}Error: langgraph.json file not found!${NC}"
    echo -e "${YELLOW}Please ensure langgraph.json exists in the project root.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ langgraph.json found${NC}"
echo ""

# Activate virtual environment if it exists
if [ -d .venv ]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source .venv/bin/activate
    echo -e "${GREEN}✓ Virtual environment activated${NC}"
    echo ""
else
    echo -e "${YELLOW}Warning: .venv directory not found${NC}"
    echo -e "${YELLOW}Using system Python environment${NC}"
    echo ""
fi

# Check if langgraph CLI is installed
if ! command -v langgraph &> /dev/null; then
    echo -e "${RED}Error: langgraph CLI not found!${NC}"
    echo -e "${YELLOW}Please install it with: pip install langgraph-cli${NC}"
    exit 1
fi

echo -e "${GREEN}✓ langgraph CLI found${NC}"
echo ""

# Print server information
echo -e "${BLUE}Starting LangGraph Development Server...${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}Server will be available at:${NC}"
echo -e "${GREEN}  - Local: http://localhost:2024${NC}"
echo -e "${GREEN}  - Studio: https://studio.langchain.com${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""


# Start the LangGraph development server
# 不需要 --allow-blocking，因为我们使用了 asyncio.to_thread 包装阻塞操作
exec langgraph dev --no-reload

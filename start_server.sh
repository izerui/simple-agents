#!/bin/bash

# LangGraph Development Server Launcher
# This script starts the LangGraph development server

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
echo -e "${BLUE}========================================${NC}"
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
exec langgraph dev
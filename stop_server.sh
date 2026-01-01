#!/bin/bash

# LangGraph Server Stopper
# This script stops the running LangGraph development server

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
echo -e "${BLUE}  Stop LangGraph Server${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to find and kill langgraph processes
kill_langgraph_processes() {
    local found=false
    local pids=()
    
    # Find langgraph dev processes
    while IFS= read -r line; do
        pid=$(echo "$line" | awk '{print $1}')
        cmd=$(echo "$line" | awk '{for(i=2;i<=NF;i++) printf $i" "; print ""}')
        
        if [[ "$cmd" == *"langgraph dev"* ]] || [[ "$cmd" == *"langgraph-cli"* ]]; then
            pids+=("$pid")
            found=true
        fi
    done < <(ps aux | grep langgraph | grep -v grep || true)
    
    # Also check for uvicorn processes (langgraph uses uvicorn)
    while IFS= read -r line; do
        pid=$(echo "$line" | awk '{print $1}')
        cmd=$(echo "$line" | awk '{for(i=2;i<=NF;i++) printf $i" "; print ""}')
        
        if [[ "$cmd" == *"uvicorn"* ]] && [[ "$cmd" == *"langgraph"* ]]; then
            pids+=("$pid")
            found=true
        fi
    done < <(ps aux | grep uvicorn | grep langgraph | grep -v grep || true)
    
    if [ "$found" = false ]; then
        return 1
    fi
    
    # Remove duplicate PIDs
    IFS=$'\n' read -d '' -r -a unique_pids < <(printf '%s\n' "${pids[@]}" | sort -u | head -n -1)
    
    # Kill processes
    for pid in "${unique_pids[@]}"; do
        echo -e "${YELLOW}Stopping process ${pid}...${NC}"
        kill "$pid" 2>/dev/null || true
    done
    
    return 0
}

# Try graceful shutdown first
echo -e "${YELLOW}Attempting graceful shutdown...${NC}"

if kill_langgraph_processes; then
    echo ""
    echo -e "${GREEN}✓ Graceful shutdown initiated${NC}"
    echo -e "${YELLOW}Waiting for processes to terminate...${NC}"
    
    # Wait up to 5 seconds for processes to terminate
    for i in {1..5}; do
        sleep 1
        if ! kill_langgraph_processes 2>/dev/null; then
            echo -e "${GREEN}✓ All processes terminated gracefully${NC}"
            echo ""
            echo -e "${GREEN}========================================${NC}"
            echo -e "${GREEN}  LangGraph Server Stopped${NC}"
            echo -e "${GREEN}========================================${NC}"
            exit 0
        fi
        echo -ne "\r${YELLOW}Waiting... ($i/5)${NC}"
    done
    echo ""
fi

# Force kill if still running
echo -e "${RED}Processes still running, forcing shutdown...${NC}"
echo ""

if kill_langgraph_processes; then
    echo -e "${YELLOW}Force killing processes...${NC}"
    
    # Get PIDs again and force kill
    pids=()
    while IFS= read -r line; do
        pid=$(echo "$line" | awk '{print $1}')
        pids+=("$pid")
    done < <(ps aux | grep langgraph | grep -v grep || true)
    
    while IFS= read -r line; do
        pid=$(echo "$line" | awk '{print $1}')
        pids+=("$pid")
    done < <(ps aux | grep uvicorn | grep langgraph | grep -v grep || true)
    
    # Force kill
    for pid in "${pids[@]}"; do
        echo -e "${YELLOW}Force killing process ${pid}...${NC}"
        kill -9 "$pid" 2>/dev/null || true
    done
    
    sleep 1
fi

# Check if processes are stopped
if ! kill_langgraph_processes 2>/dev/null; then
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  LangGraph Server Stopped${NC}"
    echo -e "${GREEN}========================================${NC}"
    exit 0
else
    echo ""
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}  Failed to stop server${NC}"
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}Some processes may still be running.${NC}"
    echo -e "${YELLOW}Please manually check with: ps aux | grep langgraph${NC}"
    exit 1
fi
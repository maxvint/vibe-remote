#!/bin/bash

# Get the absolute path of current directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/bot_$(date +%Y%m%d_%H%M%S).log"
PID_FILE="$SCRIPT_DIR/.bot.pid"
MAIN_PATH="$SCRIPT_DIR/main.py"

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

echo "Starting Telegram Bot Manager..."
echo "Working directory: $SCRIPT_DIR"
echo "Log file: $LOG_FILE"

# Function to kill the current instance safely
kill_current_instance() {
    if [ -f "$PID_FILE" ]; then
        OLD_PID=$(cat "$PID_FILE")
        
        # Check if the process exists and is our process
        if ps -p "$OLD_PID" > /dev/null 2>&1; then
            # Verify it's actually our python process in the correct directory
            PROCESS_CMD=$(ps -p "$OLD_PID" -o command= 2>/dev/null || echo "")
            PROCESS_CWD=$(lsof -p "$OLD_PID" -a -d cwd -Fn 2>/dev/null | grep '^n' | cut -c2- || echo "")
            
            if [[ "$PROCESS_CMD" == *"python"*"main.py"* ]] && [[ "$PROCESS_CWD" == "$SCRIPT_DIR" ]]; then
                echo "Found running instance (PID: $OLD_PID), stopping..."
                kill -TERM "$OLD_PID" 2>/dev/null
                
                # Wait for process to terminate gracefully
                for i in {1..10}; do
                    if ! ps -p "$OLD_PID" > /dev/null 2>&1; then
                        echo "Process stopped successfully"
                        break
                    fi
                    sleep 1
                done
                
                # Force kill if still running
                if ps -p "$OLD_PID" > /dev/null 2>&1; then
                    echo "Force killing process..."
                    kill -KILL "$OLD_PID" 2>/dev/null
                    sleep 1
                fi
            else
                echo "PID file exists but process is not our bot, removing stale PID file"
            fi
        else
            echo "No running instance found (stale PID file)"
        fi
        
        # Remove PID file
        rm -f "$PID_FILE"
    else
        echo "No previous instance found"
    fi
}

# Kill current instance
kill_current_instance

# Change to script directory
cd "$SCRIPT_DIR"

# Load environment variables from .env file if it exists
if [ -f .env ]; then
    # shellcheck disable=SC2046
    export $(grep -v '^#' .env | xargs)
else
    echo "ERROR: .env file not found!"
    echo "Please create a .env file with required environment variables."
    echo "You can start from the template:"
    echo "  cp .env.example .env && edit .env"
    exit 1
fi

# Create working directory if it doesn't exist
mkdir -p ./_tmp

# Check if virtual environment exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
else
    echo "No virtual environment found, using system Python"
fi

# Start the bot with output redirected to log file
echo "Starting bot..."
echo "============================================" >> "$LOG_FILE"
echo "Bot started at: $(date)" >> "$LOG_FILE"
echo "============================================" >> "$LOG_FILE"

# Run python in unbuffered mode for real-time logging
nohup python3 -u "$MAIN_PATH" >> "$LOG_FILE" 2>&1 &

# Save new PID
NEW_PID=$!
echo "$NEW_PID" > "$PID_FILE"

# Check if process started successfully
sleep 2
if ps -p "$NEW_PID" > /dev/null 2>&1; then
    echo "Bot started successfully (PID: $NEW_PID)"
    echo "Logs are being written to: $LOG_FILE"
    echo ""
    echo "To view logs in real-time:"
    echo "  tail -f $LOG_FILE"
    echo ""
    echo "To stop the bot:"
    echo "  $SCRIPT_DIR/stop.sh"
else
    echo "ERROR: Failed to start bot!"
    echo "Check the log file for errors: $LOG_FILE"
    tail -n 20 "$LOG_FILE"
    rm -f "$PID_FILE"
    exit 1
fi
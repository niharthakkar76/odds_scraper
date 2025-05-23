#!/bin/bash

# Check if GitHub token is provided
if [ -z "$1" ]; then
  echo "Usage: ./trigger_workflow.sh <github_token>"
  echo "Please provide a GitHub Personal Access Token with workflow permissions"
  exit 1
fi

# Activate virtual environment and run the Python script
source venv/bin/activate
python trigger_workflow.py "$1"

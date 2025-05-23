#!/usr/bin/env python
import requests
import sys
import json
from datetime import datetime

def check_workflow_runs(owner, repo, github_token):
    """
    Check the status of all workflow runs in a GitHub repository.
    
    Args:
        owner (str): GitHub username/organization
        repo (str): Repository name
        github_token (str): GitHub Personal Access Token
    """
    # API endpoint to get all workflow runs
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs"
    
    # Headers for authentication
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    print(f"Checking workflow runs for {owner}/{repo}...")
    
    # Get workflow runs with retry logic
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            break
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            retry_count += 1
            if retry_count == max_retries:
                print(f"Failed to connect after {max_retries} attempts: {e}")
                return
            print(f"Connection error, retrying ({retry_count}/{max_retries})...")
            time.sleep(2)
    
    if response.status_code == 200:
        runs_data = response.json()
        total_runs = runs_data.get("total_count", 0)
        
        print(f"Found {total_runs} workflow runs")
        
        if total_runs > 0:
            runs = runs_data.get("workflow_runs", [])
            
            print("\nWorkflow Runs:")
            print("-" * 80)
            
            for run in runs:
                run_id = run.get("id")
                workflow_name = run.get("name")
                status = run.get("status")
                conclusion = run.get("conclusion")
                created_at = run.get("created_at")
                updated_at = run.get("updated_at")
                html_url = run.get("html_url")
                
                # Convert timestamps to readable format
                if created_at:
                    created_at = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M:%S")
                if updated_at:
                    updated_at = datetime.strptime(updated_at, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M:%S")
                
                print(f"Run ID: {run_id}")
                print(f"Workflow: {workflow_name}")
                print(f"Status: {status}")
                print(f"Conclusion: {conclusion}")
                print(f"Created: {created_at}")
                print(f"Updated: {updated_at}")
                print(f"URL: {html_url}")
                
                # Get the logs URL if available
                logs_url = run.get("logs_url")
                if logs_url:
                    print(f"Logs URL: {logs_url}")
                
                # Get detailed job information
                jobs_url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
                jobs_response = requests.get(jobs_url, headers=headers)
                
                if jobs_response.status_code == 200:
                    jobs_data = jobs_response.json()
                    jobs = jobs_data.get("jobs", [])
                    
                    print("\nJobs:")
                    for job in jobs:
                        job_id = job.get("id")
                        job_name = job.get("name")
                        job_status = job.get("status")
                        job_conclusion = job.get("conclusion")
                        job_steps = job.get("steps", [])
                        
                        print(f"  Job: {job_name} (ID: {job_id})")
                        print(f"  Status: {job_status}")
                        print(f"  Conclusion: {job_conclusion}")
                        
                        if job_steps:
                            print("  Steps:")
                            for step in job_steps:
                                step_name = step.get("name")
                                step_status = step.get("status")
                                step_conclusion = step.get("conclusion")
                                
                                print(f"    - {step_name}: {step_status} ({step_conclusion})")
                
                print("-" * 80)
        else:
            print("No workflow runs found.")
    else:
        print(f"Failed to get workflow runs: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_workflow_status.py <github_token>")
        sys.exit(1)
    
    # Repository details
    owner = "niharthakkar76"
    repo = "odds_scraper"
    github_token = sys.argv[1]
    
    check_workflow_runs(owner, repo, github_token)

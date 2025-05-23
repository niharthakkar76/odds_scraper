#!/usr/bin/env python
import requests
import json
import sys
import time

def trigger_github_workflow(owner, repo, workflow_id, github_token):
    """
    Trigger a GitHub Actions workflow and monitor its status.
    
    Args:
        owner (str): GitHub username/organization
        repo (str): Repository name
        workflow_id (str): Workflow file name (e.g., 'daily_odds_scraper.yml')
        github_token (str): GitHub Personal Access Token with workflow permissions
    """
    # API endpoint to trigger a workflow
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches"
    
    # Headers for authentication
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Payload (using the default branch)
    data = {
        "ref": "main"
    }
    
    print(f"Triggering workflow '{workflow_id}' in {owner}/{repo}...")
    
    # Trigger the workflow
    response = requests.post(url, headers=headers, data=json.dumps(data))
    
    if response.status_code == 204:
        print("Workflow triggered successfully!")
        
        # Wait a moment for the workflow to start
        print("Waiting for workflow to start...")
        time.sleep(5)
        
        # Get the workflow runs to find the one we just triggered
        runs_url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs"
        runs_response = requests.get(runs_url, headers=headers)
        
        if runs_response.status_code == 200:
            runs_data = runs_response.json()
            if runs_data["total_count"] > 0:
                latest_run = runs_data["workflow_runs"][0]
                run_id = latest_run["id"]
                run_url = latest_run["html_url"]
                
                print(f"Workflow run started: {run_url}")
                print(f"Run ID: {run_id}")
                
                # Monitor the workflow status
                monitor_workflow_run(owner, repo, run_id, github_token)
            else:
                print("No workflow runs found. It might take a moment for the run to appear.")
        else:
            print(f"Failed to get workflow runs: {runs_response.status_code}")
            print(runs_response.text)
    else:
        print(f"Failed to trigger workflow: {response.status_code}")
        print(response.text)

def monitor_workflow_run(owner, repo, run_id, github_token):
    """
    Monitor a GitHub Actions workflow run until it completes.
    
    Args:
        owner (str): GitHub username/organization
        repo (str): Repository name
        run_id (int): Workflow run ID
        github_token (str): GitHub Personal Access Token
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    print("Monitoring workflow run...")
    status = "in_progress"
    
    while status in ["in_progress", "queued", "waiting"]:
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            status = data["status"]
            conclusion = data.get("conclusion")
            
            print(f"Status: {status}, Conclusion: {conclusion or 'N/A'}")
            
            if status == "completed":
                if conclusion == "success":
                    print("Workflow completed successfully!")
                else:
                    print(f"Workflow completed with conclusion: {conclusion}")
                
                # Get the logs URL
                logs_url = data["logs_url"]
                artifacts_url = f"https://github.com/{owner}/{repo}/actions/runs/{run_id}/artifacts"
                print(f"Logs URL: {logs_url}")
                print(f"Artifacts URL: {artifacts_url}")
                break
            
            # Wait before checking again
            time.sleep(10)
        else:
            print(f"Failed to get workflow run status: {response.status_code}")
            print(response.text)
            break

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python trigger_workflow.py <github_token>")
        sys.exit(1)
    
    # Repository details
    owner = "niharthakkar76"
    repo = "odds_scraper"
    workflow_id = "daily_odds_scraper.yml"
    github_token = sys.argv[1]
    
    trigger_github_workflow(owner, repo, workflow_id, github_token)

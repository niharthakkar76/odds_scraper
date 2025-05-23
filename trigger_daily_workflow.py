#!/usr/bin/env python
import requests
import sys
import json
import time

def trigger_workflow(owner, repo, workflow_name, github_token):
    """
    Trigger a GitHub Actions workflow by name and monitor its status.
    
    Args:
        owner (str): GitHub username/organization
        repo (str): Repository name
        workflow_name (str): Name of the workflow to trigger
        github_token (str): GitHub Personal Access Token
    """
    # First, get the workflow ID by name
    workflows_url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows"
    
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    print(f"Getting workflows for {owner}/{repo}...")
    
    # Get all workflows
    response = requests.get(workflows_url, headers=headers)
    
    if response.status_code == 200:
        workflows = response.json()
        
        # Find our workflow
        target_workflow = None
        for workflow in workflows.get('workflows', []):
            if workflow.get('name') == workflow_name:
                target_workflow = workflow
                break
        
        if target_workflow:
            workflow_id = target_workflow.get('id')
            print(f"Found workflow '{workflow_name}' with ID: {workflow_id}")
            
            # Trigger the workflow
            dispatch_url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches"
            data = {
                "ref": "main"
            }
            
            print(f"Triggering workflow '{workflow_name}'...")
            dispatch_response = requests.post(dispatch_url, headers=headers, data=json.dumps(data))
            
            if dispatch_response.status_code == 204:
                print("Workflow triggered successfully!")
                
                # Wait for the workflow to start
                print("Waiting for workflow run to start...")
                time.sleep(5)
                
                # Monitor the workflow run
                monitor_latest_run(owner, repo, workflow_id, github_token)
                
                return True
            else:
                print(f"Failed to trigger workflow: {dispatch_response.status_code}")
                print(dispatch_response.text)
                return False
        else:
            print(f"Workflow '{workflow_name}' not found")
            return False
    else:
        print(f"Failed to get workflows: {response.status_code}")
        print(response.text)
        return False

def monitor_latest_run(owner, repo, workflow_id, github_token):
    """
    Monitor the latest run of a workflow.
    
    Args:
        owner (str): GitHub username/organization
        repo (str): Repository name
        workflow_id (int): Workflow ID
        github_token (str): GitHub Personal Access Token
    """
    # Get the latest run for this workflow
    runs_url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs"
    
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Get workflow runs
    response = requests.get(runs_url, headers=headers)
    
    if response.status_code == 200:
        runs_data = response.json()
        runs = runs_data.get("workflow_runs", [])
        
        if runs:
            latest_run = runs[0]  # The first run is the latest
            run_id = latest_run.get("id")
            html_url = latest_run.get("html_url")
            
            print(f"Latest run started: {html_url}")
            print(f"Run ID: {run_id}")
            
            # Monitor the run status
            print("Monitoring run status...")
            status = "queued"
            
            while status in ["queued", "in_progress", "waiting"]:
                # Get the run status
                run_url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}"
                run_response = requests.get(run_url, headers=headers)
                
                if run_response.status_code == 200:
                    run_data = run_response.json()
                    status = run_data.get("status")
                    conclusion = run_data.get("conclusion")
                    
                    print(f"Status: {status}, Conclusion: {conclusion or 'N/A'}")
                    
                    if status == "completed":
                        if conclusion == "success":
                            print("Workflow completed successfully!")
                        else:
                            print(f"Workflow completed with conclusion: {conclusion}")
                        
                        # Get job details
                        jobs_url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
                        jobs_response = requests.get(jobs_url, headers=headers)
                        
                        if jobs_response.status_code == 200:
                            jobs_data = jobs_response.json()
                            jobs = jobs_data.get("jobs", [])
                            
                            print("\nJobs:")
                            for job in jobs:
                                job_name = job.get("name")
                                job_status = job.get("status")
                                job_conclusion = job.get("conclusion")
                                
                                print(f"  Job: {job_name}")
                                print(f"  Status: {job_status}")
                                print(f"  Conclusion: {job_conclusion}")
                                
                                steps = job.get("steps", [])
                                if steps:
                                    print("  Steps:")
                                    for step in steps:
                                        step_name = step.get("name")
                                        step_status = step.get("status")
                                        step_conclusion = step.get("conclusion")
                                        
                                        print(f"    - {step_name}: {step_status} ({step_conclusion})")
                        
                        break
                    
                    # Wait before checking again
                    time.sleep(10)
                else:
                    print(f"Failed to get run status: {run_response.status_code}")
                    print(run_response.text)
                    break
        else:
            print("No runs found for this workflow")
    else:
        print(f"Failed to get workflow runs: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python trigger_daily_workflow.py <github_token>")
        sys.exit(1)
    
    # Repository details
    owner = "niharthakkar76"
    repo = "odds_scraper"
    workflow_name = "Daily Odds Scraper"
    github_token = sys.argv[1]
    
    trigger_workflow(owner, repo, workflow_name, github_token)

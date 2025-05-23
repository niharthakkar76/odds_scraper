import requests
import sys
import time
import json

def trigger_workflow(owner, repo, workflow_name, github_token):
    """
    Trigger a GitHub Actions workflow by name and monitor its execution.
    
    Args:
        owner (str): GitHub repository owner
        repo (str): GitHub repository name
        workflow_name (str): Name of the workflow to trigger
        github_token (str): GitHub Personal Access Token
    """
    # Get workflow ID from name
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # First, get all workflows
    workflows_url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows"
    
    try:
        workflows_response = requests.get(workflows_url, headers=headers)
        
        if workflows_response.status_code != 200:
            print(f"Error getting workflows: {workflows_response.status_code}")
            print(workflows_response.json())
            return
            
        workflows_data = workflows_response.json()
        
        # Find the workflow by name
        workflow_id = None
        for workflow in workflows_data.get("workflows", []):
            if workflow["name"] == workflow_name:
                workflow_id = workflow["id"]
                break
                
        if not workflow_id:
            print(f"Workflow '{workflow_name}' not found")
            return
            
        # Trigger the workflow
        dispatch_url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches"
        dispatch_data = {"ref": "main"}
        
        dispatch_response = requests.post(dispatch_url, headers=headers, json=dispatch_data)
        
        if dispatch_response.status_code == 204:
            print(f"Successfully triggered workflow '{workflow_name}'")
            
            # Wait a moment for the workflow to start
            print("Waiting for workflow to start...")
            time.sleep(5)
            
            # Get the latest run of this workflow
            runs_url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs"
            
            max_attempts = 10
            for attempt in range(max_attempts):
                runs_response = requests.get(runs_url, headers=headers)
                
                if runs_response.status_code == 200:
                    runs_data = runs_response.json()
                    
                    if runs_data.get("total_count", 0) > 0:
                        latest_run = runs_data["workflow_runs"][0]
                        run_id = latest_run["id"]
                        run_url = latest_run["html_url"]
                        
                        print(f"Workflow run started: {run_url}")
                        print(f"Run ID: {run_id}")
                        print(f"Status: {latest_run['status']}")
                        
                        # Monitor the run
                        monitor_run(owner, repo, run_id, github_token)
                        return
                
                print(f"Waiting for run to appear (attempt {attempt+1}/{max_attempts})...")
                time.sleep(3)
                
            print("Could not find the triggered workflow run")
        else:
            print(f"Error triggering workflow: {dispatch_response.status_code}")
            print(dispatch_response.text)
    except Exception as e:
        print(f"Error: {e}")

def monitor_run(owner, repo, run_id, github_token):
    """
    Monitor a GitHub Actions workflow run until it completes.
    
    Args:
        owner (str): GitHub repository owner
        repo (str): GitHub repository name
        run_id (int): ID of the workflow run to monitor
        github_token (str): GitHub Personal Access Token
    """
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    run_url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}"
    
    print("\nMonitoring workflow run...")
    
    while True:
        try:
            response = requests.get(run_url, headers=headers)
            
            if response.status_code == 200:
                run_data = response.json()
                status = run_data["status"]
                conclusion = run_data.get("conclusion")
                
                print(f"Status: {status}, Conclusion: {conclusion or 'N/A'}")
                
                if status == "completed":
                    print("\nWorkflow run completed!")
                    print(f"Conclusion: {conclusion}")
                    print(f"Run URL: {run_data['html_url']}")
                    
                    # Get job details
                    jobs_url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
                    jobs_response = requests.get(jobs_url, headers=headers)
                    
                    if jobs_response.status_code == 200:
                        jobs_data = jobs_response.json()
                        
                        print("\nJobs:")
                        for job in jobs_data.get("jobs", []):
                            print(f"  Job: {job['name']} (ID: {job['id']})")
                            print(f"  Status: {job['status']}")
                            print(f"  Conclusion: {job['conclusion']}")
                            
                            print("  Steps:")
                            for step in job.get("steps", []):
                                print(f"    - {step['name']}: {step['status']} ({step['conclusion']})")
                            
                            print()
                    
                    break
                
                # Wait before checking again
                time.sleep(10)
            else:
                print(f"Error getting run details: {response.status_code}")
                print(response.text)
                break
        except Exception as e:
            print(f"Error monitoring run: {e}")
            break

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python trigger_workflow.py <workflow_name> <github_token>")
        sys.exit(1)
        
    workflow_name = sys.argv[1]
    github_token = sys.argv[2]
    
    # Repository details
    owner = "niharthakkar76"
    repo = "odds_scraper"
    
    trigger_workflow(owner, repo, workflow_name, github_token)

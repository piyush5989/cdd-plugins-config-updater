import requests
from utils.logger import get_logger

logger = get_logger(__name__)
GITHUB_API_BASE = "https://github.gwd.broadcom.net/api/v3"

def create_pull_request(github_user: str, github_token: str, repo_name: str, branch_name: str, pr_title: str, base_branch: str):
    url = f"{GITHUB_API_BASE}/repos/{github_user}/{repo_name}/pulls"
    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    payload = {
        "title": pr_title,
        "head": branch_name,
        "base": base_branch
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 201:
        pr_url = response.json().get("html_url")
        pr_number = response.json().get("number")
        logger.info(f"Created PR for {repo_name}")
        return True, pr_url, pr_number
    else:
        logger.error(f"Failed to create PR: {response.status_code} {response.text}")
        return False, None, None

def request_reviewer(github_user: str, github_token: str, repo_name: str, pr_number: int, reviewer: str):
    url = f"{GITHUB_API_BASE}/repos/{github_user}/{repo_name}/pulls/{pr_number}/requested_reviewers"
    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    payload = {
        "reviewers": [reviewer]
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.status_code == 201

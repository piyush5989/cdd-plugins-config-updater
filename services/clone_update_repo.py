import os
import tempfile
import shutil
from git import Repo
from utils.logger import get_logger

logger = get_logger(__name__)

def clone_repo(repo_url: str, github_user: str, github_token: str):
    temp_dir = tempfile.mkdtemp()
    repo_name = repo_url.split('/')[-1].replace('.git', '')
    repo_path = os.path.join(temp_dir, repo_name)
    repo = Repo.clone_from(repo_url, repo_path)
    logger.info(f"Cloned {repo_name}")
    return repo, repo_path, temp_dir, repo_name

def create_branch(repo, branch_name: str):
    new_branch = repo.create_head(branch_name)
    new_branch.checkout()
    logger.info(f"Created and checked out branch {branch_name}")

def update_file(file_path: str, search_pattern: str, replace_with: str) -> bool:
    import re
    if not os.path.exists(file_path):
        return False

    with open(file_path, 'r') as f:
        content = f.read()

    if not re.search(search_pattern, content, flags=re.MULTILINE):
        return False

    updated_content = re.sub(search_pattern, replace_with, content, flags=re.MULTILINE)

    with open(file_path, 'w') as f:
        f.write(updated_content)

    logger.info(f"Updated file {file_path}")
    return True

def apply_multiple_changes(repo_path: str, changes: list) -> bool:
    import re
    changed = False

    for change in changes:
        file_path = os.path.join(repo_path, change['target_file'])
        if not os.path.exists(file_path):
            continue

        with open(file_path, 'r') as f:
            content = f.read()

        if not re.search(change['search_pattern'], content, flags=re.MULTILINE):
            continue

        updated_content = re.sub(change['search_pattern'], change['replace_with'], content, flags=re.MULTILINE)

        with open(file_path, 'w') as f:
            f.write(updated_content)

        logger.info(f"Updated file: {file_path}")
        changed = True

    return changed

def commit_and_push(repo, branch_name: str, commit_message: str):
    repo.git.add(A=True)
    repo.index.commit(commit_message)
    origin = repo.remote(name='origin')
    origin.push(refspec=f'{branch_name}:{branch_name}')
    logger.info(f"Pushed branch {branch_name}")

def cleanup(path):
    try:
        shutil.rmtree(path)
        print(f"Deleted {path} successfully.")
        return
    except FileNotFoundError:
        print(f"{path} not found. No need to delete.")
        return
    except PermissionError:
        print(f"Permission denied when trying to delete {path}...")
    except Exception as e:
        print(f"Unexpected error when trying to delete {path}: {e}...")
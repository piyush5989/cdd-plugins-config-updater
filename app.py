import streamlit as st
import json
import concurrent.futures
import os
from git import GitCommandError
from services.git_service import clone_repo, create_branch, update_file, commit_and_push, cleanup
from services.github_service import create_pull_request, request_reviewer
from utils.logger import get_logger

logger = get_logger(__name__)

# Load environment
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_USER = 'ESD'

# Load Repos
with open('configs/cdd-plugin-repos.json') as f:
    REPOS = json.load(f)

st.title("Mass Config Updater")

if not GITHUB_TOKEN:
    st.error("GITHUB_TOKEN not set!")
    st.stop()

repo_choices = {repo.split('/')[-1].replace('.git', ''): repo for repo in REPOS}
selected_plugins = st.multiselect("Select Plugins to Update:", options=list(repo_choices.keys()))

branch_name = st.text_input("Branch Name", value="auto/config-update")
commit_message = st.text_input("Commit Message", value="Plugin config updates from script")
pr_title = st.text_input("Pull Request Title", value="Plugin config updates from script")
base_branch = st.text_input("Base Branch", value="master")

# file_name = st.text_input("File to update (e.g., gradle.properties)")
file_options = ["gradle.properties", "build.gradle", "Dockerfile", "custom"]
file_choice = st.selectbox("Select File to Update", options=file_options)
if file_choice == "custom":
    file_name = st.text_input("Enter custom file path (relative to repo root)")
else:
    file_name = file_choice
search_pattern = st.text_input("Search Pattern (Regex)", value="")
replace_with = st.text_input("Replacement Text", value="")
reviewer = st.text_input("Reviewer Username/Email", value="")

status_dashboard = {}

if st.button("Start Update"):
    progress_bar = st.progress(0)
    status_text = st.empty()
    status_text.text("Update in Progress... Please wait...")
    def process_plugin(plugin_name, reviewer):
        repo_url = repo_choices[plugin_name]
        try:
            repo, repo_path, temp_dir, repo_name = clone_repo(repo_url, GITHUB_USER, GITHUB_TOKEN)
            create_branch(repo, branch_name)
            changed = update_file(os.path.join(repo_path, file_name), search_pattern, replace_with)

            if changed:
                commit_and_push(repo, branch_name, commit_message)
                pr_created, pr_url, pr_number = create_pull_request(GITHUB_USER, GITHUB_TOKEN, repo_name, branch_name, pr_title, base_branch)
                if pr_created:
                    # If reviewer is provided, request a review
                    if reviewer:
                        request_reviewer(GITHUB_USER, GITHUB_TOKEN, repo_name, pr_number, reviewer)
                    result = f"[View PR]({pr_url})"
                else:
                    result = "PR creation failed"
            else:
                result = "No matching changes"
            
            repo.close()
            cleanup(temp_dir)
            return plugin_name, result
        except GitCommandError as e:
            logger.exception(f"Git error in {plugin_name}: {e}")
            return plugin_name, f"Git error: {str(e)}"
        except Exception as e:
            logger.exception("Error processing plugin")
            return plugin_name, f"Error: {str(e)}"
        finally:
            if repo:
                repo.close()
            if temp_dir:
                cleanup(temp_dir)

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(process_plugin, plugin, reviewer): plugin for plugin in selected_plugins}
        for idx, future in enumerate(concurrent.futures.as_completed(futures), 1):
            plugin_name, result = future.result()
            status_dashboard[plugin_name] = result
            progress_bar.progress(idx / len(selected_plugins))

    status_text.text("Update Completed Successfully!")
    st.success("Update Completed!")
    st.subheader("Status Dashboard")
    for plugin, result in status_dashboard.items():
        st.markdown(f"**{plugin}**: {result}")

import streamlit as st
import json
import concurrent.futures
import os
from git import GitCommandError
from services.clone_update_repo import clone_repo, create_branch, apply_multiple_changes, commit_and_push, cleanup
from services.pull_request_review import create_pull_request, request_reviewer
from utils.logger import get_logger
from dotenv import load_dotenv
load_dotenv()

logger = get_logger(__name__)

# Load environment
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_USER = os.getenv("GITHUB_USER")

if "changes" not in st.session_state:
    st.session_state["changes"] = []
if "edit_idx" not in st.session_state:
    st.session_state["edit_idx"] = None

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
reviewer = st.text_input("Reviewer Username/Email", value="")

status_dashboard = {}

def process_plugin(plugin_name, reviewer, changes):
    repo_url = repo_choices[plugin_name]
    try:
        repo, repo_path, temp_dir, repo_name = clone_repo(repo_url, GITHUB_USER, GITHUB_TOKEN)
        create_branch(repo, branch_name)
        logger.info(f"Applying changes: {changes}")
        changed = apply_multiple_changes(repo_path, changes)

        if changed:
            commit_and_push(repo, branch_name, commit_message)
            pr_created, pr_url, pr_number = create_pull_request(GITHUB_USER, GITHUB_TOKEN, repo_name, branch_name, pr_title, base_branch)
            if pr_created:
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
        if 'repo' in locals(): repo.close()
        if 'temp_dir' in locals(): cleanup(temp_dir)

# Safe defaults for input fields
for key in ["target_file_input", "search_pattern_input", "replace_with_input"]:
    if key not in st.session_state:
        st.session_state[key] = ""
if "reset_form" not in st.session_state:
    st.session_state["reset_form"] = False

# Handle form reset before rendering widgets
if st.session_state["reset_form"]:
    st.session_state["target_file_input"] = ""
    st.session_state["search_pattern_input"] = ""
    st.session_state["replace_with_input"] = ""
    st.session_state["reset_form"] = False

# --- UI for changes ---
st.subheader("Add Config Change")

with st.form(key="change_form"):
    file_options = ["gradle.properties", "build.gradle", "Dockerfile", "custom"]
    file_choice = st.selectbox("Select File to Update", options=file_options)
    
    if file_choice == "custom":
        target_file = st.text_input(
            "Enter custom file path (relative to repo root)",
            key="target_file_input"
        )
    else:
        target_file = file_choice
        st.session_state["target_file_input"] = target_file

    st.text_input("Search Pattern (Regex)", key="search_pattern_input")
    st.text_input("Replacement Text", key="replace_with_input")

    submit = st.form_submit_button("Add Change")

    if submit:
        change = {
            "target_file": st.session_state["target_file_input"],
            "search_pattern": st.session_state["search_pattern_input"],
            "replace_with": st.session_state["replace_with_input"]
        }

        if st.session_state["edit_idx"] is not None:
            st.session_state["changes"][st.session_state["edit_idx"]] = change
            st.session_state["edit_idx"] = None
            st.success("Change updated.")
            logger.info(f"Updated change: {change}")
        else:
            st.session_state["changes"].append(change)
            st.success("Change added.")
            logger.info(f"Added change: {change}")

        st.session_state["reset_form"] = True
        st.rerun()


st.subheader("📋 Changes to Apply")
for idx, change in enumerate(st.session_state.get("changes", [])):
    col1, col2 = st.columns([6, 1])
    with col1:
        st.markdown(f"📄 `{change['target_file']}`: `{change['search_pattern']}` → `{change['replace_with']}`")
    with col2:
        if st.button("🗑️", key=f"delete_{idx}"):
            st.session_state["changes"].pop(idx)
            st.rerun()

if st.session_state.get("changes"):
    if st.button("Clear All Changes"):
        st.session_state["changes"] = []
        st.rerun()

# --- Streamlit Update Trigger ---
if st.session_state.get("changes") and selected_plugins:
    if st.button("Start Update"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        status_text.text("Update in Progress... Please wait...")

        changes = st.session_state.get("changes", [])
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(process_plugin, plugin, reviewer, changes): plugin for plugin in selected_plugins}
            for idx, future in enumerate(concurrent.futures.as_completed(futures), 1):
                plugin_name, result = future.result()
                status_dashboard[plugin_name] = result
                progress_bar.progress(idx / len(selected_plugins))

        status_text.text("Update Completed Successfully!")
        st.success("Update Completed!")
        st.subheader("Status Dashboard")
        for plugin, result in status_dashboard.items():
            st.markdown(f"**{plugin}**: {result}")
else:
    st.info("Please add at least one change and select plugins to continue.")

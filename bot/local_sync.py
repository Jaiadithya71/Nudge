import os
import sys
import json
import datetime
import subprocess
import urllib.request
import urllib.parse
import mimetypes
import ssl
import filecmp
from dotenv import load_dotenv

# 1. Global SSL Bypass for urllib (Telegram notifications)
try:
    ssl_context = ssl._create_unverified_context()
except Exception as e:
    ssl_context = None
    print(f"Warning: Failed to create unverified SSL context: {e}")

# 2. Global SSL Bypass for Git operations
os.environ["GIT_SSL_NO_VERIFY"] = "true"

# Load env variables
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GITHUB_PAT = os.getenv("GITHUB_PAT")

import git

def send_telegram_message(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}).encode("utf-8")
    req = urllib.request.Request(url, data=data)
    try:
        with urllib.request.urlopen(req, context=ssl_context) as response:
            return response.read()
    except Exception as e:
        print(f"Error sending message: {e}")
        return None

def send_telegram_photo(token, chat_id, photo_path, caption=""):
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    
    parts = []
    parts.append(f"--{boundary}".encode("utf-8"))
    parts.append(f'Content-Disposition: form-data; name="chat_id"'.encode("utf-8"))
    parts.append(b'')
    parts.append(str(chat_id).encode("utf-8"))
    
    if caption:
        parts.append(f"--{boundary}".encode("utf-8"))
        parts.append(f'Content-Disposition: form-data; name="caption"'.encode("utf-8"))
        parts.append(b'')
        parts.append(caption.encode("utf-8"))
        
    parts.append(f"--{boundary}".encode("utf-8"))
    parts.append(f'Content-Disposition: form-data; name="photo"; filename="{os.path.basename(photo_path)}"'.encode("utf-8"))
    mime_type = mimetypes.guess_type(photo_path)[0] or 'application/octet-stream'
    parts.append(f'Content-Type: {mime_type}'.encode("utf-8"))
    parts.append(b'')
    
    with open(photo_path, 'rb') as f:
        parts.append(f.read())
        
    parts.append(f"--{boundary}--".encode("utf-8"))
    
    body = b'\r\n'.join(parts)
    
    req = urllib.request.Request(url, data=body)
    req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
    req.add_header('Content-Length', str(len(body)))
    
    try:
        with urllib.request.urlopen(req, context=ssl_context) as response:
            return response.read()
    except Exception as e:
        print(f"Error sending photo: {e}")
        return None

def sync_git_repo(repo_path, commit_message):
    try:
        repo = git.Repo(repo_path)
        if GITHUB_PAT:
            origin = repo.remote(name='origin')
            url = list(origin.urls)[0]
            if "github.com" in url and GITHUB_PAT not in url:
                authenticated_url = f"https://Jaiadithya71:{GITHUB_PAT}@github.com/Jaiadithya71/Nudge.git"
                repo.git.remote('set-url', 'origin', authenticated_url)
        
        # Pull latest
        try:
            repo.git.pull('origin', 'main')
        except Exception as e:
            print(f"Error pulling: {e}")
            
        # Add changes
        repo.git.add(all=True)
        
        # Commit if dirty
        if repo.is_dirty(untracked_files=True):
            repo.index.commit(commit_message)
            try:
                repo.git.push('origin', 'main')
                print("Pushed changes to GitHub.")
                return True
            except Exception as e:
                print(f"Error pushing: {e}")
                return False
        return True
    except Exception as e:
        print(f"Git sync failed: {e}")
        return False

def run_local_sync():
    nudge_dir = r"C:\Users\jaiad\Personal_Work_Related\Personal Projects\Nudge"
    next_move_plan = r"C:\Users\jaiad\Personal_Work_Related\Personal Projects\Next_Move\complex_accountability_plan.md"
    nudge_plan = os.path.join(nudge_dir, "complex_accountability_plan.md")
    queue_path = os.path.join(nudge_dir, "bot", "command_queue.json")
    
    print("Starting local sync sequence...")
    
    # 1. Fetch remote Git state first to see if we are behind
    repo = git.Repo(nudge_dir)
    if GITHUB_PAT:
        origin = repo.remote(name='origin')
        url = list(origin.urls)[0]
        if "github.com" in url and GITHUB_PAT not in url:
            authenticated_url = f"https://Jaiadithya71:{GITHUB_PAT}@github.com/Jaiadithya71/Nudge.git"
            repo.git.remote('set-url', 'origin', authenticated_url)
            
    print("Checking for remote updates from Git...")
    try:
        repo.git.fetch('origin', 'main')
    except Exception as e:
        print(f"Error fetching: {e}")
        
    active_branch = repo.active_branch
    tracking_branch = active_branch.tracking_branch()
    is_behind = False
    
    if tracking_branch:
        behind_commits = list(repo.iter_commits(f"{active_branch.name}..{tracking_branch.name}"))
        is_behind = len(behind_commits) > 0
        
    if is_behind:
        print("Remote updates found. Pulling latest commits...")
        try:
            repo.git.pull('origin', 'main')
        except Exception as e:
            print(f"Error pulling: {e}")
            
        # Copy updated plan from Nudge repo back to Next_Move
        if os.path.exists(nudge_plan) and os.path.exists(os.path.dirname(next_move_plan)):
            print("Updating Next_Move plan with pulled changes...")
            import shutil
            shutil.copy2(nudge_plan, next_move_plan)
    else:
        print("No remote updates found. Syncing local plan edits...")
        # Check if local plan in Next_Move was modified relative to Nudge plan
        if os.path.exists(next_move_plan):
            # Check if files differ
            if not os.path.exists(nudge_plan) or not filecmp.cmp(next_move_plan, nudge_plan, shallow=False):
                print("Local plan in Next_Move has edits. Copying to Nudge...")
                import shutil
                shutil.copy2(next_move_plan, nudge_plan)
                sync_git_repo(nudge_dir, "Local plan edits sync [skip ci]")
            else:
                print("Local and remote plan files are identical. No file sync needed.")
                
    # 2. Check for pending commands in the queue
    if os.path.exists(queue_path):
        try:
            with open(queue_path, "r", encoding="utf-8") as f:
                queue = json.load(f)
        except Exception as e:
            print(f"Error reading queue: {e}")
            queue = []
            
        pending_commands = [c for c in queue if c.get("status") == "pending"]
        
        if pending_commands:
            print(f"Processing {len(pending_commands)} pending commands...")
            
            for cmd_item in pending_commands:
                cmd_id = cmd_item.get("id")
                cmd_text = cmd_item.get("command")
                print(f"Executing: {cmd_text}")
                
                stdout_str = ""
                stderr_str = ""
                
                if cmd_text == "screenshot":
                    screenshot_path = os.path.join(nudge_dir, "bot", "screenshot.png")
                    captured = False
                    try:
                        from PIL import ImageGrab
                        screenshot = ImageGrab.grab()
                        screenshot.save(screenshot_path)
                        captured = True
                    except Exception as e:
                        print(f"PIL screenshot failed: {e}")
                        try:
                            import pyautogui
                            pyautogui.screenshot(screenshot_path)
                            captured = True
                        except Exception as e2:
                            print(f"PyAutoGUI screenshot failed: {e2}")
                            stdout_str = f"Screenshot capture failed: {str(e2)}"
                            
                    if captured:
                        send_telegram_photo(
                            TELEGRAM_BOT_TOKEN,
                            TELEGRAM_CHAT_ID,
                            screenshot_path,
                            caption="💻 Laptop Screenshot"
                        )
                        try:
                            os.remove(screenshot_path)
                        except Exception:
                            pass
                else:
                    shell_cmd = ""
                    if cmd_text == "git status":
                        shell_cmd = "git status"
                    elif cmd_text == "git log -n 5":
                        shell_cmd = "git log -n 5"
                    elif cmd_text == "run tests":
                        test_dir = r"C:\Users\jaiad\Personal_Work_Related\Personal Projects\This-or-That"
                        if os.path.exists(test_dir):
                            shell_cmd = "npm run test"
                        else:
                            shell_cmd = "echo 'No tests configured for workspace.'"
                    
                    if shell_cmd:
                        cwd_dir = nudge_dir
                        if cmd_text == "run tests" and os.path.exists(r"C:\Users\jaiad\Personal_Work_Related\Personal Projects\This-or-That"):
                            cwd_dir = r"C:\Users\jaiad\Personal_Work_Related\Personal Projects\This-or-That"
                            
                        res = subprocess.run(shell_cmd, shell=True, capture_output=True, text=True, cwd=cwd_dir)
                        stdout_str = res.stdout
                        stderr_str = res.stderr
                        
                        output_msg = f"💻 *Executed Whitelisted Command: {cmd_text}*\n\n"
                        if stdout_str:
                            output_msg += f"*Stdout:*\n```\n{stdout_str}\n```\n"
                        if stderr_str:
                            output_msg += f"*Stderr:*\n```\n{stderr_str}\n```"
                        if not stdout_str and not stderr_str:
                            output_msg += "_Command completed with no output._"
                            
                        send_telegram_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, output_msg)
                    else:
                        send_telegram_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, f"⚠️ Command '{cmd_text}' is not whitelisted.")
                        
                for item in queue:
                    if item.get("id") == cmd_id:
                        item["status"] = "completed"
                        
            with open(queue_path, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2)
                
            sync_git_repo(nudge_dir, "Clear completed commands queue [skip ci]")
            
    # Send boot-up sync notification
    send_telegram_message(
        TELEGRAM_BOT_TOKEN,
        TELEGRAM_CHAT_ID,
        "💻 *Boot-up sequence completed.*\nAll items synced, and local plan is up to date."
    )
    print("Local sync finished successfully.")

if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Error: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env")
        sys.exit(1)
    run_local_sync()

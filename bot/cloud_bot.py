import os
import sys
import json
import datetime
import uuid
import threading
import http.server
import socketserver
import asyncio
from dotenv import load_dotenv

# Load env variables
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Set Gemini API key in environment for the SDK
if GEMINI_API_KEY:
    os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# GitPython integration
import git

class LogUpdate(BaseModel):
    leetcode_solved: int = Field(0, description="Number of LeetCode problems solved to add.")
    leetcode_contest: int = Field(0, description="Number of contests attended to add (usually 1).")
    study_hours: float = Field(0.0, description="Number of hours studied to add.")
    git_commits_cert: str = Field("", description="Updates to Git Commits / Cert Prep column.")
    notes: str = Field("", description="Description of the activity to append to the Notes column.")

class UserIntent(BaseModel):
    intent_type: str = Field(description="The type of action the user wants to perform. Choose from: 'log_activity', 'query_status', 'execute_command', 'general_chat'.")
    log_update: LogUpdate = Field(description="The parsed log data if logging an activity.")
    command: str = Field("", description="The whitelisted command to execute on the laptop. Must be empty or one of: 'git status', 'git log -n 5', 'run tests', 'screenshot'.")
    chat_response: str = Field(description="A brief response to send back to the user in chat. Follow the 'Mirror' voice guidelines: concise, direct, semi-formal, avoid fillers.")

def verify_user(update: Update) -> bool:
    if not update.effective_user or str(update.effective_user.id) != TELEGRAM_CHAT_ID:
        return False
    return True

def find_plan_file():
    # Look for complex_accountability_plan.md in standard locations
    if os.path.exists("complex_accountability_plan.md"):
        return os.path.abspath("complex_accountability_plan.md")
    if os.path.exists("../complex_accountability_plan.md"):
        return os.path.abspath("../complex_accountability_plan.md")
    if os.path.exists("../Next_Move/complex_accountability_plan.md"):
        return os.path.abspath("../Next_Move/complex_accountability_plan.md")
    # Default fallback
    return os.path.abspath("complex_accountability_plan.md")

def load_identity_prompt():
    personality_path = "reusable_assets/identity_kernel/personality.yaml"
    logic_gates_path = "reusable_assets/identity_kernel/logic_gates.yaml"
    
    prompt = "You are 'Mirror', a Git-Synced Remote Accountability Agent and digital twin. "
    
    if os.path.exists(personality_path):
        try:
            with open(personality_path, "r", encoding="utf-8") as f:
                personality = f.read()
            prompt += f"\n\nPersonality guidelines to follow:\n{personality}"
        except Exception:
            pass
            
    if os.path.exists(logic_gates_path):
        try:
            with open(logic_gates_path, "r", encoding="utf-8") as f:
                gates = f.read()
            prompt += f"\n\nLogic gates and constraints:\n{gates}"
        except Exception:
            pass
            
    prompt += "\n\nAnalyze the user's message and categorize their intent. You MUST respond with a structured JSON object according to the schema provided."
    return prompt

def sync_git_repo(repo_path, commit_message):
    try:
        repo = git.Repo(repo_path)
        pat = os.getenv("GITHUB_PAT")
        if pat:
            origin = repo.remote(name='origin')
            url = list(origin.urls)[0]
            if "github.com" in url and pat not in url:
                authenticated_url = f"https://Jaiadithya71:{pat}@github.com/Jaiadithya71/Nudge.git"
                repo.git.remote('set-url', 'origin', authenticated_url)
        
        # Pull latest changes
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
                print("Pushed changes to GitHub successfully.")
                return True
            except Exception as e:
                print(f"Error pushing: {e}")
                return False
        else:
            print("No changes to commit.")
            return True
    except Exception as e:
        print(f"Git sync failed: {e}")
        return False

# --- Telegram Bot Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not verify_user(update):
        await update.message.reply_text("Unauthorized user.")
        return
    await update.message.reply_text("Mirror kernel active. Send normal text updates or queries to log progress on your roadmap.")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not verify_user(update):
        await update.message.reply_text("Unauthorized.")
        return
        
    processing_msg = await update.message.reply_text("Retrieving status...")
    
    try:
        plan_path = find_plan_file()
        if not os.path.exists(plan_path):
            await processing_msg.edit_text("Could not locate complex_accountability_plan.md.")
            return
            
        with open(plan_path, "r", encoding="utf-8") as f:
            plan_content = f.read()
            
        client = genai.Client()
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents="Summarize my progress for the current week. Be concise.",
            config=types.GenerateContentConfig(
                system_instruction="You are Mirror. Summarize the user's current week progress from the roadmap plan. Use Markdown tables or lists.",
                contents=[plan_content]
            )
        )
        await processing_msg.edit_text(response.text)
    except Exception as e:
        await processing_msg.edit_text(f"Error fetching status: {str(e)}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not verify_user(update):
        await update.message.reply_text("Unauthorized.")
        return
        
    user_msg = update.message.text
    processing_msg = await update.message.reply_text("Mirror is thinking...")
    
    try:
        # Load system instructions
        system_instruction = load_identity_prompt()
        
        # Read plan context
        plan_path = find_plan_file()
        plan_content = ""
        if os.path.exists(plan_path):
            with open(plan_path, "r", encoding="utf-8") as f:
                plan_content = f.read()
                
        # Call Gemini
        client = genai.Client()
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_msg,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=UserIntent,
                system_instruction=system_instruction + f"\n\nPlan file context:\n{plan_content}",
            ),
        )
        
        result_json = json.loads(response.text)
        intent_type = result_json.get("intent_type")
        chat_response = result_json.get("chat_response", "")
        
        await processing_msg.delete()
        
        if intent_type == "log_activity":
            log_update = result_json.get("log_update", {})
            leetcode_solved = log_update.get("leetcode_solved", 0)
            leetcode_contest = log_update.get("leetcode_contest", 0)
            study_hours = log_update.get("study_hours", 0.0)
            git_commits_cert = log_update.get("git_commits_cert", "")
            notes = log_update.get("notes", "")
            
            if leetcode_solved or leetcode_contest or study_hours or git_commits_cert or notes:
                # import parser dynamically
                sys.path.append(os.path.dirname(os.path.abspath(__file__)))
                from table_parser import update_table
                
                sunday_str = update_table(
                    plan_path,
                    datetime.date.today(),
                    leetcode_solved=leetcode_solved or None,
                    leetcode_contest=leetcode_contest or None,
                    study_hours=study_hours or None,
                    git_commits_cert=git_commits_cert or None,
                    notes=notes or None
                )
                
                # Sync repo
                repo_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                sync_git_repo(repo_path, f"Log: {notes or 'Progress update'} [skip ci]")
                
                await update.message.reply_text(f"{chat_response}\n\n✅ Table updated for week ending {sunday_str}.")
            else:
                await update.message.reply_text(f"Parsed empty updates. {chat_response}")
                
        elif intent_type == "execute_command":
            command = result_json.get("command")
            if command:
                repo_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                queue_path = os.path.join(repo_path, "bot", "command_queue.json")
                
                # Pull first
                try:
                    repo = git.Repo(repo_path)
                    repo.git.pull('origin', 'main')
                except Exception:
                    pass
                
                # Load current queue
                queue = []
                if os.path.exists(queue_path):
                    try:
                        with open(queue_path, "r", encoding="utf-8") as f:
                            queue = json.load(f)
                    except Exception:
                        queue = []
                        
                command_item = {
                    "id": str(uuid.uuid4()),
                    "command": command,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "status": "pending"
                }
                queue.append(command_item)
                
                with open(queue_path, "w", encoding="utf-8") as f:
                    json.dump(queue, f, indent=2)
                    
                sync_git_repo(repo_path, f"Queue command: {command} [skip ci]")
                
                await update.message.reply_text(f"{chat_response}\n\n⏳ Command '{command}' queued for laptop execution.")
            else:
                await update.message.reply_text(f"Could not extract whitelisted command. {chat_response}")
        else:
            await update.message.reply_text(chat_response)
            
    except Exception as e:
        await update.message.reply_text(f"Error handling message: {str(e)}")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not verify_user(update):
        await query.edit_message_text("Unauthorized.")
        return
        
    data = query.data
    status = ""
    if data == "audit_pass":
        status = "Pass"
    elif data == "audit_fail":
        status = "Fail"
    else:
        return
        
    plan_path = find_plan_file()
    try:
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from table_parser import update_table
        
        sunday_str = update_table(
            plan_path,
            datetime.date.today(),
            status=status
        )
        
        repo_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sync_git_repo(repo_path, f"Audit: {status} for week ending {sunday_str} [skip ci]")
        
        await query.edit_message_text(f"Audit recorded: *{status}* for week ending {sunday_str}.")
    except Exception as e:
        await query.edit_message_text(f"Error saving audit status: {str(e)}")

async def sunday_audit_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = TELEGRAM_CHAT_ID
    plan_path = find_plan_file()
    if not os.path.exists(plan_path):
        await context.bot.send_message(chat_id=chat_id, text="Sunday audit failed: plan file not found.")
        return
        
    try:
        with open(plan_path, "r", encoding="utf-8") as f:
            plan_content = f.read()
            
        system_instruction = "You are Mirror. Extract progress details for the current week and write a concise, direct audit summary. End by asking the user to log their status."
        
        client = genai.Client()
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents="Generate weekly accountability report.",
            config=types.GenerateContentConfig(
                system_instruction=system_instruction + f"\n\nPlan file context:\n{plan_content}",
            )
        )
        
        keyboard = [
            [
                InlineKeyboardButton("Pass", callback_data="audit_pass"),
                InlineKeyboardButton("Fail", callback_data="audit_fail")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"📊 *Weekly Audit Summary* 📊\n\n{response.text}\n\nDid you pass your targets?",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"Error during Sunday audit: {str(e)}")

# --- Render/Railway Health Server ---

class HealthCheckHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in ('/', '/health'):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

def start_health_server():
    port = int(os.getenv("PORT", 8080))
    # Allow port reuse to avoid 'Address already in use' errors
    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(("", port), HealthCheckHandler)
    print(f"Starting health check server on port {port}")
    server.serve_forever()

async def main():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Error: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env")
        sys.exit(1)
        
    # Start health server in daemon thread
    threading.Thread(target=start_health_server, daemon=True).start()
    
    # Initialize Bot Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Sunday 9:00 PM IST is 3:30 PM UTC
    import zoneinfo
    ist = zoneinfo.ZoneInfo("Asia/Kolkata")
    target_time = datetime.time(hour=21, minute=0, second=0, tzinfo=ist)
    
    application.job_queue.run_daily(sunday_audit_job, time=target_time, days=(6,))
    
    print("Mirror Telegram Bot daemon starting...")
    
    # Run polling loop
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    # Keep the async loop alive
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped by user.")

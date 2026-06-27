import os
import subprocess
import sqlite3

def handle_screenshot(cmd_text, nudge_dir, config):
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
            return f"Screenshot capture failed: {str(e2)}"
            
    if captured:
        return ("photo", screenshot_path, "💻 Laptop Screenshot")
    return "Screenshot failed."

def handle_query_db(cmd_text, nudge_dir, config):
    search_name = cmd_text[9:]
    db_path = r"C:\Users\jaiad\Personal_Work_Related\Personal Projects\Data extraction project\local_data_pipeline\sastra_data.db"
    
    if not os.path.exists(db_path):
        return f"⚠️ Database file not found at: {db_path}"
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        
        results = []
        for table in tables:
            # Get table schema/columns
            cursor.execute(f"PRAGMA table_info({table});")
            columns = [col[1] for col in cursor.fetchall()]
            
            # Construct a query searching across all columns
            conditions = []
            params = []
            for col in columns:
                conditions.append(f'"{col}" LIKE ?')
                params.append(f"%{search_name}%")
                
            query = f"SELECT * FROM {table} WHERE " + " OR ".join(conditions)
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            if rows:
                results.append(f"📊 *Table: {table}*")
                headers = " | ".join(columns)
                results.append(f"`{headers}`")
                for row in rows:
                    row_str = " | ".join(str(val) for val in row)
                    results.append(f"- {row_str}")
                    
        conn.close()
        
        if results:
            return "\n".join(results)
        else:
            return f"No records found for '{search_name}' in database."
    except Exception as e:
        return f"Database query failed: {str(e)}"

def handle_shell_command(cmd_text, nudge_dir, config):
    # Whitelisted shell commands mapping
    whitelisted_cmds = {
        "git status": ("git status", nudge_dir),
        "git log -n 5": ("git log -n 5", nudge_dir),
        "run tests": ("npm run test", r"C:\Users\jaiad\Personal_Work_Related\Personal Projects\This-or-That")
    }
    
    if cmd_text not in whitelisted_cmds:
        return f"⚠️ Command '{cmd_text}' is not whitelisted."
        
    shell_cmd, cwd_dir = whitelisted_cmds[cmd_text]
    
    if cmd_text == "run tests" and not os.path.exists(cwd_dir):
        cwd_dir = nudge_dir
        shell_cmd = "echo 'No tests configured for workspace.'"
        
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
        
    return output_msg

def dispatch_command(cmd_text, nudge_dir, config):
    """
    Route commands to their respective modular handlers.
    Returns either a string (for text messages) or a tuple ('photo', path, caption).
    """
    if cmd_text == "screenshot":
        return handle_screenshot(cmd_text, nudge_dir, config)
    elif cmd_text.startswith("query DB "):
        return handle_query_db(cmd_text, nudge_dir, config)
    else:
        return handle_shell_command(cmd_text, nudge_dir, config)

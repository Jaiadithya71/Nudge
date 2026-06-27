import os
import datetime

def parse_date(date_str):
    # Strip asterisks
    date_str = date_str.replace("**", "").strip()
    try:
        return datetime.datetime.strptime(date_str, "%B %d, %Y").date()
    except ValueError:
        # Try short month name fallback
        try:
            return datetime.datetime.strptime(date_str, "%b %d, %Y").date()
        except ValueError:
            return None

def format_date(date_obj):
    month = date_obj.strftime("%B")
    day = str(date_obj.day)
    year = date_obj.strftime("%Y")
    return f"**{month} {day}, {year}**"

def update_table(file_path, date_obj, leetcode_solved=None, leetcode_contest=None, study_hours=None, git_commits_cert=None, notes=None, status=None):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.splitlines()
    
    # Locate the table
    # We look for the header row: | Week Ending | LeetCode Solved
    header_idx = -1
    for idx, line in enumerate(lines):
        if "Week Ending" in line and "LeetCode Solved" in line and line.strip().startswith("|"):
            header_idx = idx
            break

    if header_idx == -1:
        raise ValueError("Could not find the Weekly Self-Audit Dashboard table in the plan file.")

    separator_idx = header_idx + 1
    if separator_idx >= len(lines) or not lines[separator_idx].strip().startswith("|"):
        raise ValueError("Invalid table format: separator row missing.")

    # Parse rows
    row_idx = separator_idx + 1
    table_rows = []
    end_of_table_idx = len(lines)
    
    for idx in range(row_idx, len(lines)):
        line = lines[idx].strip()
        if not line.startswith("|"):
            end_of_table_idx = idx
            break
        
        # Parse the cells
        cells = [c.strip() for c in line.split("|")[1:-1]]
        table_rows.append((idx, cells))

    # Calculate target Sunday date
    days_to_sunday = (6 - date_obj.weekday()) % 7
    target_sunday = date_obj + datetime.timedelta(days=days_to_sunday)
    target_sunday_str = format_date(target_sunday)
    
    # Search if target Sunday exists
    found = False
    updated_rows = []
    
    for idx, cells in table_rows:
        row_date = parse_date(cells[0])
        if row_date == target_sunday:
            found = True
            # Update cells
            # 1: LeetCode Solved
            if leetcode_solved is not None:
                val = 0
                try:
                    val = int(cells[1]) if cells[1] else 0
                except ValueError:
                    pass
                cells[1] = str(val + leetcode_solved)
                
            # 2: LeetCode Contest
            if leetcode_contest is not None:
                val = 0
                try:
                    val = int(cells[2]) if cells[2] else 0
                except ValueError:
                    pass
                cells[2] = str(val + leetcode_contest)
                
            # 3: Study Hours
            if study_hours is not None:
                val = 0.0
                try:
                    val = float(cells[3]) if cells[3] else 0.0
                except ValueError:
                    pass
                cells[3] = f"{val + study_hours:.1f}"
                
            # 4: Git Commits / Cert Prep
            if git_commits_cert is not None:
                if cells[4]:
                    cells[4] = f"{cells[4]}; {git_commits_cert}"
                else:
                    cells[4] = git_commits_cert
                    
            # 5: Notes
            if notes is not None:
                if cells[5]:
                    cells[5] = f"{cells[5]}; {notes}"
                else:
                    cells[5] = notes
                    
            # 6: Status
            if status is not None:
                cells[6] = status
                
        updated_rows.append((row_date, cells))

    if not found:
        # Create a new row
        cells = [
            target_sunday_str,
            str(leetcode_solved) if leetcode_solved is not None else "",
            str(leetcode_contest) if leetcode_contest is not None else "",
            f"{study_hours:.1f}" if study_hours is not None else "",
            git_commits_cert if git_commits_cert is not None else "",
            notes if notes is not None else "",
            status if status is not None else ""
        ]
        updated_rows.append((target_sunday, cells))

    # Sort updated rows chronologically
    valid_rows = [r for r in updated_rows if r[0] is not None]
    invalid_rows = [r for r in updated_rows if r[0] is None]
    
    valid_rows.sort(key=lambda x: x[0])
    
    all_final_rows = valid_rows + invalid_rows
    
    # Format rows back to Markdown lines
    formatted_lines = []
    for date_val, cells in all_final_rows:
        line_str = "| " + " | ".join(cells) + " |"
        formatted_lines.append(line_str)

    # Reconstruct the file content
    new_lines = lines[:separator_idx + 1] + formatted_lines + lines[end_of_table_idx:]
    new_content = "\n".join(new_lines)
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    return target_sunday_str

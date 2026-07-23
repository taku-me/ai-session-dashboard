import os
import json
import glob
from pathlib import Path
from datetime import datetime

# File paths for custom titles, archived sessions, and commander history
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

CUSTOM_TITLES_FILE = DATA_DIR / "custom_titles.json"
ARCHIVED_SESSIONS_FILE = DATA_DIR / "archived_sessions.json"
COMMANDER_HISTORY_FILE = DATA_DIR / "commander_history.json"

def get_custom_titles():
    if CUSTOM_TITLES_FILE.exists():
        try:
            with open(CUSTOM_TITLES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def set_custom_title(session_id, title):
    titles = get_custom_titles()
    titles[session_id] = title
    with open(TITLES_FILE, 'w', encoding='utf-8') as f:
        json.dump(titles, f, ensure_ascii=False, indent=2)
    return title

def get_claude_session_names():
    names = {}
    claude_dir = Path.home() / '.claude'
    if claude_dir.exists():
        for sf in claude_dir.glob('sessions/*.json'):
            try:
                with open(sf, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    sess_id = data.get('sessionId')
                    name = data.get('name')
                    if sess_id and name:
                        names[sess_id] = name
            except Exception:
                pass
    return names

def get_archived_session_ids():
    if ARCHIVED_SESSIONS_FILE.exists():
        try:
            with open(ARCHIVED_SESSIONS_FILE, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def toggle_archive_session(session_id):
    archived = get_archived_session_ids()
    if session_id in archived:
        archived.remove(session_id)
        is_archived = False
    else:
        archived.add(session_id)
        is_archived = True
        
    with open(ARCHIVED_SESSIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(archived), f, ensure_ascii=False, indent=2)
    return is_archived

def check_needs_review(session_type: str, last_role: str, last_message: str) -> bool:
    """Detect if the session requires user attention or feedback."""
    if not last_message:
        return False
    # If the last message was from Assistant/Model
    if last_role in ('assistant', 'model', 'PLANNER_RESPONSE'):
        keywords = ['確認', 'いかが', 'でしょうか', 'よろしいですか', 'ご指定', '教えて', '選んで', '?', '？', 'input', 'select', 'proceed']
        msg_lower = last_message.lower()
        if any(k in msg_lower for k in keywords):
            return True
        # If assistant just finished a response and is waiting
        return True
    return False

def parse_sessions(include_archived=False):
    sessions = []
    archived_ids = get_archived_session_ids()
    custom_titles = get_custom_titles()
    claude_names = get_claude_session_names()
    
    # 1. Parse atoTerminal Sessions (~/.ato/sessions/*.json)
    ato_dir = Path.home() / '.ato'
    if ato_dir.exists():
        for session_file in ato_dir.glob('sessions/*.json'):
            session_id = session_file.stem
            is_archived = session_id in archived_ids
            if is_archived and not include_archived:
                continue
                
            try:
                with open(session_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    histories = data.get('histories', {})
                    models = list(histories.keys()) if isinstance(histories, dict) else []
                    model_name = ", ".join(models) if models else data.get('model', 'Unknown Model')
                    
                    all_messages = []
                    if isinstance(histories, dict):
                        for model_key, msgs in histories.items():
                            if isinstance(msgs, list):
                                all_messages.extend(msgs)
                    elif isinstance(data.get('messages'), list):
                        all_messages = data.get('messages', [])

                    last_message = ""
                    last_role = "user"
                    if all_messages:
                        last_msg_obj = all_messages[-1]
                        if isinstance(last_msg_obj, dict):
                            last_role = last_msg_obj.get('role', 'user')
                            content = last_msg_obj.get('content', '')
                            if isinstance(content, str):
                                last_message = content[:150]
                            elif isinstance(content, list):
                                text_parts = [p.get('text', '') for p in content if isinstance(p, dict) and 'text' in p]
                                last_message = " ".join(text_parts)[:150]

                    project_name = data.get('project') or data.get('name') or 'atoTerminal'
                    updated_at = data.get('updated_at') or datetime.fromtimestamp(session_file.stat().st_mtime).isoformat()
                    display_name = custom_titles.get(session_id) or project_name
                    needs_rev = check_needs_review("ato", last_role, last_message)
                    is_recent = (datetime.now() - datetime.fromtimestamp(session_file.stat().st_mtime)).total_seconds() < 86400

                    is_subagent = False
                    if "subagent" in display_name.lower() or "subagent" in last_message.lower():
                        is_subagent = True

                    sessions.append({
                        "id": session_id,
                        "type": "ato",
                        "project": project_name,
                        "title": display_name,
                        "model": model_name,
                        "message_count": len(all_messages),
                        "last_message": last_message or "会話ログあり",
                        "updated_at": updated_at,
                        "is_archived": is_archived,
                        "needs_review": needs_rev,
                        "is_recent": is_recent,
                        "is_subagent": is_subagent
                    })
            except Exception as e:
                print(f"Error parsing ato session {session_file}: {e}")

    # 2. Parse Claude Code Sessions (~/.claude/projects/*/<session_id>.jsonl)
    claude_dir = Path.home() / '.claude'
    if claude_dir.exists():
        projects_dir = claude_dir / 'projects'
        if projects_dir.exists():
            for proj_dir in projects_dir.iterdir():
                if not proj_dir.is_dir():
                    continue
                for jsonl_file in proj_dir.glob('*.jsonl'):
                    s_id = jsonl_file.stem
                    if len(s_id) < 10:
                        continue
                        
                    is_archived = s_id in archived_ids
                    if is_archived and not include_archived:
                        continue
                        
                    try:
                        first_user_text = ""
                        last_text = ""
                        last_role = "user"
                        actual_cwd = ""
                        msg_count = 0
                        
                        with open(jsonl_file, 'r', encoding='utf-8') as f:
                            for line in f:
                                lstr = line.strip()
                                if not lstr:
                                    continue
                                try:
                                    item = json.loads(lstr)
                                    msg_type = item.get('type')
                                    
                                    if not actual_cwd and item.get('cwd'):
                                        actual_cwd = item.get('cwd')
                                        
                                    if msg_type in ('user', 'assistant'):
                                        msg_count += 1
                                        last_role = msg_type
                                        msg_obj = item.get('message', {})
                                        content = msg_obj.get('content', '')
                                        
                                        text_content = ""
                                        if isinstance(content, str):
                                            text_content = content
                                        elif isinstance(content, list):
                                            parts = []
                                            for part in content:
                                                if isinstance(part, dict) and part.get('type') == 'text':
                                                    parts.append(part.get('text', ''))
                                                elif isinstance(part, str):
                                                    parts.append(part)
                                            text_content = "\n".join(parts)
                                            
                                        if text_content.strip():
                                            if not first_user_text and msg_type == 'user':
                                                first_user_text = text_content[:80]
                                            last_text = text_content[:150]
                                except Exception:
                                    continue
                                    
                        if not actual_cwd:
                            raw_dirname = proj_dir.name
                            if raw_dirname.startswith('-'):
                                actual_cwd = '/' + raw_dirname[1:].replace('-', '/')
                                
                        proj_display = Path(actual_cwd).name if actual_cwd else proj_dir.name
                        updated_at = datetime.fromtimestamp(jsonl_file.stat().st_mtime).isoformat()
                        needs_rev = check_needs_review("claude", last_role, last_text)
                        is_recent = (datetime.now() - datetime.fromtimestamp(jsonl_file.stat().st_mtime)).total_seconds() < 86400

                        display_title = custom_titles.get(s_id) or claude_names.get(s_id) or first_user_text or f"claude-{s_id[:8]}"

                        # Subagent detection for Claude (only genuine internal subagents)
                        is_subagent = False
                        if "--claude-worktrees-" in proj_dir.name or first_user_text.startswith("Task description:") or "このセッションの会話から、以下" in first_user_text:
                            is_subagent = True

                        sessions.append({
                            "id": s_id,
                            "type": "claude",
                            "project": proj_display,
                            "project_dir": actual_cwd or str(Path.home()),
                            "title": display_title,
                            "model": "Claude Code",
                            "message_count": msg_count or 1,
                            "last_message": last_text or "対話ログあり",
                            "updated_at": updated_at,
                            "is_archived": is_archived,
                            "needs_review": needs_rev,
                            "is_recent": is_recent,
                            "is_subagent": is_subagent
                        })
                    except Exception as e:
                        print(f"Error parsing claude jsonl {jsonl_file}: {e}")

    # 3. Parse agy (Antigravity CLI) Sessions (~/.gemini/antigravity-cli/brain/<uuid>/)
    gemini_dir = Path.home() / '.gemini' / 'antigravity-cli' / 'brain'
    if gemini_dir.exists():
        for sess_dir in gemini_dir.iterdir():
            if not sess_dir.is_dir():
                continue
            sess_id = sess_dir.name
            is_archived = sess_id in archived_ids
            if is_archived and not include_archived:
                continue
                
            transcript_file = sess_dir / '.system_generated' / 'logs' / 'transcript.jsonl'
            if transcript_file.exists():
                try:
                    all_lines = []
                    first_user_req = ""
                    last_msg = ""
                    last_role = ""
                    is_subagent = False
                    
                    with open(transcript_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            lstr = line.strip()
                            if lstr:
                                all_lines.append(lstr)
                                
                    if all_lines:
                        try:
                            item0 = json.loads(all_lines[0])
                            content = item0.get('content', '')
                            if '<USER_REQUEST>' in content:
                                req = content.split('<USER_REQUEST>')[1].split('</USER_REQUEST>')[0].strip()
                                first_user_req = req.split('\n')[0][:80]
                            else:
                                first_user_req = content[:80]
                                
                            if '<USER_REQUEST>' not in content and ('Subagent:' in content or 'invoke_subagent' in content or 'Role:' in content):
                                is_subagent = True
                        except Exception:
                            first_user_req = "agy session"

                        try:
                            item_last = json.loads(all_lines[-1])
                            last_role = item_last.get('type', '')
                            last_content = item_last.get('content', '')
                            if isinstance(last_content, str):
                                last_msg = last_content[:150]
                            elif isinstance(last_content, list):
                                last_msg = str(last_content)[:150]
                        except Exception:
                            last_msg = "操作ログあり"

                        updated_at = datetime.fromtimestamp(transcript_file.stat().st_mtime).isoformat()
                        needs_rev = check_needs_review("agy", last_role, last_msg)
                        is_recent = (datetime.now() - datetime.fromtimestamp(transcript_file.stat().st_mtime)).total_seconds() < 86400

                        sessions.append({
                            "id": sess_id,
                            "type": "agy",
                            "project": "Antigravity",
                            "project_dir": str(Path.home()),
                            "title": custom_titles.get(sess_id) or first_user_req or f"agy-{sess_id[:8]}",
                            "model": "Gemini (AGY)",
                            "message_count": len(all_lines),
                            "last_message": last_msg or "対話ログあり",
                            "updated_at": updated_at,
                            "is_archived": is_archived,
                            "needs_review": needs_rev,
                            "is_recent": is_recent,
                            "is_subagent": is_subagent
                        })
                except Exception as e:
                    print(f"Error parsing agy session {sess_dir}: {e}")

    # Sort by updated_at desc
    sessions.sort(key=lambda x: str(x.get('updated_at', '')), reverse=True)
    return sessions

def delete_session(session_type: str, session_id: str):
    try:
        if session_type == 'ato':
            session_file = Path.home() / '.ato' / 'sessions' / f"{session_id}.json"
            if session_file.exists():
                session_file.unlink()
                return {"status": "success", "session_id": session_id}
        elif session_type == 'agy':
            sess_dir = Path.home() / '.gemini' / 'antigravity-cli' / 'brain' / session_id
            if sess_dir.exists() and sess_dir.is_dir():
                import shutil
                shutil.rmtree(sess_dir)
                return {"status": "success", "session_id": session_id}
        elif session_type == 'claude':
            # Remove session metadata if exists
            claude_dir = Path.home() / '.claude'
            for sf in claude_dir.glob('sessions/*.json'):
                try:
                    with open(sf, 'r', encoding='utf-8') as f:
                        d = json.load(f)
                        if d.get('sessionId') == session_id:
                            sf.unlink()
                except Exception:
                    pass
            # Mark in archive file as deleted
            toggle_archive_session(session_id)
            return {"status": "success", "session_id": session_id}
            
        return {"status": "error", "message": "Session file not found"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_stats():
    sessions = parse_sessions()
    ato_count = sum(1 for s in sessions if s['type'] == 'ato')
    claude_count = sum(1 for s in sessions if s['type'] == 'claude')
    agy_count = sum(1 for s in sessions if s['type'] == 'agy')
    
    projects = set(s['project'] for s in sessions if s.get('project'))
    
    latest_activity = "None"
    if sessions:
        latest_activity = sessions[0]['updated_at']
        
    return {
        "ato_sessions": ato_count,
        "claude_sessions": claude_count,
        "agy_sessions": agy_count,
        "total_projects": len(projects),
        "latest_activity": latest_activity
    }

def get_projects():
    sessions = parse_sessions()
    projects = set(s['project'] for s in sessions if s.get('project'))
    return [{"name": p} for p in projects]

def get_session_details(session_type, session_id):
    if session_type == 'ato':
        session_file = Path.home() / '.ato' / 'sessions' / f"{session_id}.json"
        if session_file.exists():
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                histories = data.get('histories', {})
                all_messages = []
                if isinstance(histories, dict):
                    for model_key, msgs in histories.items():
                        if isinstance(msgs, list):
                            all_messages.extend(msgs)
                elif isinstance(data.get('messages'), list):
                    all_messages = data.get('messages', [])
                
                return {
                    "id": session_id,
                    "type": "ato",
                    "project": data.get('project') or data.get('name') or 'atoTerminal',
                    "model": ", ".join(histories.keys()) if isinstance(histories, dict) else "ato",
                    "messages": all_messages
                }
    elif session_type == 'claude':
        # Search for project session log file: ~/.claude/projects/*/<session_id>.jsonl
        claude_dir = Path.home() / '.claude'
        session_file = None
        if claude_dir.exists():
            matches = list(claude_dir.glob(f"projects/*/{session_id}.jsonl"))
            if matches:
                session_file = matches[0]

        if session_file and session_file.exists():
            messages = []
            try:
                with open(session_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line_str = line.strip()
                        if not line_str:
                            continue
                        try:
                            item = json.loads(line_str)
                            msg_type = item.get('type')
                            
                            # Parse User or Assistant message
                            if msg_type in ('user', 'assistant'):
                                msg_obj = item.get('message', {})
                                content = msg_obj.get('content', '')
                                
                                text_content = ""
                                if isinstance(content, str):
                                    text_content = content
                                elif isinstance(content, list):
                                    parts = []
                                    for part in content:
                                        if isinstance(part, dict):
                                            if part.get('type') == 'text':
                                                parts.append(part.get('text', ''))
                                            elif part.get('type') == 'tool_use':
                                                parts.append(f"*[Tool Call: {part.get('name')}]*")
                                        elif isinstance(part, str):
                                            parts.append(part)
                                    text_content = "\n".join(parts)
                                    
                                if text_content.strip():
                                    messages.append({
                                        "role": msg_type,
                                        "content": text_content,
                                        "timestamp": item.get('timestamp')
                                    })
                        except Exception:
                            continue
                return {
                    "id": session_id,
                    "type": "claude",
                    "project": session_file.parent.name,
                    "model": "Claude Code",
                    "messages": messages
                }
            except Exception as e:
                print(f"Error parsing claude jsonl {session_file}: {e}")

        # Fallback to history.jsonl
        history_file = claude_dir / 'history.jsonl'
        if history_file.exists():
            items = []
            with open(history_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        try:
                            item = json.loads(line)
                            if item.get('sessionId') == session_id or session_id == 'default-claude':
                                items.append({
                                    "role": "user",
                                    "content": item.get('display', ''),
                                    "timestamp": item.get('timestamp')
                                })
                        except Exception:
                            continue
            return {
                "id": session_id,
                "type": "claude",
                "project": "Claude Code",
                "model": "Claude Code",
                "messages": items
            }
    elif session_type == 'agy':
        transcript_file = Path.home() / '.gemini' / 'antigravity-cli' / 'brain' / session_id / '.system_generated' / 'logs' / 'transcript.jsonl'
        if transcript_file.exists():
            items = []
            with open(transcript_file, 'r', encoding='utf-8') as f:
                for line in f:
                    lstr = line.strip()
                    if lstr:
                        try:
                            item = json.loads(lstr)
                            stype = item.get('type', '')
                            content = item.get('content') or item.get('thinking') or ''
                            if stype in ('USER_INPUT', 'PLANNER_RESPONSE', 'MODEL') and content:
                                role = 'user' if stype == 'USER_INPUT' else 'assistant'
                                if '<USER_REQUEST>' in str(content):
                                    content = content.split('<USER_REQUEST>')[1].split('</USER_REQUEST>')[0].strip()
                                items.append({
                                    "role": role,
                                    "content": str(content)
                                })
                        except Exception:
                            continue
            return {
                "id": session_id,
                "type": "agy",
                "project": "Antigravity",
                "model": "Gemini (AGY)",
                "messages": items
            }
            
    return {"error": "Session not found"}

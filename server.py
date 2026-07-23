from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import sys
from pathlib import Path

from pydantic import BaseModel
from datetime import datetime
import json
import session_parser

app = FastAPI(title="atoTerminal & Claude Code Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
class ArchiveRequest(BaseModel):
    session_id: str

class RenameRequest(BaseModel):
    session_id: str
    title: str

class DeleteRequest(BaseModel):
    session_type: str
    session_id: str

class ResumeRequest(BaseModel):
    session_type: str
    session_id: str
    project: str = None
    title: str = None

import subprocess
import shutil
import re
import threading
import time

def resolve_project_path(project_dir: str) -> str:
    if not project_dir or project_dir == "Global":
        return str(Path.home())
    
    # 1. Direct path check
    p = Path(project_dir)
    if p.exists():
        return str(p.resolve())
        
    # 2. Fast direct lookups in common roots (No recursive glob!)
    common_roots = [
        Path("/Volumes/NVME202502/projects"),
        Path.home() / "projects",
        Path.home() / "Library/CloudStorage/Dropbox/_inbox",
        Path.home(),
        Path("/Volumes/NVME202502"),
    ]
    
    for root in common_roots:
        if root.exists():
            candidate = root / project_dir
            if candidate.exists():
                return str(candidate.resolve())
                
    return str(Path.home())

def _exec_resume_async(session_type: str, session_id: str, project_dir: str = None, title: str = None, req_time: float = 0):
    start_t = time.time()
    print(f"⏱️ [PERF-LOG] [{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Resume task started (OS: {sys.platform})")
    
    # Fast path resolution
    target_dir = resolve_project_path(project_dir)
    t_resolved = time.time()
    print(f"⏱️ [PERF-LOG] [{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Path resolved to '{target_dir}' in {(t_resolved - start_t)*1000:.1f}ms")

    if session_type == 'claude':
        cmd_str = f"claude --resume '{session_id}'" if sys.platform != 'win32' else f"claude --resume \"{session_id}\""
        tab_title = f"Claude: {title or session_id[:8]}"
        post_send_cmd = None
    elif session_type == 'agy':
        cmd_str = "agy"
        tab_title = f"AGY: {title or session_id[:8]}"
        post_send_cmd = None
    else:
        cmd_str = "uv run ato"
        tab_title = f"ato: {title or session_id[:8]}"
        post_send_cmd = f"/session load {session_id}"

    # 1. Windows Platform -> Windows Terminal (wt.exe)
    if sys.platform == 'win32':
        wt_bin = shutil.which("wt.exe") or "wt.exe"
        try:
            wt_cmd = [wt_bin, "-w", "0", "nt", "--title", tab_title, "-d", target_dir, "cmd", "/k", cmd_str]
            subprocess.Popen(wt_cmd)
            print(f"⏱️ [PERF-LOG] Launched via Windows Terminal (wt.exe): {wt_cmd}")
            return
        except Exception as e:
            print(f"❌ [PERF-LOG] wt.exe launch error: {e}")
            return

    # 2. macOS Platform -> cmux
    cmux_bin = shutil.which("cmux") or "/Applications/cmux.app/Contents/Resources/bin/cmux"
    env = os.environ.copy()

    if os.path.exists(cmux_bin):
        try:
            t_before_pane = time.time()
            full_cmd_str = f"cd '{target_dir}' && {cmd_str}"
            
            # Find terminal pane (default pane:1)
            tree_res = subprocess.run([f"'{cmux_bin}'", "tree", "--workspace", "workspace:1"], shell=True, capture_output=True, text=True, timeout=2, env=env)
            terminal_pane = "pane:1"
            if tree_res.returncode == 0:
                for line in tree_res.stdout.splitlines():
                    if "pane:" in line:
                        m_pane = re.search(r'pane:\d+', line)
                        if m_pane:
                            current_pane = m_pane.group(0)
                    if "[terminal]" in line and 'current_pane' in locals():
                        terminal_pane = current_pane
                        break

            # Create a NEW TAB (surface) inside the terminal pane instead of a new pane
            new_surf_cmd = f"'{cmux_bin}' new-surface --pane {terminal_pane}"
            res = subprocess.run(new_surf_cmd, shell=True, capture_output=True, text=True, timeout=3, env=env)
            t_after_pane = time.time()
            print(f"⏱️ [PERF-LOG] [{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] cmux new-surface finished (took {(t_after_pane - t_before_pane)*1000:.1f}ms, out: {res.stdout.strip()})")
            
            if res.returncode == 0:
                m_surf = re.search(r'surface:\d+', res.stdout)
                if m_surf:
                    target_surface = m_surf.group(0)
                    time.sleep(0.4)
                    
                    t_before_send = time.time()
                    escaped_cmd = full_cmd_str.replace("'", "'\\''")
                    send_cmd = f"'{cmux_bin}' send --surface {target_surface} '{escaped_cmd}\n'"
                    subprocess.run(send_cmd, shell=True, capture_output=True, timeout=3, env=env)
                    
                    key_cmd = f"'{cmux_bin}' send-key --surface {target_surface} enter"
                    subprocess.run(key_cmd, shell=True, capture_output=True, timeout=3, env=env)
                    
                    rename_cmd = f"'{cmux_bin}' rename-tab --surface {target_surface} '{tab_title}'"
                    subprocess.run(rename_cmd, shell=True, capture_output=True, timeout=3, env=env)

                    # If ato session, send /session load after REPL boots
                    if post_send_cmd:
                        def _send_post_cmd():
                            time.sleep(2.5) # Wait for ato REPL boot
                            escaped_post = post_send_cmd.replace("'", "'\\''")
                            subprocess.run(f"'{cmux_bin}' send --surface {target_surface} '{escaped_post}\n'", shell=True, env=env)
                            subprocess.run(f"'{cmux_bin}' send-key --surface {target_surface} enter", shell=True, env=env)
                            print(f"⏱️ [PERF-LOG] Auto-loaded ato session with {post_send_cmd}")
                        threading.Thread(target=_send_post_cmd, daemon=True).start()
                    
                    t_after_send = time.time()
                    total_elapsed = (t_after_send - start_t) * 1000
                    print(f"⏱️ [PERF-LOG] [{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] ✅ cmux tab created and command sent to {target_surface} (send took {(t_after_send - t_before_send)*1000:.1f}ms | Total backend elapsed: {total_elapsed:.1f}ms)")
                    return
        except Exception as e:
            print(f"❌ [PERF-LOG] cmux launch error: {e}")

    # Fallback to AppleScript
    try:
        full_cmd_str = f"cd '{target_dir}' && {cmd_str}"
        script = f'tell application "Terminal" to do script "{full_cmd_str}"'
        subprocess.run(["osascript", "-e", script], timeout=3)
        print(f"⏱️ [PERF-LOG] Launched via AppleScript Terminal")
    except Exception as e:
        print(f"❌ [PERF-LOG] Terminal app launch error: {e}")

def launch_resume_session(session_type: str, session_id: str, project_dir: str = None, title: str = None):
    req_time = time.time()
    t_str = datetime.fromtimestamp(req_time).strftime('%H:%M:%S.%f')[:-3]
    print(f"\n⏱️ [PERF-LOG] [{t_str}] HTTP /api/sessions/resume received for {session_type}:{session_id}")
    
    t = threading.Thread(target=_exec_resume_async, args=(session_type, session_id, project_dir, title, req_time), daemon=True)
    t.start()
    return {
        "status": "success",
        "requested_at": t_str,
        "message": "Launch command dispatched in background"
    }

@app.get("/api/stats")
def get_stats():
    return session_parser.get_stats()

@app.get("/api/sessions")
def get_sessions(type: str = None, project: str = None, search: str = None, include_archived: bool = False, limit: int = 100):
    sessions = session_parser.parse_sessions(include_archived=include_archived)
    
    if type:
        sessions = [s for s in sessions if s.get("type") == type]
    if project:
        sessions = [s for s in sessions if s.get("project") == project]
    if search:
        search_lower = search.lower()
        sessions = [s for s in sessions if search_lower in s.get("last_message", "").lower() or search_lower in s.get("project", "").lower() or search_lower in s.get("title", "").lower() or search_lower in s.get("id", "").lower()]
        
    return sessions[:limit]

@app.post("/api/sessions/archive")
def archive_session(req: ArchiveRequest):
    is_archived = session_parser.toggle_archive_session(req.session_id)
    return {"status": "success", "session_id": req.session_id, "is_archived": is_archived}

@app.post("/api/sessions/rename")
def rename_session(req: RenameRequest):
    new_title = session_parser.set_custom_title(req.session_id, req.title)
    return {"status": "success", "session_id": req.session_id, "title": new_title}

@app.post("/api/sessions/delete")
def delete_session(req: DeleteRequest):
    return session_parser.delete_session(req.session_type, req.session_id)

@app.post("/api/sessions/resume")
def resume_session(req: ResumeRequest):
    return launch_resume_session(req.session_type, req.session_id, req.project, req.title)

@app.get("/api/sessions/{session_type}/{session_id}")
def get_session_detail(session_type: str, session_id: str):
    return session_parser.get_session_details(session_type, session_id)

@app.get("/api/projects")
def get_projects():
    return session_parser.get_projects()

# Serve static files
current_dir = Path(__file__).parent
static_dir = current_dir / "static"

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Commander API Routes
class DispatchRequest(BaseModel):
    target: str
    instruction: str

commander_history_file = current_dir / "data" / "commander_history.json"

def _exec_commander_dispatch_async(target: str, instruction: str):
    cmux_bin = shutil.which("cmux") or "/Applications/cmux.app/Contents/Resources/bin/cmux"
    env = os.environ.copy()
    
    if not os.path.exists(cmux_bin):
        print(f"⚠️ [COMMANDER] cmux bin not found")
        return

    try:
        # Find all active surfaces
        tree_res = subprocess.run([f"'{cmux_bin}'", "tree", "--workspace", "workspace:1"], shell=True, capture_output=True, text=True, timeout=3, env=env)
        surfaces = []
        if tree_res.returncode == 0:
            for line in tree_res.stdout.splitlines():
                if "surface:" in line and "[terminal]" in line:
                    m_surf = re.search(r'surface:\d+', line)
                    if m_surf:
                        surfaces.append(m_surf.group(0))

        escaped_instruction = instruction.replace("'", "'\\''")
        
        for surf in surfaces:
            send_cmd = f"'{cmux_bin}' send --surface {surf} '{escaped_instruction}\n'"
            subprocess.run(send_cmd, shell=True, capture_output=True, timeout=3, env=env)
            key_cmd = f"'{cmux_bin}' send-key --surface {surf} enter"
            subprocess.run(key_cmd, shell=True, capture_output=True, timeout=3, env=env)
            print(f"👑 [COMMANDER] Dispatched instruction to {surf}")

    except Exception as e:
        print(f"❌ [COMMANDER] Dispatch error: {e}")

@app.post("/api/commander/dispatch")
def dispatch_command(req: DispatchRequest):
    try:
        if commander_history_file.exists():
            with open(commander_history_file, 'r', encoding='utf-8') as f:
                try:
                    history = json.load(f)
                except Exception:
                    history = []
        else:
            history = []
            
        entry = {
            "id": f"cmd_{int(datetime.now().timestamp())}",
            "timestamp": datetime.now().isoformat(),
            "target": req.target,
            "instruction": req.instruction,
            "status": "dispatched"
        }
        history.append(entry)
        
        commander_history_file.parent.mkdir(exist_ok=True)
        with open(commander_history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
            
        # Dispatch command to cmux in background thread
        t = threading.Thread(target=_exec_commander_dispatch_async, args=(req.target, req.instruction), daemon=True)
        t.start()

        return {"status": "success", "entry": entry}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/commander/history")
def get_commander_history():
    if commander_history_file.exists():
        try:
            with open(commander_history_file, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

@app.get("/")
def serve_index():
    return FileResponse(str(static_dir / "index.html"))

if __name__ == "__main__":
    uvicorn.run("dashboard.server:app", host="0.0.0.0", port=8888, reload=True)

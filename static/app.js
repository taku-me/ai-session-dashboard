document.addEventListener('DOMContentLoaded', () => {
    const statsContainer = document.getElementById('stats-container');
    const sessionsContainer = document.getElementById('sessions-container');
    const searchInput = document.getElementById('search-input');
    const typeFilter = document.getElementById('type-filter');
    const refreshBtn = document.getElementById('refresh-btn');
    const modal = document.getElementById('session-modal');
    const closeModalBtn = document.getElementById('close-modal');
    const modalBody = document.getElementById('modal-body');

    // Commander UI Elements
    const commanderBtn = document.getElementById('commander-btn');
    const commanderPanel = document.getElementById('commander-panel');
    const commanderTarget = document.getElementById('commander-target');
    const commanderInstruction = document.getElementById('commander-instruction');
    const commanderDispatchBtn = document.getElementById('commander-dispatch-btn');
    const commanderTimeline = document.getElementById('commander-timeline');

    // Toggle Commander Panel
    if (commanderBtn && commanderPanel) {
        commanderBtn.addEventListener('click', () => {
            if (commanderPanel.style.display === 'none' || !commanderPanel.style.display) {
                commanderPanel.style.display = 'block';
                commanderPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                fetchCommanderHistory();
            } else {
                commanderPanel.style.display = 'none';
            }
        });
    }

    // Fetch and render commander history
    async function fetchCommanderHistory() {
        try {
            const res = await fetch('/api/commander/history');
            const data = await res.json();
            
            if (data.length === 0) {
                commanderTimeline.innerHTML = '<div style="color: var(--text-secondary);">No commands dispatched yet.</div>';
                return;
            }
            
            commanderTimeline.innerHTML = data.reverse().map(entry => `
                <div class="timeline-item">
                    <div class="timeline-header">
                        <span class="timeline-target">Target: ${entry.target}</span>
                        <span>${new Date(entry.timestamp).toLocaleString()}</span>
                    </div>
                    <div class="timeline-content">${entry.instruction}</div>
                    <div style="margin-top: 0.5rem; font-size: 0.8rem; color: ${entry.status === 'success' ? 'var(--claude-color)' : 'var(--ato-color)'}">
                        Status: ${entry.status}
                    </div>
                </div>
            `).join('');
        } catch (error) {
            console.error('Error fetching commander history:', error);
        }
    }

    // Dispatch Command
    commanderDispatchBtn.addEventListener('click', async () => {
        const target = commanderTarget.value;
        const instruction = commanderInstruction.value.trim();
        
        if (!instruction) return;
        
        commanderDispatchBtn.disabled = true;
        commanderDispatchBtn.innerHTML = 'Dispatching...';
        
        try {
            const res = await fetch('/api/commander/dispatch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target, instruction })
            });
            const data = await res.json();
            
            if (data.status === 'success') {
                commanderInstruction.value = '';
                fetchCommanderHistory();
            } else {
                alert('Dispatch failed: ' + data.message);
            }
        } catch (error) {
            alert('Error: ' + error.message);
        } finally {
            commanderDispatchBtn.disabled = false;
            commanderDispatchBtn.innerHTML = `
                Dispatch Command
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
            `;
        }
    });

    // Fetch and render stats
    async function fetchStats() {
        try {
            const res = await fetch('/api/stats');
            const data = await res.json();
            
            const formatDate = (dateString) => {
                if (dateString === "None") return "No Activity";
                const date = new Date(dateString);
                return date.toLocaleString();
            };

            statsContainer.innerHTML = `
                <div class="stat-card glass-panel">
                    <div class="stat-label">atoTerminal Sessions</div>
                    <div class="stat-value" style="color: var(--ato-color)">${data.ato_sessions}</div>
                </div>
                <div class="stat-card glass-panel">
                    <div class="stat-label">Claude Code Sessions</div>
                    <div class="stat-value" style="color: var(--claude-color)">${data.claude_sessions}</div>
                </div>
                <div class="stat-card glass-panel">
                    <div class="stat-label">Antigravity (AGY) Sessions</div>
                    <div class="stat-value" style="color: #f59e0b">${data.agy_sessions || 0}</div>
                </div>
                <div class="stat-card glass-panel">
                    <div class="stat-label">Total Projects</div>
                    <div class="stat-value">${data.total_projects}</div>
                </div>
            `;
        } catch (error) {
            console.error("Error fetching stats:", error);
        }
    }

    const toggleArchivedBtn = document.getElementById('toggle-archived-btn');
    let showArchived = false;

    toggleArchivedBtn.addEventListener('click', () => {
        showArchived = !showArchived;
        if (showArchived) {
            toggleArchivedBtn.style.borderColor = 'var(--ato-color)';
            toggleArchivedBtn.style.color = 'var(--ato-color)';
            toggleArchivedBtn.innerText = '📦 Hide Archived';
        } else {
            toggleArchivedBtn.style.borderColor = 'var(--glass-border)';
            toggleArchivedBtn.style.color = 'var(--text-primary)';
            toggleArchivedBtn.innerText = '📦 Show Archived';
        }
        fetchSessions(false);
    });

    // Fetch and render sessions
    async function fetchSessions(isSilent = false) {
        if (!isSilent) {
            sessionsContainer.innerHTML = '<div class="loading">Loading sessions...</div>';
        }
        try {
            const query = new URLSearchParams();
            if (searchInput.value) query.append('search', searchInput.value);
            if (typeFilter.value) query.append('type', typeFilter.value);
            if (showArchived) query.append('include_archived', 'true');
            
            const res = await fetch(`/api/sessions?${query.toString()}`);
            const data = await res.json();

            if (data.length === 0) {
                sessionsContainer.innerHTML = '<div class="glass-panel" style="padding: 2rem; text-align: center;">No sessions found.</div>';
                return;
            }

            const fragment = document.createDocumentFragment();
            const statusFilterEl = document.getElementById('status-filter');
            const statusFilter = statusFilterEl ? statusFilterEl.value : '';

            data.forEach(session => {
                if (statusFilter === 'needs_review' && !session.needs_review) return;
                if (statusFilter === 'recent' && !session.is_recent) return;

                const card = document.createElement('div');
                card.className = `session-card glass-panel ${session.is_archived ? 'archived-card' : ''}`;
                
                const date = new Date(session.updated_at).toLocaleString();
                const displayTitle = session.title || session.project || 'Global';
                
                card.innerHTML = `
                    <div class="session-header">
                        <div class="session-title-area">
                            <div class="session-title-row">
                                <span class="badge badge-${session.type}">${session.type}</span>
                                ${session.needs_review ? '<span class="badge badge-review">🔔 Needs Review</span>' : ''}
                                ${session.is_recent ? '<span class="badge badge-recent">⚡ Updated</span>' : ''}
                                <span class="session-title">${displayTitle}</span>
                            </div>
                            ${session.project && session.project !== displayTitle ? `<span style="font-size: 0.8rem; color: var(--text-secondary);">(${session.project})</span>` : ''}
                        </div>
                        <div class="session-actions">
                            <span class="session-meta">${date}</span>
                            <button class="resume-btn glass-btn" style="padding: 0.2rem 0.6rem; font-size: 0.8rem; color: #38bdf8; border-color: rgba(56, 189, 248, 0.4);" title="Resume in cmux / Terminal">
                                ▶️ Resume
                            </button>
                            <button class="rename-btn glass-btn" style="padding: 0.2rem 0.6rem; font-size: 0.8rem;" title="Rename Session">
                                ✏️ Rename
                            </button>
                            <button class="archive-btn glass-btn" style="padding: 0.2rem 0.6rem; font-size: 0.8rem;" title="${session.is_archived ? 'Unarchive' : 'Archive'}">
                                ${session.is_archived ? '📂 Unarchive' : '📦 Archive'}
                            </button>
                            <button class="delete-btn glass-btn" style="padding: 0.2rem 0.6rem; font-size: 0.8rem; color: #ef4444; border-color: rgba(239, 68, 68, 0.4);" title="Delete Session">
                                🗑️ Delete
                            </button>
                        </div>
                    </div>
                    <div class="session-meta" style="margin-top: 0.75rem;">
                        <span>Model: ${session.model || 'Unknown'}</span>
                        <span>Messages: ${session.message_count}</span>
                    </div>
                    <div class="session-preview" style="margin-top: 0.75rem;">
                        ${session.last_message || 'No messages'}
                    </div>
                `;
                
                // Handle Resume button
                const resumeBtn = card.querySelector('.resume-btn');
                resumeBtn.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    const tClick = Date.now();
                    const clickStr = new Date(tClick).toLocaleTimeString() + '.' + String(tClick % 1000).padStart(3, '0');
                    console.log(`⏱️ [UI-PERF-LOG] [${clickStr}] Button clicked for ${session.type}:${session.id}`);
                    
                    resumeBtn.disabled = true;
                    resumeBtn.innerText = '🚀 Launching...';
                    try {
                        const res = await fetch('/api/sessions/resume', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                session_type: session.type,
                                session_id: session.id,
                                project: session.project_dir || session.project,
                                title: displayTitle
                            })
                        });
                        const tRes = Date.now();
                        const resStr = new Date(tRes).toLocaleTimeString() + '.' + String(tRes % 1000).padStart(3, '0');
                        const resData = await res.json();
                        
                        console.log(`⏱️ [UI-PERF-LOG] [${resStr}] HTTP response received in ${tRes - tClick}ms`, resData);

                        if (resData.status === 'success') {
                            resumeBtn.innerText = '✅ Launched!';
                            setTimeout(() => {
                                resumeBtn.disabled = false;
                                resumeBtn.innerText = '▶️ Resume';
                            }, 2000);
                        } else {
                            alert('Resume failed: ' + resData.message);
                            resumeBtn.disabled = false;
                            resumeBtn.innerText = '▶️ Resume';
                        }
                    } catch (err) {
                        alert('Error: ' + err.message);
                        resumeBtn.disabled = false;
                        resumeBtn.innerText = '▶️ Resume';
                    }
                });

                // Handle Rename button
                const renameBtn = card.querySelector('.rename-btn');
                renameBtn.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    const newTitle = prompt('セッションの名前（タイトル）を変更:', displayTitle);
                    if (newTitle !== null && newTitle.trim() !== '') {
                        try {
                            await fetch('/api/sessions/rename', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ session_id: session.id, title: newTitle.trim() })
                            });
                            fetchSessions(true);
                        } catch (err) {
                            console.error('Failed to rename session:', err);
                        }
                    }
                });

                // Handle Archive button click without opening modal
                const archiveBtn = card.querySelector('.archive-btn');
                archiveBtn.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    try {
                        await fetch('/api/sessions/archive', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ session_id: session.id })
                        });
                        fetchSessions(true);
                    } catch (err) {
                        console.error('Failed to archive session:', err);
                    }
                });

                // Handle Delete button click
                const deleteBtn = card.querySelector('.delete-btn');
                deleteBtn.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    const confirmed = confirm(`セッション「${displayTitle}」を削除してもよろしいですか？\n※この操作は取り消せません。`);
                    if (confirmed) {
                        try {
                            const res = await fetch('/api/sessions/delete', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ session_type: session.type, session_id: session.id })
                            });
                            const resData = await res.json();
                            if (resData.status === 'success') {
                                fetchStats();
                                fetchSessions(true);
                            } else {
                                alert('削除に失敗しました: ' + resData.message);
                            }
                        } catch (err) {
                            alert('エラーが発生しました: ' + err.message);
                        }
                    }
                });

                card.addEventListener('click', () => openSessionDetail(session.type, session.id));
                fragment.appendChild(card);
            });

            sessionsContainer.innerHTML = '';
            if (fragment.children.length === 0) {
                sessionsContainer.innerHTML = '<div class="glass-panel" style="padding: 2rem; text-align: center; color: var(--text-secondary);">条件に一致するセッションがありません。</div>';
            } else {
                sessionsContainer.appendChild(fragment);
            }

            // Update Commander Target Dropdown
            if (commanderTarget) {
                commanderTarget.innerHTML = `
                    <option value="all">All Sessions</option>
                    <option value="ato">All atoTerminal</option>
                    <option value="claude">All Claude Code</option>
                    <option value="agy">All Antigravity (AGY)</option>
                ` + data.map(session => `
                    <option value="${session.id}">${session.type}: ${session.project || 'Global'} (${session.id.substring(0,8)}...)</option>
                `).join('');
            }
        } catch (error) {
            console.error("Failed to fetch/render sessions:", error);
            sessionsContainer.innerHTML = `<div class="glass-panel" style="padding: 2rem; color: #ef4444; text-align: center;">セッションの読み込み中にエラーが発生しました: ${error.message}</div>`;
        }
    }

    // Open session modal
    async function openSessionDetail(type, id) {
        modal.classList.add('active');
        modalBody.innerHTML = '<div class="loading">Loading details...</div>';
        
        try {
            const res = await fetch(`/api/sessions/${type}/${id}`);
            const data = await res.json();
            
            if (data.error) {
                modalBody.innerHTML = `<div>Error: ${data.error}</div>`;
                return;
            }

            let html = '';
            const messages = data.messages || [];
            
            if (messages.length === 0) {
                html = '<div>No messages in this session.</div>';
            } else {
                messages.forEach(msg => {
                    const role = msg.role || (msg.type === 'USER_INPUT' ? 'user' : 'assistant');
                    const content = msg.content || '';
                    
                    // Safe parsing for text content
                    let textContent = content;
                    if (Array.isArray(content)) {
                        textContent = content.map(c => c.text || JSON.stringify(c)).join('\n');
                    } else if (typeof content === 'object') {
                        textContent = JSON.stringify(content, null, 2);
                    }
                    
                    const parsedContent = marked.parse(textContent);

                    html += `
                        <div class="chat-message ${role}">
                            <div class="chat-role">${role}</div>
                            <div class="chat-content">${parsedContent}</div>
                        </div>
                    `;
                });
            }
            
            modalBody.innerHTML = html;
        } catch (error) {
            modalBody.innerHTML = `<div>Error loading details: ${error.message}</div>`;
        }
    }

    // Event listeners
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            fetchStats();
            fetchSessions(false);
        });
    }

    if (searchInput) {
        searchInput.addEventListener('input', () => fetchSessions(true));
    }
    
    if (typeFilter) {
        typeFilter.addEventListener('change', () => fetchSessions(true));
    }
    
    const statusFilter = document.getElementById('status-filter');
    if (statusFilter) {
        statusFilter.addEventListener('change', () => fetchSessions(true));
    }
    
    const projectFilter = document.getElementById('project-filter');
    if (projectFilter) {
        projectFilter.addEventListener('change', () => fetchSessions(true));
    }

    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', () => {
            if (modal) modal.classList.remove('active');
        });
    }

    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.remove('active');
            }
        });
    }

    // Initial load safely
    fetchStats();
    fetchSessions(false);
    if (commanderPanel && commanderPanel.style && commanderPanel.style.display !== 'none') {
        fetchCommanderHistory();
    }
    
    // Auto refresh quietly every 30 seconds
    setInterval(() => {
        fetchStats();
        fetchSessions(true);
        if (commanderPanel && commanderPanel.style && commanderPanel.style.display !== 'none') {
            fetchCommanderHistory();
        }
    }, 30000);
});

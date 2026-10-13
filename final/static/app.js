// SOAR Sentinel — Interactive SOC Platform & AI Copilot Controller

function showToast(message, type = 'info') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
    </svg>
    <span>${message}</span>
  `;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// AI Copilot Chat Dispatcher
async function sendCopilotMessage(msgText, messagesContainer) {
  if (!msgText.trim()) return;

  // Append user bubble
  const userMsgEl = document.createElement('div');
  userMsgEl.className = 'chat-msg user';
  userMsgEl.innerHTML = `
    <div class="chat-avatar user">YOU</div>
    <div class="chat-bubble user"><p>${escapeHtml(msgText)}</p></div>
  `;
  messagesContainer.appendChild(userMsgEl);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;

  // Temporary bot typing indicator
  const typingEl = document.createElement('div');
  typingEl.className = 'chat-msg bot';
  typingEl.innerHTML = `
    <div class="chat-avatar bot">AI</div>
    <div class="chat-bubble bot"><span style="color:var(--cyan); font-family:var(--font-mono);">● ● ● Neural analysis in progress...</span></div>
  `;
  messagesContainer.appendChild(typingEl);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;

  try {
    const res = await fetch('/api/copilot/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: msgText })
    });
    const data = await res.json();
    typingEl.remove();

    // Render formatted bot response
    const botMsgEl = document.createElement('div');
    botMsgEl.className = 'chat-msg bot';
    
    let actionBtnHtml = '';
    if (data.suggested_action) {
      actionBtnHtml = `<div style="margin-top:10px;"><a href="${data.suggested_action.url}" class="btn primary sm">${data.suggested_action.label} &rarr;</a></div>`;
    }

    botMsgEl.innerHTML = `
      <div class="chat-avatar bot">AI</div>
      <div class="chat-bubble bot">
        <div>${formatMarkdown(data.reply)}</div>
        ${actionBtnHtml}
      </div>
    `;
    messagesContainer.appendChild(botMsgEl);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  } catch (err) {
    typingEl.remove();
    showToast('Copilot neural link timeout.', 'error');
  }
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.innerText = text;
  return div.innerHTML;
}

function formatMarkdown(text) {
  return text
    .replace(/\*\*(.*?)\*\*/g, '<b>$1</b>')
    .replace(/\*(.*?)\*/g, '<i>$1</i>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>');
}

document.addEventListener('DOMContentLoaded', () => {
  // Modal handlers
  document.querySelectorAll('[data-modal-open]').forEach(btn => {
    btn.addEventListener('click', () => {
      const modalId = btn.getAttribute('data-modal-open');
      const target = document.getElementById(modalId);
      if (target) target.classList.add('active');
    });
  });

  document.querySelectorAll('[data-modal-close]').forEach(btn => {
    btn.addEventListener('click', () => {
      const modal = btn.closest('.modal-overlay');
      if (modal) modal.classList.remove('active');
    });
  });

  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) overlay.classList.remove('active');
    });
  });

  // Slide-out AI Copilot Drawer Controllers
  const drawer = document.getElementById('copilotDrawer');
  const openCopilotBtn = document.getElementById('openCopilotBtn');
  const topbarCopilotBtn = document.getElementById('topbarCopilotBtn');
  const closeCopilotDrawer = document.getElementById('closeCopilotDrawer');
  const drawerChatForm = document.getElementById('drawerChatForm');
  const drawerChatInput = document.getElementById('drawerChatInput');
  const drawerChatMessages = document.getElementById('drawerChatMessages');

  if (openCopilotBtn && drawer) {
    openCopilotBtn.addEventListener('click', () => drawer.classList.toggle('active'));
  }
  if (topbarCopilotBtn && drawer) {
    topbarCopilotBtn.addEventListener('click', () => drawer.classList.add('active'));
  }
  if (closeCopilotDrawer && drawer) {
    closeCopilotDrawer.addEventListener('click', () => drawer.classList.remove('active'));
  }

  if (drawerChatForm && drawerChatInput && drawerChatMessages) {
    drawerChatForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const text = drawerChatInput.value;
      drawerChatInput.value = '';
      sendCopilotMessage(text, drawerChatMessages);
    });
  }

  // Full Copilot Page Chat Form
  const copilotChatForm = document.getElementById('copilotChatForm');
  const copilotInput = document.getElementById('copilotInput');
  const copilotChatMessages = document.getElementById('copilotChatMessages');

  if (copilotChatForm && copilotInput && copilotChatMessages) {
    copilotChatForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const text = copilotInput.value;
      copilotInput.value = '';
      sendCopilotMessage(text, copilotChatMessages);
    });
  }

  // Quick Action Prompt Chips
  document.querySelectorAll('[data-copilot-prompt]').forEach(chip => {
    chip.addEventListener('click', () => {
      const prompt = chip.getAttribute('data-copilot-prompt');
      if (copilotChatMessages) {
        sendCopilotMessage(prompt, copilotChatMessages);
      } else if (drawerChatMessages && drawer) {
        drawer.classList.add('active');
        sendCopilotMessage(prompt, drawerChatMessages);
      }
    });
  });

  // Client-side quick search for tables
  const incidentSearch = document.getElementById('incidentSearch');
  if (incidentSearch) {
    incidentSearch.addEventListener('input', () => {
      const q = incidentSearch.value.toLowerCase();
      document.querySelectorAll('#incidentTable tbody tr').forEach(row => {
        row.style.display = row.innerText.toLowerCase().includes(q) ? '' : 'none';
      });
    });
  }

  // Integration Diagnostic Ping Handler
  document.querySelectorAll('[data-test-integration]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const connId = btn.getAttribute('data-test-integration');
      const origText = btn.innerHTML;
      btn.innerHTML = `<span class="spin">⚡</span> Querying API...`;
      btn.disabled = true;

      try {
        const res = await fetch(`/integrations/${connId}/test`, { method: 'POST' });
        const data = await res.json();
        if (data.status === 'success') {
          showToast(data.message, 'success');
        } else {
          showToast(`Test failed: ${data.message || 'Unknown error'}`, 'error');
        }
      } catch (err) {
        showToast(`Diagnostic ping to ${connId} failed: Connection timeout`, 'error');
      } finally {
        btn.innerHTML = origText;
        btn.disabled = false;
      }
    });
  });

  // Action Confirmation Prompt
  document.querySelectorAll('[data-confirm]').forEach(el => {
    el.addEventListener('click', (e) => {
      const msg = el.getAttribute('data-confirm');
      if (!confirm(msg)) {
        e.preventDefault();
      }
    });
  });

  // Initialize Chart.js Charts if on Dashboard
  initCharts();
});

function initCharts() {
  if (typeof Chart === 'undefined') return;

  const velCanvas = document.getElementById('velocityChart');
  const donutCanvas = document.getElementById('severityDonutChart');
  const chartData = window.SOAR_CHART_DATA || null;

  if (velCanvas && chartData) {
    const ctx = velCanvas.getContext('2d');
    const gradCyan = ctx.createLinearGradient(0, 0, 0, 200);
    gradCyan.addColorStop(0, 'rgba(6, 182, 212, 0.4)');
    gradCyan.addColorStop(1, 'rgba(6, 182, 212, 0.0)');

    const gradPurple = ctx.createLinearGradient(0, 0, 0, 200);
    gradPurple.addColorStop(0, 'rgba(139, 92, 246, 0.35)');
    gradPurple.addColorStop(1, 'rgba(139, 92, 246, 0.0)');

    new Chart(velCanvas, {
      type: 'line',
      data: {
        labels: chartData.timeline_labels,
        datasets: [
          {
            label: 'Alert Volume',
            data: chartData.timeline_series,
            borderColor: '#06b6d4',
            backgroundColor: gradCyan,
            fill: true,
            tension: 0.4,
            borderWidth: 2,
            pointRadius: 3,
            pointBackgroundColor: '#06b6d4'
          },
          {
            label: 'Automated Containments',
            data: chartData.response_series,
            borderColor: '#8b5cf6',
            backgroundColor: gradPurple,
            fill: true,
            tension: 0.4,
            borderWidth: 2,
            pointRadius: 3,
            pointBackgroundColor: '#8b5cf6'
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            labels: { color: '#94a3b8', font: { family: 'Inter', size: 11 } }
          }
        },
        scales: {
          x: {
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            ticks: { color: '#64748b', font: { family: 'JetBrains Mono', size: 10 } }
          },
          y: {
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            ticks: { color: '#64748b', font: { family: 'JetBrains Mono', size: 10 } }
          }
        }
      }
    });
  }

  if (donutCanvas && chartData) {
    new Chart(donutCanvas, {
      type: 'doughnut',
      data: {
        labels: ['Critical', 'High', 'Medium', 'Low'],
        datasets: [
          {
            data: chartData.severity,
            backgroundColor: ['#ef4444', '#f97316', '#f59e0b', '#10b981'],
            borderColor: '#0f172a',
            borderWidth: 3,
            hoverOffset: 6
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '72%',
        plugins: {
          legend: { display: false }
        }
      }
    });
  }
}

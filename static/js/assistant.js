/**
 * Digital Library & Research Management System
 * Smart AI Library Assistant ("Libra") & Interactive Welcome Experience
 */

(function () {
  'use strict';

  // ============================================================================
  // Configuration & Constants
  // ============================================================================
  const STORAGE_KEY_CHAT = 'libra_chat_history_v2';
  const STORAGE_KEY_STATUS = 'libra_chat_state_v2';
  const DEFAULT_GREETING =
    "Hi! I'm Libra, your personal Library Assistant. I can help you navigate the library, find books, explore research papers, and manage your account. What would you like to do today?";

  // ============================================================================
  // Helpers
  // ============================================================================
  function getDynamicGreeting(name) {
    const hour = new Date().getHours();
    let timeGreet = 'Hello';
    if (hour >= 5 && hour < 12) {
      timeGreet = 'Good morning';
    } else if (hour >= 12 && hour < 17) {
      timeGreet = 'Good afternoon';
    } else if (hour >= 17 && hour < 22) {
      timeGreet = 'Good evening';
    }
    const cleanName = (name || '').trim();
    if (cleanName) {
      return `${timeGreet}, ${cleanName}! Ready to explore something new?`;
    }
    return `${timeGreet}! Welcome to Your Digital Library.`;
  }

  function formatTime(isoOrDate) {
    const d = isoOrDate ? new Date(isoOrDate) : new Date();
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  function parseSimpleMarkdown(text) {
    if (!text) return '';
    let parsed = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');

    // Bold text **word**
    parsed = parsed.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    // Italic text *word*
    parsed = parsed.replace(/\*(.*?)\*/g, '<em>$1</em>');
    // Inline code `code`
    parsed = parsed.replace(/`([^`]+)`/g, '<code class="bg-light px-1 rounded">$1</code>');

    // Newlines into line breaks
    const lines = parsed.split('\n');
    let html = '';
    let inList = false;

    lines.forEach((line) => {
      const trimmed = line.trim();
      if (trimmed.startsWith('- ') || trimmed.startsWith('• ')) {
        if (!inList) {
          html += '<ul class="ps-3 mb-2 small">';
          inList = true;
        }
        html += `<li>${trimmed.substring(2)}</li>`;
      } else if (/^\d+\.\s/.test(trimmed)) {
        if (!inList) {
          html += '<ol class="ps-3 mb-2 small">';
          inList = true;
        }
        html += `<li>${trimmed.replace(/^\d+\.\s/, '')}</li>`;
      } else {
        if (inList) {
          html += inList ? '</ul>' : '</ol>';
          inList = false;
        }
        if (trimmed.length > 0) {
          html += `<p class="mb-2">${trimmed}</p>`;
        }
      }
    });

    if (inList) {
      html += '</ul>';
    }

    return html;
  }

  // ============================================================================
  // Welcome Screen Management
  // ============================================================================
  function initWelcomeScreen() {
    const overlay = document.getElementById('welcome-overlay');
    if (!overlay) return;

    const userName = overlay.getAttribute('data-user-name') || '';
    const greetingEl = document.getElementById('welcome-dynamic-greeting');
    if (greetingEl) {
      greetingEl.textContent = getDynamicGreeting(userName);
    }

    let isDismissed = false;

    function dismissWelcome(openAssistant) {
      if (isDismissed) return;
      isDismissed = true;

      overlay.classList.add('docking');
      setTimeout(() => {
        overlay.classList.add('d-none');
      }, 600);

      // Tell backend to clear show_welcome from session
      fetch('/api/welcome/dismiss', { method: 'POST' }).catch(() => {});

      // Show proactive speech bubble on Libra launcher
      const bubble = document.getElementById('libra-speech-bubble');
      if (bubble) {
        bubble.classList.remove('d-none');
        setTimeout(() => {
          bubble.classList.add('d-none');
        }, 8000);
      }

      if (openAssistant) {
        setTimeout(() => {
          window.LibraAssistant && window.LibraAssistant.openChat();
        }, 500);
      }
    }

    // Auto-dismiss after 3.8 seconds
    const timer = setTimeout(() => {
      dismissWelcome(false);
    }, 3800);

    const btnDismiss = document.getElementById('btn-welcome-dismiss');
    if (btnDismiss) {
      btnDismiss.addEventListener('click', (e) => {
        e.preventDefault();
        clearTimeout(timer);
        dismissWelcome(false);
      });
    }

    const btnAskLibra = document.getElementById('btn-welcome-ask-libra');
    if (btnAskLibra) {
      btnAskLibra.addEventListener('click', (e) => {
        e.preventDefault();
        clearTimeout(timer);
        dismissWelcome(true);
      });
    }

    const btnSkip = document.getElementById('welcome-skip-btn');
    if (btnSkip) {
      btnSkip.addEventListener('click', (e) => {
        e.preventDefault();
        clearTimeout(timer);
        dismissWelcome(false);
      });
    }
  }

  // ============================================================================
  // Libra Smart Assistant Chatbot
  // ============================================================================
  class LibraChatbot {
    constructor() {
      this.windowEl = document.getElementById('libra-chat-window');
      this.launcherBtn = document.getElementById('libra-launcher-btn');
      this.speechBubble = document.getElementById('libra-speech-bubble');
      this.chatBody = document.getElementById('libra-chat-body');
      this.inputField = document.getElementById('libra-input-field');
      this.sendBtn = document.getElementById('libra-send-btn');
      this.suggestionsContainer = document.getElementById('libra-suggestions-container');
      this.closeBtn = document.getElementById('libra-close-btn');
      this.minimizeBtn = document.getElementById('libra-minimize-btn');
      this.clearBtn = document.getElementById('libra-clear-btn');

      if (!this.windowEl || !this.launcherBtn) {
        return;
      }

      this.messages = [];
      this.isTyping = false;

      this.init();
    }

    init() {
      this.bindEvents();
      this.loadHistory();
      this.loadSuggestions();

      // Check stored open/close state
      const savedState = sessionStorage.getItem(STORAGE_KEY_STATUS);
      if (savedState === 'open') {
        this.openChat(false);
      }
    }

    bindEvents() {
      this.launcherBtn.addEventListener('click', () => {
        this.toggleChat();
      });

      if (this.speechBubble) {
        this.speechBubble.addEventListener('click', (e) => {
          if (e.target.closest('.libra-bubble-close')) {
            this.speechBubble.classList.add('d-none');
            return;
          }
          this.openChat();
          this.speechBubble.classList.add('d-none');
        });
      }

      if (this.closeBtn) {
        this.closeBtn.addEventListener('click', () => this.closeChat());
      }

      if (this.minimizeBtn) {
        this.minimizeBtn.addEventListener('click', () => this.toggleMinimize());
      }

      if (this.clearBtn) {
        this.clearBtn.addEventListener('click', () => this.clearChat());
      }

      if (this.sendBtn && this.inputField) {
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        this.inputField.addEventListener('keydown', (e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            this.sendMessage();
          }
        });
      }
    }

    openChat(focusInput = true) {
      this.windowEl.classList.remove('closed');
      this.windowEl.classList.remove('minimized');
      sessionStorage.setItem(STORAGE_KEY_STATUS, 'open');
      if (this.speechBubble) {
        this.speechBubble.classList.add('d-none');
      }
      this.scrollToBottom();
      if (focusInput && this.inputField) {
        setTimeout(() => this.inputField.focus(), 200);
      }
    }

    closeChat() {
      this.windowEl.classList.add('closed');
      sessionStorage.setItem(STORAGE_KEY_STATUS, 'closed');
    }

    toggleChat() {
      if (this.windowEl.classList.contains('closed')) {
        this.openChat();
      } else {
        this.closeChat();
      }
    }

    toggleMinimize() {
      this.windowEl.classList.toggle('minimized');
    }

    clearChat() {
      if (confirm('Clear chat history with Libra?')) {
        this.messages = [];
        sessionStorage.removeItem(STORAGE_KEY_CHAT);
        this.chatBody.innerHTML = '';
        this.addInitialGreeting();
      }
    }

    loadHistory() {
      try {
        const raw = sessionStorage.getItem(STORAGE_KEY_CHAT);
        if (raw) {
          this.messages = JSON.parse(raw) || [];
        }
      } catch (e) {
        this.messages = [];
      }

      if (this.messages.length === 0) {
        this.addInitialGreeting();
      } else {
        this.messages.forEach((m) => this.renderMessage(m));
        this.scrollToBottom();
      }
    }

    saveHistory() {
      try {
        // Keep last 30 messages in session
        const trimmed = this.messages.slice(-30);
        sessionStorage.setItem(STORAGE_KEY_CHAT, JSON.stringify(trimmed));
      } catch (e) {}
    }

    addInitialGreeting() {
      const greetingMsg = {
        sender: 'assistant',
        text: DEFAULT_GREETING,
        actions: [
          { label: 'Browse Catalog', url: '/books', icon: 'bi-book' },
          { label: 'Research Papers', url: '/research', icon: 'bi-file-earmark-text' }
        ],
        timestamp: new Date().toISOString()
      };
      this.messages.push(greetingMsg);
      this.renderMessage(greetingMsg);
      this.saveHistory();
    }

    renderMessage(msg) {
      const isUser = msg.sender === 'user';
      const row = document.createElement('div');
      row.className = `libra-msg-row ${isUser ? 'user' : 'assistant'}`;

      const avatar = document.createElement('div');
      avatar.className = 'libra-msg-avatar';
      avatar.innerHTML = isUser
        ? '<i class="bi bi-person-fill"></i>'
        : '<i class="bi bi-stars"></i>';

      const bubbleContainer = document.createElement('div');
      bubbleContainer.style.maxWidth = '100%';

      const bubble = document.createElement('div');
      bubble.className = 'libra-msg-bubble';

      if (isUser) {
        bubble.textContent = msg.text;
      } else {
        bubble.innerHTML = parseSimpleMarkdown(msg.text);

        // Render Action Buttons if available
        if (msg.actions && msg.actions.length > 0) {
          const actionsWrap = document.createElement('div');
          actionsWrap.className = 'libra-actions-list';

          msg.actions.forEach((act) => {
            const btn = document.createElement('a');
            btn.className = 'libra-action-pill';
            btn.href = act.url;
            btn.innerHTML = `<i class="bi ${act.icon || 'bi-arrow-right-short'}"></i> ${act.label}`;
            actionsWrap.appendChild(btn);
          });

          bubble.appendChild(actionsWrap);
        }
      }

      const timeEl = document.createElement('div');
      timeEl.className = 'libra-msg-time';
      timeEl.textContent = formatTime(msg.timestamp);

      bubbleContainer.appendChild(bubble);
      bubbleContainer.appendChild(timeEl);

      row.appendChild(avatar);
      row.appendChild(bubbleContainer);

      this.chatBody.appendChild(row);
    }

    showTypingIndicator() {
      if (this.isTyping) return;
      this.isTyping = true;

      const row = document.createElement('div');
      row.className = 'libra-msg-row assistant typing-row';
      row.id = 'libra-typing-indicator-row';

      const avatar = document.createElement('div');
      avatar.className = 'libra-msg-avatar';
      avatar.innerHTML = '<i class="bi bi-stars"></i>';

      const bubble = document.createElement('div');
      bubble.className = 'libra-msg-bubble libra-typing-indicator';
      bubble.innerHTML = `
        <div class="libra-typing-dot"></div>
        <div class="libra-typing-dot"></div>
        <div class="libra-typing-dot"></div>
      `;

      row.appendChild(avatar);
      row.appendChild(bubble);
      this.chatBody.appendChild(row);
      this.scrollToBottom();
    }

    hideTypingIndicator() {
      this.isTyping = false;
      const el = document.getElementById('libra-typing-indicator-row');
      if (el) {
        el.remove();
      }
    }

    scrollToBottom() {
      setTimeout(() => {
        this.chatBody.scrollTop = this.chatBody.scrollHeight;
      }, 50);
    }

    loadSuggestions() {
      if (!this.suggestionsContainer) return;
      fetch('/api/assistant/suggestions')
        .then((res) => res.json())
        .then((data) => {
          if (data && data.suggestions && data.suggestions.length > 0) {
            this.suggestionsContainer.innerHTML = '';
            data.suggestions.forEach((text) => {
              const chip = document.createElement('button');
              chip.className = 'libra-suggest-chip';
              chip.type = 'button';
              chip.textContent = text;
              chip.addEventListener('click', () => {
                this.inputField.value = text;
                this.sendMessage();
              });
              this.suggestionsContainer.appendChild(chip);
            });
          }
        })
        .catch(() => {});
    }

    sendMessage() {
      const text = (this.inputField.value || '').trim();
      if (!text || this.isTyping) return;

      this.inputField.value = '';
      this.sendBtn.disabled = true;

      const userMsg = {
        sender: 'user',
        text: text,
        timestamp: new Date().toISOString()
      };
      this.messages.push(userMsg);
      this.renderMessage(userMsg);
      this.saveHistory();
      this.scrollToBottom();

      this.showTypingIndicator();

      fetch('/api/assistant/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
      })
        .then((res) => res.json())
        .then((data) => {
          setTimeout(() => {
            this.hideTypingIndicator();
            this.sendBtn.disabled = false;

            const replyMsg = {
              sender: 'assistant',
              text: data.reply || "I'm sorry, I couldn't process your request.",
              actions: data.actions || [],
              timestamp: new Date().toISOString()
            };
            this.messages.push(replyMsg);
            this.renderMessage(replyMsg);
            this.saveHistory();
            this.scrollToBottom();
          }, 350); // slight realistic typing feel
        })
        .catch((err) => {
          setTimeout(() => {
            this.hideTypingIndicator();
            this.sendBtn.disabled = false;

            const errorMsg = {
              sender: 'assistant',
              text: "I'm having trouble connecting right now. Please try again or visit the catalog directly.",
              actions: [{ label: 'Book Catalog', url: '/books', icon: 'bi-book' }],
              timestamp: new Date().toISOString()
            };
            this.messages.push(errorMsg);
            this.renderMessage(errorMsg);
            this.saveHistory();
            this.scrollToBottom();
          }, 300);
        });
    }
  }

  // ============================================================================
  // Initialization on DOMContentLoaded
  // ============================================================================
  document.addEventListener('DOMContentLoaded', () => {
    initWelcomeScreen();
    window.LibraAssistant = new LibraChatbot();
  });
})();

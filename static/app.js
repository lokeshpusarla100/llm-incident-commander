// LLM Incident Commander - Frontend JavaScript

// DOM Elements
const chatMessages = document.getElementById('chatMessages');
const questionInput = document.getElementById('questionInput');
const submitBtn = document.getElementById('submitBtn');
const chatForm = document.getElementById('chatForm');

// Add message to chat
function addMessage(type, content, meta = null) {
    // Remove welcome message if exists
    const welcome = chatMessages.querySelector('.welcome-message');
    if (welcome) welcome.remove();

    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;

    const avatar = type === 'user' ? '👤' : '🤖';

    let metaHtml = '';
    if (meta) {
        metaHtml = `
            <div class="message-meta">
                <span>⏱️ ${meta.latency_ms}ms</span>
                <span>🎯 ${meta.tokens.total} tokens</span>
            </div>
        `;
    }

    messageDiv.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
            ${content}
            ${metaHtml}
        </div>
    `;

    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Handle form submit
async function handleSubmit(e) {
    e.preventDefault();

    const question = questionInput.value.trim();
    if (!question) return;

    // Disable input
    submitBtn.classList.add('loading');
    submitBtn.disabled = true;
    questionInput.disabled = true;

    // Add user message
    addMessage('user', question);
    questionInput.value = '';

    try {
        const response = await fetch('/ask', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ question })
        });

        const data = await response.json();

        if (response.ok) {
            // Add assistant message
            addMessage('assistant', data.answer, {
                latency_ms: data.latency_ms,
                tokens: data.tokens
            });
        } else {
            // Handle error response
            const errorMsg = data.message || data.error || 'An error occurred';
            addMessage('assistant', `⚠️ Error: ${errorMsg}`);
        }
    } catch (error) {
        console.error('Error:', error);
        addMessage('assistant', `⚠️ Connection error: ${error.message}`);
    } finally {
        // Re-enable input
        submitBtn.classList.remove('loading');
        submitBtn.disabled = false;
        questionInput.disabled = false;
        questionInput.focus();
    }
}

// Use example query
function useExample(button) {
    questionInput.value = button.textContent;
    questionInput.focus();
}

// Check API health on load
async function checkHealth() {
    try {
        const response = await fetch('/health');
        const data = await response.json();

        if (data.status === 'healthy') {
            console.log('✅ API is healthy', data);
        } else {
            console.warn('⚠️ API degraded:', data);
        }
    } catch (error) {
        console.error('❌ API health check failed:', error);
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    checkHealth();

    // Auto-focus input
    questionInput.focus();

    // Handle Enter key
    questionInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            chatForm.dispatchEvent(new Event('submit'));
        }
    });
});

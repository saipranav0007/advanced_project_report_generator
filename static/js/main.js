// frontend/static/js/main.js

document.addEventListener('DOMContentLoaded', () => {
    
    // --- 1. REPORT BUILDER: AI HELPER MODAL LOGIC ---
    const aiModalElement = document.getElementById('aiHelperModal');
    if (aiModalElement) {
        let currentTargetInput = null;

        // Listen for clicks on any "AI Help" button next to form inputs
        document.querySelectorAll('.ai-help-btn').forEach(button => {
            button.addEventListener('click', (e) => {
                const targetId = e.currentTarget.getAttribute('data-target');
                currentTargetInput = document.getElementById(targetId);
                
                // Set modal title based on which field was clicked
                const modalTitle = document.getElementById('aiHelperModalLabel');
                if (modalTitle && currentTargetInput) {
                    modalTitle.innerText = `AI Assistant: Drafting ${currentTargetInput.name || 'Content'}`;
                }
            });
        });

        // Handle the "Insert Text" button inside the Modal
        const insertBtn = document.getElementById('insertAiTextBtn');
        if (insertBtn) {
            insertBtn.addEventListener('click', () => {
                const aiOutput = document.getElementById('aiModalOutput');
                if (currentTargetInput && aiOutput && aiOutput.value.trim() !== '') {
                    // Append or replace content in the target input
                    if (currentTargetInput.value.trim() === '') {
                        currentTargetInput.value = aiOutput.value.trim();
                    } else {
                        currentTargetInput.value += "\n\n" + aiOutput.value.trim();
                    }
                    aiOutput.value = ''; // Reset modal textarea
                    
                    // Close modal using Bootstrap API if available
                    if (typeof bootstrap !== 'undefined') {
                        const modalInstance = bootstrap.Modal.getInstance(aiModalElement);
                        if (modalInstance) modalInstance.hide();
                    }
                }
            });
        }
    }

    // --- 2. STANDALONE AI ASSISTANT PAGE LOGIC ---
    const chatBox = document.getElementById('chatBox');
    const chatInput = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendBtn');
    const modeSelect = document.getElementById('aiModeSelect');

    if (chatBox && chatInput && sendBtn) {
        
        // Helper: Scroll chat window to the bottom
        const scrollToBottom = () => {
            chatBox.scrollTop = chatBox.scrollHeight;
        };

        // Helper: Append a message bubble to the chat
        const appendMessage = (sender, text) => {
            const msgDiv = document.createElement('div');
            msgDiv.classList.add('chat-message', sender === 'user' ? 'user-msg' : 'ai-msg');
            
            const bubble = document.createElement('div');
            bubble.classList.add('msg-bubble');
            bubble.innerText = text;
            
            msgDiv.appendChild(bubble);
            chatBox.appendChild(msgDiv);
            scrollToBottom();
            return bubble;
        };

        // Helper: Add a temporary typing indicator
        const showTypingIndicator = () => {
            const msgDiv = document.createElement('div');
            msgDiv.classList.add('chat-message', 'ai-msg', 'typing-indicator-msg');
            msgDiv.innerHTML = `
                <div class="msg-bubble text-muted small">
                    <span class="spinner-grow spinner-grow-sm me-1" role="status"></span>
                    AI is thinking...
                </div>
            `;
            chatBox.appendChild(msgDiv);
            scrollToBottom();
            return msgDiv;
        };

        // Send message to backend
        const sendMessage = async () => {
            const text = chatInput.value.trim();
            if (!text) return;

            // 1. Display user message and clear input
            appendMessage('user', text);
            chatInput.value = '';
            
            // 2. Show typing indicator
            const indicator = showTypingIndicator();

            // 3. Get current selected AI mode (e.g., 'general', 'academic', 'grammar')
            const mode = modeSelect ? modeSelect.value : 'general';

            try {
                const response = await fetch('/api/ai-chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text, mode: mode })
                });

                const data = await response.json();
                
                // Remove indicator
                indicator.remove();

                if (response.ok && data.reply) {
                    appendMessage('ai', data.reply);
                } else {
                    appendMessage('ai', data.error || 'Sorry, I encountered an issue processing your request.');
                }
            } catch (error) {
                indicator.remove();
                appendMessage('ai', 'Network error: Unable to connect to the AI Assistant.');
                console.error('AI Chat Error:', error);
            }
        };

        // Event Listeners for Chat
        sendBtn.addEventListener('click', sendMessage);

        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        // Quick Prompt Pill Buttons
        document.querySelectorAll('.quick-prompt-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const promptText = e.currentTarget.getAttribute('data-prompt') || e.currentTarget.innerText;
                chatInput.value = promptText;
                sendMessage();
            });
        });
    }
});
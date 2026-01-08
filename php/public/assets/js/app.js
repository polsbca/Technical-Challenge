class ChatApp {
    constructor() {
        this.messagesContainer = document.getElementById('messages');
        this.messageInput = document.getElementById('message-input');
        this.sendButton = document.getElementById('send-button');
        this.companySelect = document.getElementById('company-select');
        this.loadingIndicator = document.getElementById('loading-indicator');
        this.conversationHistory = [];
        
        this.initializeEventListeners();
        this.loadCompanies();
    }
    
    initializeEventListeners() {
        // Send message on button click
        this.sendButton.addEventListener('click', () => this.handleSendMessage());
        
        // Send message on Enter key (but allow Shift+Enter for new lines)
        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.handleSendMessage();
            }
        });
        
        // Auto-resize textarea as user types
        this.messageInput.addEventListener('input', () => {
            this.adjustTextareaHeight();
        });
    }
    
    async loadCompanies() {
        try {
            const response = await fetch('/api/companies');
            const companies = await response.json();
            
            // Clear existing options except the first one
            this.companySelect.innerHTML = '<option value="">Select a company...</option>';
            
            // Add companies to select
            companies.forEach(company => {
                const option = document.createElement('option');
                option.value = company.id;
                option.textContent = company.name;
                this.companySelect.appendChild(option);
            });
        } catch (error) {
            console.error('Error loading companies:', error);
            this.showError('Failed to load companies. Please refresh the page.');
        }
    }
    
    async handleSendMessage() {
        const message = this.messageInput.value.trim();
        const companyId = this.companySelect.value;
        
        if (!message) return;
        if (!companyId) {
            this.showError('Please select a company first');
            return;
        }
        
        // Add user message to chat
        this.addMessage('user', message);
        this.messageInput.value = '';
        this.adjustTextareaHeight();
        
        // Show loading indicator
        this.setLoading(true);
        
        try {
            // Add to conversation history
            this.conversationHistory.push({ role: 'user', content: message });
            
            // Send to API
            const response = await this.sendToChatAPI(message, companyId);
            
            // Add assistant's response to chat
            this.addMessage('assistant', response.answer, response.sources, response.confidence);
            
            // Add to conversation history (keep last 5 messages to manage context size)
            this.conversationHistory.push({ role: 'assistant', content: response.answer });
            if (this.conversationHistory.length > 10) {
                this.conversationHistory = this.conversationHistory.slice(-10);
            }
            
        } catch (error) {
            console.error('Error:', error);
            this.showError('Failed to get response. Please try again.');
        } finally {
            this.setLoading(false);
        }
    }
    
    async sendToChatAPI(message, companyId) {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message,
                company_id: companyId,
                conversation_history: this.conversationHistory
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to get response');
        }
        
        return response.json();
    }
    
    addMessage(role, content, sources = [], confidence = null) {
        const messageElement = document.createElement('div');
        messageElement.className = `message ${role}`;
        
        // Format message content with line breaks
        const formattedContent = content.replace(/\n/g, '<br>');
        
        // Get current time
        const now = new Date();
        const timeString = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        
        // Add confidence indicator if available
        let confidenceBadge = '';
        if (confidence !== null && role === 'assistant') {
            const confidencePercent = Math.round(confidence * 100);
            let confidenceClass = 'high-confidence';
            
            if (confidence < 0.5) confidenceClass = 'low-confidence';
            else if (confidence < 0.8) confidenceClass = 'medium-confidence';
            
            confidenceBadge = `<span class="confidence-badge ${confidenceClass}" title="Confidence: ${confidencePercent}%">
                ${confidencePercent}% confident
            </span>`;
        }
        
        // Add sources if available
        let sourcesHtml = '';
        if (sources && sources.length > 0) {
            sourcesHtml = `
                <div class="sources">
                    <span>Sources:</span>
                    ${sources.map(source => 
                        `<a href="${source}" target="_blank" rel="noopener noreferrer">${new URL(source).hostname}</a>`
                    ).join(', ')}
                </div>`;
        }
        
        messageElement.innerHTML = `
            <div class="message-content">${formattedContent}</div>
            <div class="message-footer">
                <span class="timestamp">${timeString}</span>
                ${confidenceBadge}
            </div>
            ${sourcesHtml}
        `;
        
        this.messagesContainer.appendChild(messageElement);
        this.scrollToBottom();
    }
    
    showError(message) {
        const errorElement = document.createElement('div');
        errorElement.className = 'message error';
        errorElement.textContent = message;
        this.messagesContainer.appendChild(errorElement);
        this.scrollToBottom();
        
        // Remove error message after 5 seconds
        setTimeout(() => {
            errorElement.remove();
        }, 5000);
    }
    
    setLoading(isLoading) {
        if (isLoading) {
            this.sendButton.disabled = true;
            this.loadingIndicator.style.display = 'flex';
            
            // Add typing indicator
            const typingIndicator = document.createElement('div');
            typingIndicator.className = 'message assistant typing-indicator';
            typingIndicator.innerHTML = `
                <div class="typing">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
            `;
            this.messagesContainer.appendChild(typingIndicator);
            this.scrollToBottom();
            
        } else {
            this.sendButton.disabled = false;
            this.loadingIndicator.style.display = 'none';
            
            // Remove typing indicator
            const typingIndicator = this.messagesContainer.querySelector('.typing-indicator');
            if (typingIndicator) {
                typingIndicator.remove();
            }
        }
    }
    
    scrollToBottom() {
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }
    
    adjustTextareaHeight() {
        this.messageInput.style.height = 'auto';
        this.messageInput.style.height = Math.min(this.messageInput.scrollHeight, 150) + 'px';
    }
}

// Initialize the chat when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', () => {
    window.chatApp = new ChatApp();
});

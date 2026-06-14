document.addEventListener('DOMContentLoaded', () => {
    const prepForm = document.getElementById('prep-form');
    const companyInput = document.getElementById('company-name');
    const submitBtn = document.getElementById('submit-btn');
    
    const welcomeState = document.getElementById('welcome-state');
    const loadingState = document.getElementById('loading-state');
    const resultsDashboard = document.getElementById('results-dashboard');
    const errorAlert = document.getElementById('error-alert');
    const errorMessage = document.getElementById('error-message');
    
    // Result fields
    const resultCompanyTitle = document.getElementById('result-company-title');
    const summaryContent = document.getElementById('summary-content');
    const newsContent = document.getElementById('news-content');
    const painPointsContent = document.getElementById('pain-points-content');
    const questionsContent = document.getElementById('questions-content');
    const peopleContent = document.getElementById('people-content');
    
    // Action buttons
    const copyBtn = document.getElementById('copy-btn');
    const printBtn = document.getElementById('print-btn');
    
    // Local copy variable to store fetched data
    let currentBrief = null;
    let isProcessing = false;

    prepForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        if (isProcessing) return;

        const companyName = companyInput.value.trim();
        
        // 1. Client-Side Input Validation
        if (!companyName) {
            showLocalError('Company name cannot be blank.');
            return;
        }

        if (companyName.length > 100) {
            showLocalError('Company name cannot exceed 100 characters.');
            return;
        }

        if (/[<>]/.test(companyName)) {
            showLocalError('Company name contains invalid HTML/tag characters.');
            return;
        }

        // Lock form states
        isProcessing = true;
        
        // Reset UI states
        errorAlert.classList.add('hidden');
        welcomeState.classList.add('hidden');
        resultsDashboard.classList.add('hidden');
        loadingState.classList.remove('hidden');
        
        // Disable submit button and input to prevent spam
        submitBtn.disabled = true;
        companyInput.disabled = true;
        const originalBtnText = submitBtn.innerHTML;
        submitBtn.innerHTML = `
            <span>Analyzing ${escapeHtml(companyName)}...</span>
            <span class="pulse-dot"></span>
        `;

        try {
            const response = await fetch('/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ company_name: companyName })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to generate prep brief.');
            }

            // Save the data locally
            currentBrief = data;

            // Render details
            renderBrief(data);

            // Transition states
            loadingState.classList.add('hidden');
            resultsDashboard.classList.remove('hidden');
            
            // Scroll to results
            resultsDashboard.scrollIntoView({ behavior: 'smooth' });

        } catch (error) {
            console.error('Error fetching prep brief:', error);
            errorMessage.textContent = error.message || 'An unexpected error occurred.';
            errorAlert.classList.remove('hidden');
            loadingState.classList.add('hidden');
            welcomeState.classList.remove('hidden');
        } finally {
            // Restore form states
            isProcessing = false;
            submitBtn.disabled = false;
            companyInput.disabled = false;
            submitBtn.innerHTML = originalBtnText;
            // Reinitialize icons in case buttons changed
            lucide.createIcons();
        }
    });

    function showLocalError(message) {
        errorMessage.textContent = message;
        errorAlert.classList.remove('hidden');
        errorAlert.scrollIntoView({ behavior: 'smooth' });
    }

    function renderBrief(data) {
        // Set header title
        resultCompanyTitle.textContent = data.company_name || companyInput.value.trim();

        // 1. Render Summary
        summaryContent.innerHTML = `<p>${data.company_summary || 'No summary generated.'}</p>`;

        // 2. Render News
        if (data.recent_news && data.recent_news.length > 0) {
            newsContent.innerHTML = data.recent_news.map(news => `
                <div class="brief-item">
                    <div class="item-title">
                        <i data-lucide="arrow-right-circle" class="text-accent" style="width:16px;height:16px;margin-top:4px;"></i>
                        <span>${escapeHtml(news.title)}</span>
                    </div>
                    <div class="item-desc">${escapeHtml(news.summary)}</div>
                </div>
            `).join('');
        } else {
            newsContent.innerHTML = '<p class="text-muted">No recent news available.</p>';
        }

        // 3. Render Pain Points
        if (data.pain_points && data.pain_points.length > 0) {
            painPointsContent.innerHTML = data.pain_points.map(pain => `
                <div class="brief-item">
                    <div class="item-title">
                        <i data-lucide="alert-triangle" class="text-danger" style="width:16px;height:16px;margin-top:4px;"></i>
                        <span>${escapeHtml(pain.issue)}</span>
                    </div>
                    <div class="item-desc">${escapeHtml(pain.impact)}</div>
                    <div class="item-meta">
                        <div>
                            <span class="meta-label">Solution Angle:</span> 
                            <span class="meta-val">${escapeHtml(pain.solution_angle)}</span>
                        </div>
                    </div>
                </div>
            `).join('');
        } else {
            painPointsContent.innerHTML = '<p class="text-muted">No pain points identified.</p>';
        }

        // 4. Render Discovery Questions
        if (data.discovery_questions && data.discovery_questions.length > 0) {
            questionsContent.innerHTML = data.discovery_questions.map(q => `
                <div class="brief-item">
                    <div class="item-title">
                        <i data-lucide="help-circle" class="text-success" style="width:16px;height:16px;margin-top:4px;"></i>
                        <span>${escapeHtml(q.question)}</span>
                    </div>
                    <div class="item-meta">
                        <div>
                            <span class="meta-label">Buyer Intent target:</span> 
                            <span class="meta-val">${escapeHtml(q.intent)}</span>
                        </div>
                    </div>
                </div>
            `).join('');
        } else {
            questionsContent.innerHTML = '<p class="text-muted">No discovery questions generated.</p>';
        }

        // 5. Render Key Stakeholders
        if (data.key_people && data.key_people.length > 0) {
            peopleContent.innerHTML = data.key_people.map(person => `
                <div class="brief-item">
                    <div class="item-title">
                        <i data-lucide="user-check" class="text-info" style="width:16px;height:16px;margin-top:4px;"></i>
                        <span>${escapeHtml(person.name)}</span>
                    </div>
                    <div class="item-desc">Role: <strong>${escapeHtml(person.role)}</strong></div>
                    <div class="item-meta">
                        <div>
                            <span class="meta-label">Engagement Strategy:</span> 
                            <span class="meta-val">${escapeHtml(person.focus)}</span>
                        </div>
                    </div>
                </div>
            `).join('');
        } else {
            peopleContent.innerHTML = '<p class="text-muted">No specific stakeholder profiles suggested.</p>';
        }

        // Re-render Lucide icons for all dynamically added nodes
        lucide.createIcons();
    }

    // Helper to prevent HTML Injection
    function escapeHtml(str) {
        if (!str) return '';
        return str
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Print Button Handler
    printBtn.addEventListener('click', () => {
        window.print();
    });

    // Copy Button Handler
    copyBtn.addEventListener('click', () => {
        if (!currentBrief) return;

        try {
            const copyText = formatBriefForClipboard(currentBrief);
            navigator.clipboard.writeText(copyText).then(() => {
                // Temporary feedback on copy button
                const originalText = copyBtn.innerHTML;
                copyBtn.innerHTML = `<i data-lucide="check"></i> <span>Copied!</span>`;
                lucide.createIcons();
                setTimeout(() => {
                    copyBtn.innerHTML = originalText;
                    lucide.createIcons();
                }, 2000);
            }).catch(err => {
                alert('Could not copy text to clipboard: ' + err);
            });
        } catch (e) {
            console.error('Copy failure', e);
        }
    });

    function formatBriefForClipboard(data) {
        let text = `==================================================\n`;
        text += `SALES PREPARATION BRIEF: ${data.company_name.toUpperCase()}\n`;
        text += `==================================================\n\n`;
        
        text += `[COMPANY SUMMARY]\n${data.company_summary}\n\n`;
        
        text += `[RECENT NEWS & TRIGGER EVENTS]\n`;
        data.recent_news.forEach((news, idx) => {
            text += `${idx + 1}. ${news.title}\n   Context: ${news.summary}\n\n`;
        });
        
        text += `[POTENTIAL PAIN POINTS]\n`;
        data.pain_points.forEach((pain, idx) => {
            text += `${idx + 1}. Issue: ${pain.issue}\n   Impact: ${pain.impact}\n   Approach: ${pain.solution_angle}\n\n`;
        });
        
        text += `[STRATEGIC DISCOVERY QUESTIONS]\n`;
        data.discovery_questions.forEach((q, idx) => {
            text += `${idx + 1}. Question: ${q.question}\n   Target Intent: ${q.intent}\n\n`;
        });
        
        text += `[KEY STAKEHOLDERS TO RESEARCH]\n`;
        data.key_people.forEach((person, idx) => {
            text += `${idx + 1}. Profile/Name: ${person.name} (${person.role})\n   Engagement Focus: ${person.focus}\n\n`;
        });
        
        text += `--------------------------------------------------\n`;
        text += `Generated via SalesPrep.AI\n`;
        return text;
    }
});

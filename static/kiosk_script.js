document.addEventListener("DOMContentLoaded", function() {

    // --- Get Elements ---
    const startPassForm = document.getElementById("start-pass-form");
    const startStudentIdInput = document.getElementById("start-student-id-input");
    const startMessageArea = document.getElementById("start-message-area");

    const returnPassForm = document.getElementById("return-pass-form");
    const returnStudentIdInput = document.getElementById("return-student-id-input");
    const returnMessageArea = document.getElementById("return-message-area");

    const activePassesList = document.getElementById("active-passes-list");
    const passesHeader = document.getElementById("passes-header");
    const capacityIndicator = document.getElementById("capacity-indicator");

    // --- Form Submission for Starting a Pass ---
    startPassForm.addEventListener("submit", function(event) {
        event.preventDefault();
        const studentId = startStudentIdInput.value;

        fetch("/start_pass", {
            method: "POST",
            headers: {"Content-Type": "application/x-www-form-urlencoded"},
            body: `student_id=${studentId}`
        })
        .then(response => response.json())
        .then(data => {
            showMessage(startMessageArea, data.message, data.success ? "success" : "error");
            if (data.success) {
                startStudentIdInput.value = ""; // Clear input on success
                fetchActivePasses(); // Refresh the list immediately
            }
        })
        .catch(error => {
            console.error("Error:", error);
            showMessage(startMessageArea, "A network error occurred.", "error");
        });
    });

    // --- Form Submission for Returning a Pass ---
    returnPassForm.addEventListener("submit", function(event) {
        event.preventDefault();
        const studentId = returnStudentIdInput.value;

        fetch("/return_by_student_id", {
            method: "POST",
            headers: {"Content-Type": "application/x-www-form-urlencoded"},
            body: `student_id=${studentId}`
        })
        .then(response => response.json())
        .then(data => {
            showMessage(returnMessageArea, data.message, data.success ? "success" : "error");
            if (data.success) {
                returnStudentIdInput.value = ""; // Clear input on success
                fetchActivePasses(); // Refresh the list immediately
            }
        })
        .catch(error => {
            console.error("Error:", error);
            showMessage(returnMessageArea, "A network error occurred.", "error");
        });
    });

    // --- Display Messages ---
    function showMessage(areaElement, text, type) {
        areaElement.textContent = text;
        areaElement.className = `message ${type}`;
        setTimeout(() => {
            areaElement.textContent = "";
            areaElement.className = "message";
        }, 5000); // Message disappears after 5 seconds
    }

    // --- Active Pass Polling ---
    function fetchActivePasses() {
        fetch("/api/active_passes")
            .then(response => response.json())
            .then(data => {
                // Handle both old format (array) and new format (object with passes and capacity)
                if (Array.isArray(data)) {
                    // Old format - just passes
                    renderPasses(data);
                    updateCapacityIndicator(null);
                } else {
                    // New format - object with passes and capacity info
                    renderPasses(data.passes || []);
                    updateCapacityIndicator(data.capacity);
                }
            })
            .catch(error => {
                console.error("Error fetching active passes:", error);
            });
    }

    // --- Update Capacity Indicator ---
    function updateCapacityIndicator(capacity) {
        if (!capacity || !capacity.enabled) {
            capacityIndicator.innerHTML = "";
            passesHeader.textContent = "Students Currently Out";
            return;
        }

        const current = capacity.current;
        const max = capacity.max;
        const percentage = max > 0 ? (current / max) * 100 : 0;
        const isNearCapacity = percentage >= 80;
        const isAtCapacity = current >= max;

        // Update header with capacity info
        passesHeader.textContent = `Students Currently Out (${current}/${max})`;

        // Create capacity indicator
        const statusColor = isAtCapacity ? 'var(--error)' : isNearCapacity ? 'var(--warning)' : 'var(--success)';
        const statusText = isAtCapacity ? 'At Capacity' : isNearCapacity ? 'Near Capacity' : 'Available';

        capacityIndicator.innerHTML = `
            <div style="
                background: var(--bg-tertiary); 
                padding: 16px; 
                border-radius: 12px; 
                border: 1px solid var(--border);
                ${isAtCapacity ? 'border-left: 4px solid var(--error);' : ''}
            ">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <span style="font-weight: 600; color: var(--text-primary);">Capacity Status</span>
                    <span style="
                        color: ${statusColor}; 
                        font-weight: 600; 
                        font-size: 0.9rem;
                        ${isAtCapacity ? 'animation: pulse 2s infinite;' : ''}
                    ">${statusText}</span>
                </div>
                <div style="
                    width: 100%; 
                    height: 8px; 
                    background: var(--border); 
                    border-radius: 4px; 
                    overflow: hidden;
                    margin-bottom: 4px;
                ">
                    <div style="
                        height: 100%; 
                        background: ${statusColor}; 
                        width: ${percentage}%; 
                        transition: all 0.5s ease;
                        ${isAtCapacity ? 'animation: pulse-bg 2s infinite;' : ''}
                    "></div>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 0.8rem; color: var(--text-muted);">
                    <span>0</span>
                    <span>${max}</span>
                </div>
            </div>
        `;
    }

    // --- Render Pass Cards ---
    function renderPasses(passes) {
        activePassesList.innerHTML = ""; // Clear the list
        if (passes.length === 0) {
            activePassesList.innerHTML = "<p>No students are currently out.</p>";
            return;
        }

        passes.forEach(pass => {
            const isOvertime = pass.time_remaining < 0;
            const card = document.createElement("div");
            card.className = `pass-card ${isOvertime ? 'overtime' : ''}`;

            const nameEl = document.createElement("h3");
            nameEl.textContent = pass.full_name;

            const timerEl = document.createElement("div");
            timerEl.className = "timer";
            timerEl.textContent = formatTime(pass.time_remaining);

            card.appendChild(nameEl);
            card.appendChild(timerEl);
            activePassesList.appendChild(card);
        });
    }

    // --- Time Formatting Helper ---
    function formatTime(totalSeconds) {
        const isNegative = totalSeconds < 0;
        if (isNegative) {
            totalSeconds = -totalSeconds;
        }
        
        const minutes = Math.floor(totalSeconds / 60);
        const seconds = totalSeconds % 60;

        const sign = isNegative ? "-" : "";
        return `${sign}${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    }

    // --- Initial Load and Periodic Refresh ---
    fetchActivePasses(); // Load on page start
    setInterval(fetchActivePasses, 2000); // Refresh every 2 seconds
});

// Add CSS for capacity animations
const style = document.createElement('style');
style.textContent = `
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
    @keyframes pulse-bg {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }
`;
document.head.appendChild(style);
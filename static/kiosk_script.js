document.addEventListener("DOMContentLoaded", function() {
    const passForm = document.getElementById("pass-form");
    const studentIdInput = document.getElementById("student-id-input");
    const messageArea = document.getElementById("message-area");
    const activePassesList = document.getElementById("active-passes-list");
    const passesHeader = document.getElementById("passes-header");
    const capacityIndicator = document.getElementById("capacity-indicator");

    passForm.addEventListener("submit", function(event) {
        event.preventDefault();
        const studentId = studentIdInput.value.trim();

        if (!studentId) {
            showMessage("Please enter a Student ID", "error");
            return;
        }

        const submitBtn = passForm.querySelector('button[type="submit"]');
        submitBtn.disabled = true;
        submitBtn.style.opacity = '0.6';

        checkStudentStatus(studentId, submitBtn);
    });

    function checkStudentStatus(studentId, submitBtn) {
        fetch("/api/active_passes")
            .then(response => response.json())
            .then(data => {
                const passes = Array.isArray(data) ? data : (data.passes || []);
                const isOut = passes.some(pass => pass.student_id === studentId);

                if (isOut) {
                    returnPass(studentId, submitBtn);
                } else {
                    startPass(studentId, submitBtn);
                }
            })
            .catch(error => {
                console.error("Error:", error);
                showMessage("Network error. Please try again.", "error");
                submitBtn.disabled = false;
                submitBtn.style.opacity = '1';
            });
    }

    function startPass(studentId, submitBtn) {
        fetch("/start_pass", {
            method: "POST",
            headers: {"Content-Type": "application/x-www-form-urlencoded"},
            body: `student_id=${encodeURIComponent(studentId)}`
        })
        .then(response => response.json())
        .then(data => {
            showMessage(data.message, data.success ? "success" : "error");
            if (data.success) {
                studentIdInput.value = "";
                fetchActivePasses();
            }
            submitBtn.disabled = false;
            submitBtn.style.opacity = '1';
            studentIdInput.focus();
        })
        .catch(error => {
            console.error("Error:", error);
            showMessage("Network error. Please try again.", "error");
            submitBtn.disabled = false;
            submitBtn.style.opacity = '1';
        });
    }

    function returnPass(studentId, submitBtn) {
        fetch("/return_by_student_id", {
            method: "POST",
            headers: {"Content-Type": "application/x-www-form-urlencoded"},
            body: `student_id=${encodeURIComponent(studentId)}`
        })
        .then(response => response.json())
        .then(data => {
            showMessage(data.message, data.success ? "success" : "error");
            if (data.success) {
                studentIdInput.value = "";
                fetchActivePasses();
            }
            submitBtn.disabled = false;
            submitBtn.style.opacity = '1';
            studentIdInput.focus();
        })
        .catch(error => {
            console.error("Error:", error);
            showMessage("Network error. Please try again.", "error");
            submitBtn.disabled = false;
            submitBtn.style.opacity = '1';
        });
    }

    function showMessage(text, type) {
        messageArea.textContent = text;
        messageArea.className = `message ${type}`;
        setTimeout(() => {
            messageArea.textContent = "";
            messageArea.className = "message";
        }, 5000);
    }

    function fetchActivePasses() {
        fetch("/api/active_passes")
            .then(response => response.json())
            .then(data => {
                if (Array.isArray(data)) {
                    renderPasses(data);
                    updateCapacityIndicator(null);
                } else {
                    renderPasses(data.passes || []);
                    updateCapacityIndicator(data.capacity);
                }
            })
            .catch(error => {
                console.error("Error fetching active passes:", error);
            });
    }

    function updateCapacityIndicator(capacity) {
        if (!capacity || !capacity.enabled) {
            capacityIndicator.innerHTML = "";
            passesHeader.textContent = "Students Currently Out";
            return;
        }

        const current = capacity.current;
        const max = capacity.max;
        const percentage = max > 0 ? (current / max) * 100 : 0;
        const isAtCapacity = current >= max;
        const statusColor = isAtCapacity ? '#ef4444' : percentage >= 80 ? '#f59e0b' : '#10b981';

        passesHeader.textContent = `Students Currently Out (${current}/${max})`;

        capacityIndicator.innerHTML = `
            <div style="background: #1a1a1a; padding: 25px; border-radius: 20px; border: 2px solid #333;">
                <div style="width: 100%; height: 16px; background: #333; border-radius: 8px; overflow: hidden; margin-bottom: 12px;">
                    <div style="height: 100%; background: ${statusColor}; width: ${percentage}%; transition: all 0.5s ease;"></div>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 1.1rem; color: #a3a3a3; font-weight: 600;">
                    <span>0</span>
                    <span style="color: ${statusColor}; font-weight: 800; font-size: 1.3rem;">${current} / ${max}</span>
                </div>
            </div>
        `;
    }

    function renderPasses(passes) {
        activePassesList.innerHTML = "";
        if (passes.length === 0) {
            activePassesList.innerHTML = "<p>✓ All Clear</p>";
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

    function formatTime(totalSeconds) {
        const isNegative = totalSeconds < 0;
        if (isNegative) totalSeconds = -totalSeconds;
        
        const minutes = Math.floor(totalSeconds / 60);
        const seconds = totalSeconds % 60;

        const sign = isNegative ? "-" : "";
        return `${sign}${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    }

    studentIdInput.addEventListener('focus', function() {
        this.select();
    });

    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            studentIdInput.value = '';
            studentIdInput.focus();
        }
    });

    fetchActivePasses();
    setInterval(fetchActivePasses, 2000);
});

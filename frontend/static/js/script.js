document.addEventListener('DOMContentLoaded', function() {
    // ✅ DEVICE ID — stable per-browser so the same device cannot appraise the same person twice
    function getOrCreateDeviceId() {
        let id = localStorage.getItem('dclm_device_id');
        if (!id) {
            if (crypto.randomUUID) {
                id = crypto.randomUUID();
            } else {
                id = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
                    const r = Math.random() * 16 | 0;
                    const v = c === 'x' ? r : (r & 0x3 | 0x8);
                    return v.toString(16);
                });
            }
            localStorage.setItem('dclm_device_id', id);
        }
        return id;
    }
    const deviceField = document.getElementById('device_id');
    if (deviceField) {
        deviceField.value = getOrCreateDeviceId();
    }

    // ✅ NAME AUTOCOMPLETE — staff list intelligence
    const nameInput = document.getElementById('staff_name');
    if (nameInput && window.STAFF_NAMES && window.STAFF_NAMES.length) {
        const suggestionsBox = document.getElementById('name-suggestions');
        let activeIndex = -1;

        function showSuggestions(list) {
            suggestionsBox.innerHTML = '';
            activeIndex = -1;
            if (!list.length) {
                suggestionsBox.classList.add('hidden');
                return;
            }
            list.forEach(function(name) {
                const div = document.createElement('div');
                div.textContent = name;
                div.className = 'name-suggestion-item';
                div.addEventListener('mousedown', function(e) {
                    e.preventDefault();
                    selectName(name);
                });
                div.addEventListener('touchstart', function(e) {
                    e.preventDefault();
                    selectName(name);
                });
                suggestionsBox.appendChild(div);
            });
            suggestionsBox.classList.remove('hidden');
        }

        function selectName(name) {
            nameInput.value = name;
            suggestionsBox.classList.add('hidden');
            activeIndex = -1;
        }

        nameInput.addEventListener('input', function() {
            const query = nameInput.value.trim().toLowerCase();
            hideOnFocusName(query);
        });

        function hideOnFocusName(query) {
            if (!query) {
                suggestionsBox.classList.add('hidden');
                return;
            }
            const matches = window.STAFF_NAMES.filter(function(n) {
                return n.toLowerCase().indexOf(query) !== -1;
            }).slice(0, 8);
            showSuggestions(matches);
        }

        nameInput.addEventListener('keydown', function(e) {
            const kids = Array.from(suggestionsBox.children);
            if (!kids.length) return;
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                activeIndex = (activeIndex + 1) % kids.length;
                highlightActive();
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                activeIndex = (activeIndex - 1 + kids.length) % kids.length;
                highlightActive();
            } else if (e.key === 'Enter' && activeIndex >= 0) {
                e.preventDefault();
                selectName(kids[activeIndex].textContent);
            }
        });

        function highlightActive() {
            const kids = Array.from(suggestionsBox.children);
            kids.forEach(function(k, i) {
                k.classList.toggle('active', i === activeIndex);
            });
        }

        document.addEventListener('click', function(e) {
            if (!nameInput.parentElement.contains(e.target)) {
                suggestionsBox.classList.add('hidden');
            }
        });
    }

    const form = document.getElementById('appraisalForm');
    const progressFill = document.getElementById('progress-fill');
    const progressPercent = document.getElementById('progress-percent');
    const submissionProgress = document.getElementById('submission-progress');
    const submissionFill = document.getElementById('submission-fill');
    const submissionPercent = document.getElementById('submission-percent');
    const submissionStatus = document.getElementById('submission-status');
    const submitBtn = document.getElementById('submitBtn');

    // Required fields for form completion progress
    const requiredFields = [
        'staff_name',
        'christian_conduct',
        'job_performance',
        'reliability',
        'teamwork',
        'communication',
        'initiative',
        'adaptability',
        'overall_assessment'
    ];
    const totalFields = requiredFields.length;

    // Update form completion progress
    function updateProgress() {
        let completed = 0;
        requiredFields.forEach(fieldName => {
            const elements = document.getElementsByName(fieldName);
            if (elements[0].type === 'radio') {
                const isChecked = Array.from(elements).some(el => el.checked);
                if (isChecked) completed++;
            } else {
                if (elements[0].value.trim() !== '') completed++;
            }
        });
        const percentage = Math.round((completed / totalFields) * 100);
        progressFill.style.width = percentage + '%';
        progressPercent.textContent = percentage + '%';
    }

    // Initial progress update
    updateProgress();

    // Update on input/change
    form.addEventListener('input', updateProgress);
    form.addEventListener('change', updateProgress);

    // ✅ SUBMISSION PROGRESS BAR LOGIC — strict canonical name enforcement
    form.addEventListener('submit', function(e) {
        // Enforce exact canonical staff name (no variants)
        if (window.STAFF_NAMES && window.STAFF_NAMES.length) {
            const raw = document.getElementsByName('staff_name')[0].value;
            const collapsed = raw.trim().split(/\s+/).join(' ');
            if (!window.STAFF_NAMES.includes(collapsed)) {
                e.preventDefault();
                alert('⚠️ Please pick an exact name from the suggestions. Variant spellings are not accepted. Select the highlighted staff name.');
                const inp = document.getElementById('staff_name');
                if (inp) { inp.focus(); inp.style.borderColor = '#dc2626'; }
                window.scrollTo({top: 0, behavior: 'smooth'});
                return;
            }
        }
        // Validate first
        let missing = [];
        requiredFields.forEach(fieldName => {
            const elements = document.getElementsByName(fieldName);
            if (elements[0].type === 'radio') {
                const checked = Array.from(elements).some(el => el.checked);
                if (!checked) missing.push(fieldName);
            } else {
                if (!elements[0].value.trim()) missing.push(fieldName);
            }
        });

        if (missing.length > 0) {
            e.preventDefault();
            alert('Please complete all required sections before submitting.');
            window.scrollTo({top: 0, behavior: 'smooth'});
            return;
        }

        // ✅ Show submission progress bar
        submissionProgress.style.display = 'block';
        window.scrollTo({top: 0, behavior: 'smooth'});
        submitBtn.disabled = true;
        submitBtn.textContent = 'Submitting...';

        // Simulate progress animation (real progress happens in background)
        let progress = 0;
        const interval = setInterval(() => {
            progress += Math.random() * 12;
            if (progress >= 100) {
                progress = 100;
                submissionStatus.textContent = '✅ Saving complete!';
                clearInterval(interval);
            } else {
                submissionStatus.textContent = '⏳ Saving your appraisal to database...';
            }
            submissionFill.style.width = progress + '%';
            submissionPercent.textContent = Math.round(progress) + '%';
        }, 250);
    });

    // Highlight active section
    const radioOptions = document.querySelectorAll('.radio-option');
    radioOptions.forEach(option => {
        option.addEventListener('click', function() {
            const section = this.closest('.form-section');
            section.style.borderColor = '#1a365d';
            section.style.backgroundColor = '#f0f4f8';
        });
    });
});
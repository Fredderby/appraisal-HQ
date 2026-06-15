document.addEventListener('DOMContentLoaded', function() {
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

    // ✅ SUBMISSION PROGRESS BAR LOGIC
    form.addEventListener('submit', function(e) {
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
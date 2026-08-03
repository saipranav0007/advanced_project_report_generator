// frontend/static/js/dashboard.js

document.addEventListener('DOMContentLoaded', function() {
    // 1. Auto-dismiss Flash Alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    
    alerts.forEach(alert => {
        setTimeout(() => {
            // Using Bootstrap's native alert closure logic if available
            if (typeof bootstrap !== 'undefined') {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            } else {
                // Fallback fade out
                alert.style.transition = 'opacity 0.5s ease';
                alert.style.opacity = '0';
                setTimeout(() => alert.remove(), 500);
            }
        }, 5000);
    });

    // 2. Chart.js Placeholder (For analytics.html)
    const chartCanvas = document.getElementById('generationChart');
    if (chartCanvas) {
        console.log("Analytics canvas detected. Ready for Chart.js initialization.");
        // Future logic to fetch user data and render charts goes here.
    }

    // 3. Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
});
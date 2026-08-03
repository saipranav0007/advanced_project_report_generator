// frontend/static/js/validation.js

document.addEventListener('DOMContentLoaded', function() {
    // 1. Bootstrap Custom Form Validation
    const forms = document.querySelectorAll('.needs-validation');

    Array.from(forms).forEach(form => {
        form.addEventListener('submit', event => {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });

    // 2. Password Matching Validation (Profile & Register pages)
    const passwordInput = document.querySelector('input[name="new_password"], input[name="password"]');
    const confirmPasswordInput = document.querySelector('input[name="confirm_new_password"], input[name="confirm_password"]');

    if (passwordInput && confirmPasswordInput) {
        const validatePasswords = () => {
            if (confirmPasswordInput.value !== passwordInput.value) {
                confirmPasswordInput.setCustomValidity("Passwords do not match.");
            } else {
                confirmPasswordInput.setCustomValidity("");
            }
        };

        passwordInput.addEventListener('input', validatePasswords);
        confirmPasswordInput.addEventListener('input', validatePasswords);
    }
    
    // 3. File Upload Size Limitation (Profile Avatar)
    const fileInputs = document.querySelectorAll('input[type="file"]');
    const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB

    fileInputs.forEach(input => {
        input.addEventListener('change', function() {
            if (this.files && this.files[0]) {
                if (this.files[0].size > MAX_FILE_SIZE) {
                    alert('File is too large. Maximum size is 5MB.');
                    this.value = ''; // Clear the input
                }
            }
        });
    });
});
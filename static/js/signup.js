document.addEventListener("DOMContentLoaded", () => {

    const form = document.getElementById("signupForm");

    if (!form) {
        return;
    }


    const steps = Array.from(
        document.querySelectorAll(".signup-step")
    );


    const nextButton =
        document.getElementById("nextButton");

    const backButton =
        document.getElementById("backButton");

    const submitButton =
        document.getElementById("submitButton");

    const progressBar =
        document.getElementById("signupProgress");

    const stepLabel =
        document.getElementById("stepLabel");

    const progressLabel =
        document.getElementById("progressLabel");


    let currentStep = 0;


    // =========================================================
    // DISPLAY STEP
    // =========================================================

    function showStep(index) {

        steps.forEach((step, stepIndex) => {

            step.classList.toggle(
                "active",
                stepIndex === index
            );

        });


        const percentage =
            ((index + 1) / steps.length) * 100;


        progressBar.style.width =
            `${percentage}%`;


        stepLabel.textContent =
            `Step ${index + 1} of ${steps.length}`;


        progressLabel.textContent =
            `${Math.round(percentage)}%`;


        backButton.hidden =
            index === 0;


        nextButton.hidden =
            index === steps.length - 1;


        submitButton.hidden =
            index !== steps.length - 1;


        focusCurrentInput(index);

    }


    // =========================================================
    // AUTO-FOCUS
    // =========================================================

    function focusCurrentInput(index) {

        const input =
            steps[index].querySelector("input");

        if (!input) {
            return;
        }


        window.setTimeout(() => {

            input.focus();

        }, 250);

    }


    // =========================================================
    // ERROR HANDLING
    // =========================================================

    function getErrorBox(step) {

        return step.querySelector(
            ".client-error"
        );

    }


    function clearError(step) {

        const input =
            step.querySelector("input");

        const errorBox =
            getErrorBox(step);


        if (input) {

            input.classList.remove(
                "input-error"
            );

            input.removeAttribute(
                "aria-invalid"
            );

        }


        if (errorBox) {

            errorBox.textContent = "";

        }

    }


    function showError(step, message) {

        const input =
            step.querySelector("input");

        const errorBox =
            getErrorBox(step);


        if (input) {

            input.classList.add(
                "input-error"
            );

            input.setAttribute(
                "aria-invalid",
                "true"
            );

        }


        if (errorBox) {

            errorBox.textContent = message;

        }

    }


    // =========================================================
    // VALIDATION
    // =========================================================

    function validateCurrentStep() {

        const step =
            steps[currentStep];

        const input =
            step.querySelector("input");


        if (!input) {
            return true;
        }


        clearError(step);


        const value =
            input.value.trim();


        // ---------------------------------------------
        // Required fields
        // ---------------------------------------------

        if (!value) {

            switch (input.name) {

                case "username":

                    showError(
                        step,
                        "Please choose a username."
                    );

                    break;


                case "email":

                    showError(
                        step,
                        "Please enter your email address."
                    );

                    break;


                case "password1":

                    showError(
                        step,
                        "Please create a password."
                    );

                    break;


                case "password2":

                    showError(
                        step,
                        "Please confirm your password."
                    );

                    break;


                default:

                    showError(
                        step,
                        "This field is required."
                    );

            }


            return false;

        }


        // ---------------------------------------------
        // Username
        // ---------------------------------------------

        if (input.name === "username") {

            if (value.length < 3) {

                showError(
                    step,
                    "Your username must contain at least 3 characters."
                );

                return false;

            }

        }


        // ---------------------------------------------
        // Email
        // ---------------------------------------------

        if (input.name === "email") {

            const emailPattern =
                /^[^\s@]+@[^\s@]+\.[^\s@]+$/;


            if (!emailPattern.test(value)) {

                showError(
                    step,
                    "Please enter a valid email address."
                );

                return false;

            }

        }


        // ---------------------------------------------
        // Password
        // ---------------------------------------------

        if (input.name === "password1") {

            if (value.length < 8) {

                showError(
                    step,
                    "Your password must contain at least 8 characters."
                );

                return false;

            }


            if (/^\d+$/.test(value)) {

                showError(
                    step,
                    "Your password cannot contain numbers only."
                );

                return false;

            }

        }


        // ---------------------------------------------
        // Confirm password
        // ---------------------------------------------

        if (input.name === "password2") {

            const passwordOne =
                form.querySelector(
                    '[name="password1"]'
                );


            if (
                !passwordOne ||
                value !== passwordOne.value
            ) {

                showError(
                    step,
                    "Your passwords do not match."
                );

                return false;

            }

        }


        return true;

    }


    // =========================================================
    // NEXT BUTTON
    // =========================================================

    nextButton.addEventListener(
        "click",
        () => {

            if (!validateCurrentStep()) {
                return;
            }


            if (
                currentStep <
                steps.length - 1
            ) {

                currentStep += 1;

                showStep(currentStep);

            }

        }
    );


    // =========================================================
    // BACK BUTTON
    // =========================================================

    backButton.addEventListener(
        "click",
        () => {

            if (currentStep > 0) {

                currentStep -= 1;

                showStep(currentStep);

            }

        }
    );


    // =========================================================
    // SUBMIT
    // =========================================================

    form.addEventListener(
        "submit",
        (event) => {

            if (!validateCurrentStep()) {

                event.preventDefault();

            }

        }
    );


    // =========================================================
    // CLEAR ERRORS WHILE TYPING
    // =========================================================

    steps.forEach((step) => {

        const input =
            step.querySelector("input");


        if (!input) {
            return;
        }


        input.addEventListener(
            "input",
            () => {

                clearError(step);

            }
        );


        // Press Enter to move forward.
        input.addEventListener(
            "keydown",
            (event) => {

                if (event.key !== "Enter") {
                    return;
                }


                event.preventDefault();


                if (
                    currentStep <
                    steps.length - 1
                ) {

                    nextButton.click();

                }

                else {

                    submitButton.click();

                }

            }
        );

    });


    // =========================================================
    // PASSWORD SHOW / HIDE
    // =========================================================

    document
        .querySelectorAll(".password-toggle")
        .forEach((button) => {

            button.addEventListener(
                "click",
                () => {

                    const target =
                        button.dataset.target;


                    const input =
                        document.getElementById(
                            target
                        );


                    if (!input) {
                        return;
                    }


                    const currentlyHidden =
                        input.type === "password";


                    input.type =
                        currentlyHidden
                            ? "text"
                            : "password";


                    button.textContent =
                        currentlyHidden
                            ? "Hide"
                            : "Show";


                    button.setAttribute(
                        "aria-label",
                        currentlyHidden
                            ? "Hide password"
                            : "Show password"
                    );

                }
            );

        });


    // =========================================================
    // DJANGO SERVER-SIDE ERRORS
    //
    // If Allauth rejects a username/email/password,
    // return the customer directly to that question.
    // =========================================================

    const serverErrorIndex =
        steps.findIndex(
            (step) =>
                step.querySelector(
                    ".server-error"
                )
        );


    if (serverErrorIndex !== -1) {

        currentStep =
            serverErrorIndex;

    }


    // =========================================================
    // INITIALISE
    // =========================================================

    showStep(currentStep);

});
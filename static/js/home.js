document.addEventListener("DOMContentLoaded", () => {

    initialisePromoBanner();
    initialiseRevealAnimations();
    initialiseChangingWords();
    initialiseScrollButtons();
    initialiseTiltCards();
    initialiseRippleButtons();

});


/* =========================================================
   PROMOTIONAL BANNER

   Supported modes:

   static
   scroll
   flash
   both
========================================================= */

function initialisePromoBanner() {

    const banner = document.querySelector(".promo-banner");

    if (!banner) {
        return;
    }

    const mode = (
        banner.dataset.bannerMode || "static"
    ).toLowerCase();


    banner.classList.remove(
        "banner-static",
        "banner-scroll",
        "banner-flash",
        "banner-both"
    );


    switch (mode) {

        case "scroll":

            banner.classList.add("banner-scroll");

            break;


        case "flash":

            banner.classList.add("banner-flash");

            break;


        case "both":

            banner.classList.add("banner-both");

            break;


        default:

            banner.classList.add("banner-static");

    }

}



/* =========================================================
   SCROLL REVEAL
========================================================= */

function initialiseRevealAnimations() {

    const elements = document.querySelectorAll(".reveal");

    if (!elements.length) {
        return;
    }


    if (!("IntersectionObserver" in window)) {

        elements.forEach((element) => {
            element.classList.add("reveal-visible");
        });

        return;
    }


    const observer = new IntersectionObserver(
        (entries) => {

            entries.forEach((entry) => {

                if (entry.isIntersecting) {

                    entry.target.classList.add(
                        "reveal-visible"
                    );

                    observer.unobserve(
                        entry.target
                    );

                }

            });

        },
        {
            threshold: 0.12
        }
    );


    elements.forEach((element, index) => {

        element.style.transitionDelay =
            `${Math.min(index * 40, 200)}ms`;

        observer.observe(element);

    });

}



/* =========================================================
   HERO CHANGING WORD
========================================================= */

function initialiseChangingWords() {

    const element = document.querySelector(
        ".hero-changing-word"
    );

    if (!element) {
        return;
    }


    const words = (
        element.dataset.words || ""
    )
        .split(",")
        .map((word) => word.trim())
        .filter(Boolean);


    if (words.length <= 1) {
        return;
    }


    let currentIndex = 0;


    window.setInterval(() => {

        element.classList.add(
            "word-changing"
        );


        window.setTimeout(() => {

            currentIndex =
                (currentIndex + 1) %
                words.length;


            element.textContent =
                words[currentIndex];


            element.classList.remove(
                "word-changing"
            );

        }, 250);

    }, 2600);

}



/* =========================================================
   SMOOTH SCROLL BUTTONS
========================================================= */

function initialiseScrollButtons() {

    const buttons = document.querySelectorAll(
        "[data-scroll-target]"
    );


    buttons.forEach((button) => {

        button.addEventListener(
            "click",
            () => {

                const selector =
                    button.dataset.scrollTarget;


                const target =
                    document.querySelector(selector);


                if (!target) {
                    return;
                }


                target.scrollIntoView({
                    behavior: "smooth",
                    block: "start"
                });

            }
        );

    });

}



/* =========================================================
   3D TILT CARDS
========================================================= */

function initialiseTiltCards() {

    const cards =
        document.querySelectorAll(
            ".js-tilt-card"
        );


    if (!cards.length) {
        return;
    }


    const reducedMotion =
        window.matchMedia(
            "(prefers-reduced-motion: reduce)"
        ).matches;


    const finePointer =
        window.matchMedia(
            "(pointer: fine)"
        ).matches;


    if (
        reducedMotion ||
        !finePointer
    ) {
        return;
    }


    cards.forEach((card) => {

        card.addEventListener(
            "mousemove",
            (event) => {

                const rect =
                    card.getBoundingClientRect();


                const x =
                    event.clientX -
                    rect.left;


                const y =
                    event.clientY -
                    rect.top;


                const centreX =
                    rect.width / 2;


                const centreY =
                    rect.height / 2;


                const rotateY =
                    ((x - centreX) /
                        centreX) *
                    3;


                const rotateX =
                    ((centreY - y) /
                        centreY) *
                    3;


                card.style.transform =
                    `perspective(900px)
                    rotateX(${rotateX}deg)
                    rotateY(${rotateY}deg)
                    translateY(-4px)`;

            }
        );


        card.addEventListener(
            "mouseleave",
            () => {

                card.style.transform = "";

            }
        );

    });

}



/* =========================================================
   BUTTON RIPPLE EFFECT
========================================================= */

function initialiseRippleButtons() {

    const buttons =
        document.querySelectorAll(
            ".js-ripple"
        );


    buttons.forEach((button) => {

        button.addEventListener(
            "click",
            (event) => {

                const existingRipple =
                    button.querySelector(
                        ".ripple-effect"
                    );


                if (existingRipple) {

                    existingRipple.remove();

                }


                const rect =
                    button.getBoundingClientRect();


                const size =
                    Math.max(
                        rect.width,
                        rect.height
                    );


                const x =
                    event.clientX -
                    rect.left -
                    size / 2;


                const y =
                    event.clientY -
                    rect.top -
                    size / 2;


                const ripple =
                    document.createElement(
                        "span"
                    );


                ripple.className =
                    "ripple-effect";


                ripple.style.width =
                    `${size}px`;


                ripple.style.height =
                    `${size}px`;


                ripple.style.left =
                    `${x}px`;


                ripple.style.top =
                    `${y}px`;


                button.appendChild(
                    ripple
                );


                window.setTimeout(
                    () => {
                        ripple.remove();
                    },
                    700
                );

            }
        );

    });

}
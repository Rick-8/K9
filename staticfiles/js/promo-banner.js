document.addEventListener("DOMContentLoaded", () => {

    initialisePromoBanner();

});


/* =========================================================
   K9 GLOBAL PROMOTIONAL BANNER

   Supported modes:

   static
   scroll
   flash
   both
========================================================= */

function initialisePromoBanner() {

    const banners = document.querySelectorAll(
        ".promo-banner"
    );


    if (!banners.length) {
        return;
    }


    banners.forEach((banner) => {

        const requestedMode = (
            banner.dataset.bannerMode || "static"
        )
            .trim()
            .toLowerCase();


        const allowedModes = [
            "static",
            "scroll",
            "flash",
            "both"
        ];


        const mode = allowedModes.includes(
            requestedMode
        )
            ? requestedMode
            : "static";


        banner.classList.remove(
            "banner-static",
            "banner-scroll",
            "banner-flash",
            "banner-both"
        );


        banner.classList.add(
            `banner-${mode}`
        );

    });

}
/**
 * F-05 Dynamic Pricing Estimates
 * Automatically retrieves and displays estimated JMD prices.
 */

"use strict";

const jmdFormatter = new Intl.NumberFormat("en-JM", {
    style: "currency",
    currency: "JMD",
    currencyDisplay: "narrowSymbol",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
});


async function loadVehiclePrice(container) {

    const priceElement = container.querySelector(".pricing-amount");
    const pricingUrl = container.dataset.pricingUrl;

    if (!priceElement || !pricingUrl) {
        return;
    }

    priceElement.textContent = "Calculating...";
    priceElement.classList.remove("pricing-unavailable");

    try {

        const response = await fetch(pricingUrl, {
            method: "GET",
            cache: "no-store",
            headers: {
                "Accept": "application/json"
            }
        });

        if (!response.ok) {
            throw new Error("Unable to retrieve price.");
        }

        const data = await response.json();

        if (
            data.status !== "success" ||
            data.estimated_jmd_price === null ||
            data.estimated_jmd_price === undefined ||
            data.estimated_jmd_price === ""
        ) {
            throw new Error("Price estimate unavailable.");
        }

        const estimatedPrice = Number(data.estimated_jmd_price);

        if (!Number.isFinite(estimatedPrice) || estimatedPrice < 0) {
            throw new Error("Invalid price estimate.");
        }

        priceElement.textContent =
            jmdFormatter.format(estimatedPrice);

    } catch (error) {

        priceElement.textContent = "Price unavailable";
        priceElement.classList.add("pricing-unavailable");

        console.error("F-05 Pricing Error:", error);

    }
}


function initializeDynamicPricing() {

    const pricingContainers = document.querySelectorAll(
        ".kj-price-estimate[data-pricing-url]"
    );

    pricingContainers.forEach(container => {
        loadVehiclePrice(container);
    });
}


if (document.readyState === "loading") {

    document.addEventListener(
        "DOMContentLoaded",
        initializeDynamicPricing
    );

} else {

    initializeDynamicPricing();

}



// Live customer make/model search and filter for F-04 (Ashaya Watts)

document.addEventListener("DOMContentLoaded", function () {

    const searchInput = document.querySelector('input[name="q"]');
    const searchForm = searchInput.closest("form");
    const results = document.getElementById("vehicle-results");

    let searchTimer;
    let controller;

    async function searchVehicles() {

        const query = searchInput.value.trim();

        // Cancel the previous request if another search is made.
        if (controller) {
            controller.abort();
        }

        controller = new AbortController();

        try {
            const response = await fetch(
                "/api/public/vehicles?q=" + encodeURIComponent(query),
                { signal: controller.signal }
            );

            if (!response.ok) {
                throw new Error("Search failed");
            }

            const vehicles = await response.json();

            results.replaceChildren();

            // Display a message if no vehicles match the search.
            if (vehicles.length === 0) {
                results.textContent = query
                    ? "No matching vehicles found"
                    : "No vehicles are currently available in the inventory.";
                return;
            }

            // Display matching vehicles.
            vehicles.forEach(function (vehicle) {

                const card = document.createElement("div");
                card.className = "kj-card";

                const title = document.createElement("h3");
                title.textContent =
                    `${vehicle.year} ${vehicle.make} ${vehicle.model}`;

                card.appendChild(title);

                // Display vehicle photo if available.
                if (vehicle.photo_urls && vehicle.photo_urls.length > 0) {
                    const image = document.createElement("img");
                    image.src = vehicle.photo_urls[0];
                    image.alt = `${vehicle.make} ${vehicle.model}`;
                    image.width = 250;
                    card.appendChild(image);
                }

                const color = document.createElement("p");
                color.textContent = `Color: ${vehicle.color}`;

                const mileage = document.createElement("p");
                mileage.textContent = `Mileage: ${vehicle.mileage_km} km`;

                const status = document.createElement("p");
                status.textContent = `Status: ${vehicle.availability}`;

                card.appendChild(color);
                card.appendChild(mileage);
                card.appendChild(status);
                const price = document.createElement("p");
                price.textContent = vehicle.estimated_jmd_price
                    ? `Estimated price: J$${vehicle.estimated_jmd_price}`
                    : "Estimated price: Unavailable";
                card.appendChild(price);

                // Display the ETA for upcoming vehicles.
                if (vehicle.availability === "Upcoming Arrival") {
                    const arrival = document.createElement("p");

                    arrival.textContent = vehicle.estimated_arrival
                        ? `Estimated Arrival: ${vehicle.estimated_arrival}`
                        : "Estimated arrival date is not yet available.";

                    card.appendChild(arrival);
                }

                const details = document.createElement("a");
                details.href = `/vehicle/${vehicle.id}`;
                details.textContent = "View Details";
                details.className = "kj-btn kj-btn-gold";

                card.appendChild(details);
                results.appendChild(card);
            });

        } catch (error) {
            if (error.name !== "AbortError") {
                results.textContent =
                    "Unable to load vehicles. Please try again.";
            }
        }
    }

    // Search automatically as the customer types.
    searchInput.addEventListener("input", function () {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(searchVehicles, 300);
    });

    // Search when the customer clicks the search button.
    searchForm.addEventListener("submit", function (event) {
        event.preventDefault();
        clearTimeout(searchTimer);
        searchVehicles();
    });
});

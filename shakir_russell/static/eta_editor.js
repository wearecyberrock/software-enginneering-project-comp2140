/* ============================================================================
   INTRODUCTION — shakir_russell/static/eta_editor.js
   ============================================================================
   Author:      Shakir Russell (Student ID: 620181663)
   Feature:     F-06 Shipment Status & ETA Updating (Client-Side Helper)

   What this file does:
     Runs in the staff member's web browser on `update_shipment.html` to make
     the form easier and safer to use:
     1. Shows the "Delay Reason" input box ONLY when the status dropdown is
        set to "Delayed", and hides it for other statuses.
     2. Checks that the ETA date (if typed) is a valid YYYY-MM-DD date before
        sending the form to Flask.
     3. Asks the staff member to confirm before archiving (soft-deleting) a
        shipment record (SRS §3.2).

   Libraries used:
     - None (100% plain/vanilla JavaScript built into every web browser).

   What it connects to in our code:
     - Loaded at the bottom of `shakir_russell/templates/update_shipment.html`
       via `<script src="/shakir/static/eta_editor.js"></script>`.
     - Connects to HTML element IDs: `status-select`, `delay-reason-group`,
       `eta-input`, `shipment-update-form`, `client-error-box`, and
       `soft-delete-form`.
   ============================================================================ */

// Wait until the entire HTML page has finished loading before looking up elements
document.addEventListener("DOMContentLoaded", function () {
  // Variable `statusSelect`: the <select> dropdown for transit status (F-06 SR-1)
  const statusSelect = document.getElementById("status-select");

  // Variable `delayReasonGroup`: the <div> wrapping the Delay Reason label and text box
  const delayReasonGroup = document.getElementById("delay-reason-group");

  // Variable `etaInput`: the <input type="date"> field for the ETA override (F-06 SR-2)
  const etaInput = document.getElementById("eta-input");

  // Variable `updateForm`: the <form> that submits the status and ETA update
  const updateForm = document.getElementById("shipment-update-form");

  // Variable `errorBox`: hidden red alert <div> used to show client-side error messages
  const errorBox = document.getElementById("client-error-box");

  // Variable `softDeleteForm`: the <form> that submits the soft-delete request
  const softDeleteForm = document.getElementById("soft-delete-form");

  // Helper function: show the Delay Reason box only when status === "Delayed"
  function toggleDelayReason() {
    // If either element is not on the page right now, do nothing
    if (!statusSelect || !delayReasonGroup) {
      return;
    }

    // Check whether the currently selected option in the dropdown is "Delayed"
    if (statusSelect.value === "Delayed") {
      // Show the Delay Reason input group
      delayReasonGroup.style.display = "block";
    } else {
      // Hide the Delay Reason input group for In Transit, Arrived, or Cleared
      delayReasonGroup.style.display = "none";
    }
  }

  // Run once as soon as the page loads so the initial visibility matches the saved status
  toggleDelayReason();

  // Re-run whenever the staff member picks a different status in the dropdown
  if (statusSelect) {
    statusSelect.addEventListener("change", toggleDelayReason);
  }

  // Validate the ETA date format right before the update form is submitted
  if (updateForm && etaInput) {
    updateForm.addEventListener("submit", function (event) {
      // Variable `etaValue`: trimmed text inside the ETA date picker
      const etaValue = etaInput.value.trim();

      // Variable `isoDatePattern`: regular expression matching YYYY-MM-DD (e.g. 2026-12-15)
      const isoDatePattern = /^\d{4}-\d{2}-\d{2}$/;

      // If an ETA was entered but does not match YYYY-MM-DD, stop submission and show error
      if (etaValue && !isoDatePattern.test(etaValue)) {
        event.preventDefault(); // Stop the browser from submitting bad data
        if (errorBox) {
          errorBox.textContent = "Please enter a valid ETA date in YYYY-MM-DD format.";
          errorBox.style.display = "block";
        }
        return;
      }

      // If valid, make sure any old client-side error message is hidden
      if (errorBox) {
        errorBox.style.display = "none";
      }
    });
  }

  // Ask for a quick confirmation before soft-deleting (archiving) a shipment
  if (softDeleteForm) {
    softDeleteForm.addEventListener("submit", function (event) {
      // Variable `confirmed`: true if staff clicks OK, false if they click Cancel
      const confirmed = window.confirm(
        "Archive (soft-delete) this shipment? It will be hidden from active searches but kept in the database."
      );
      // If staff clicked Cancel, stop the form from submitting
      if (!confirmed) {
        event.preventDefault();
      }
    });
  }
});

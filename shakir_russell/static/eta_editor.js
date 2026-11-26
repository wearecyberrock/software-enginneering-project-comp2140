// Client-side validation & delay reason toggle for F-06 (Shakir Russell)
(function () {
  "use strict";

  var form = document.getElementById("shipment-update-form");
  if (!form) {
    return;
  }

  var statusSelect = document.getElementById("status");
  var etaInput = document.getElementById("eta_date");
  var delayGroup = document.getElementById("delay-reason-group");
  var delayInput = document.getElementById("delay_reason");
  var errorBox = document.getElementById("form-client-error");

  function syncDelayField() {
    var isDelayed = statusSelect && statusSelect.value === "Delayed";
    if (delayGroup) {
      delayGroup.classList.toggle("is-delay-highlighted", isDelayed);
    }
    if (delayInput && statusSelect && (statusSelect.value === "Arrived" || statusSelect.value === "Cleared")) {
      delayInput.value = "";
    }
  }

  if (statusSelect) {
    statusSelect.addEventListener("change", syncDelayField);
    syncDelayField();
  }

  form.addEventListener("submit", function (event) {
    if (errorBox) {
      errorBox.hidden = true;
      errorBox.textContent = "";
    }

    if (etaInput && etaInput.value && !/^\d{4}-\d{2}-\d{2}$/.test(etaInput.value)) {
      event.preventDefault();
      if (errorBox) {
        errorBox.textContent = "Please enter a valid ETA date in YYYY-MM-DD format.";
        errorBox.hidden = false;
      }
      etaInput.focus();
    }
  });

  var deleteForms = document.querySelectorAll(".delete-form");
  Array.prototype.forEach.call(deleteForms, function (delForm) {
    delForm.addEventListener("submit", function (event) {
      var bol = delForm.getAttribute("data-bol") || "this shipment";
      if (!window.confirm("Archive shipment " + bol + "? It will be hidden via soft delete.")) {
        event.preventDefault();
      }
    });
  });
})();

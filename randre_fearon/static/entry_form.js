// Client-side checks for F-02 Manual Data Entry (Randre Fearon)
//
// This gives instant feedback before the form is sent (required fields, the deposit
// checkbox, and a preview of the chosen photos). It is only a convenience: the server
// (entry_service.py) checks everything again, so a user cannot skip these rules.
(function () {
  "use strict";

  var form = document.getElementById("vehicle-form");
  if (!form) { return; }

  var DEPOSIT_MESSAGE = "Deposit confirmation required";  // exact wording from the test plan
  var MAX_PHOTOS = 10;
  var MAX_PHOTO_BYTES = 5 * 1024 * 1024;
  var NEXT_YEAR = new Date().getFullYear() + 1;

  var errorBox = document.getElementById("form-errors");
  var errorList = document.getElementById("form-errors-list");
  var photoInput = document.getElementById("photos");
  var previews = document.getElementById("photo-previews");
  var previewUrls = [];

  // ---- Show / clear one field's error -------------------------------------
  function clearError(name) {
    var field = document.getElementById(name);
    var message = document.getElementById(name + "-error");
    if (message) { message.parentNode.removeChild(message); }
    if (field) {
      field.classList.remove("field-invalid");
      field.removeAttribute("aria-invalid");
      field.removeAttribute("aria-describedby");
    }
    var box = form.querySelector('.deposit-box[data-field="' + name + '"]');
    if (box) { box.classList.remove("field-invalid-box"); }
  }

  function showError(name, message) {
    clearError(name);
    var field = document.getElementById(name);
    var holder = form.querySelector('[data-field="' + name + '"]');
    if (!field || !holder) { return; }

    var p = document.createElement("p");
    p.className = "field-error";
    p.id = name + "-error";
    p.setAttribute("role", "alert");
    p.textContent = message;          // textContent (not innerHTML) so nothing typed can run as code
    holder.appendChild(p);

    if (holder.classList.contains("deposit-box")) {
      holder.classList.add("field-invalid-box");
    } else {
      field.classList.add("field-invalid");
    }
    field.setAttribute("aria-invalid", "true");
    field.setAttribute("aria-describedby", p.id);
  }

  // ---- Rules for each number field (mirrors entry_service.py) ----------------
  function checkNumber(value, min, max) {
    var n = Number(value.replace(/,/g, ""));
    return value !== "" && isFinite(n) && Math.floor(n) === n && n >= min && n <= max;
  }

  function checkAmount(value) {
    var n = Number(value.replace(/[$,\s]/g, ""));
    return value !== "" && isFinite(n) && n > 0;
  }

  function validateForm() {
    var problems = [];   // [fieldName, message]

    // 1. Required fields (marked data-required in the HTML)
    var required = form.querySelectorAll("[data-required]");
    Array.prototype.forEach.call(required, function (input) {
      if (input.value.trim() === "") {
        problems.push([input.id, input.getAttribute("data-label") + " is required"]);
      }
    });
    function alreadyFlagged(name) {
      return problems.some(function (p) { return p[0] === name; });
    }

    // 2. Numbers must make sense (only when something was typed)
    var year = document.getElementById("year").value.trim();
    if (year && !alreadyFlagged("year") && !checkNumber(year, 1900, NEXT_YEAR)) {
      problems.push(["year", "Year must be a whole number between 1900 and " + NEXT_YEAR]);
    }
    var cc = document.getElementById("engine_cc").value.trim();
    if (cc && !alreadyFlagged("engine_cc") && !checkNumber(cc, 1, 100000)) {
      problems.push(["engine_cc", "Engine size must be a whole number of cc, such as 2800"]);
    }
    var mileage = document.getElementById("mileage_km").value.trim();
    if (mileage && !checkNumber(mileage, 0, 9999999)) {
      problems.push(["mileage_km", "Mileage must be a whole number of kilometres (0 or more)"]);
    }
    var price = document.getElementById("base_foreign_price").value.trim();
    if (price && !alreadyFlagged("base_foreign_price") && !checkAmount(price)) {
      problems.push(["base_foreign_price", "Base price must be an amount greater than 0, such as 18500"]);
    }

    // 3. Bill of Lading format
    var bol = document.getElementById("bill_of_lading").value.trim();
    if (bol && !/^[A-Za-z0-9_-]{3,64}$/.test(bol)) {
      problems.push(["bill_of_lading", "Bill of Lading may only use letters, numbers, hyphens and underscores (3 to 64 characters)"]);
    }

    // 4. The deposit gate (F-02 SR-2)
    if (!document.getElementById("deposit_paid").checked) {
      problems.push(["deposit_paid", DEPOSIT_MESSAGE]);
    }

    // 5. Photos
    var photoProblem = checkPhotos();
    if (photoProblem) { problems.push(["photos", photoProblem]); }

    return problems;
  }

  function checkPhotos() {
    var files = photoInput.files;
    if (files.length > MAX_PHOTOS) {
      return "You can upload at most " + MAX_PHOTOS + " photos at a time";
    }
    for (var i = 0; i < files.length; i++) {
      if (!/^image\/(jpeg|png|gif|webp)$/.test(files[i].type)) {
        return '"' + files[i].name + '" is not a valid image (use JPG, PNG, GIF or WEBP)';
      }
      if (files[i].size > MAX_PHOTO_BYTES) {
        return '"' + files[i].name + '" is larger than 5 MB';
      }
    }
    return "";
  }

  // ---- Submit: block the send if anything is wrong ---------------------------
  form.addEventListener("submit", function (event) {
    var names = ["make", "model", "year", "category", "color", "mileage_km", "engine_cc", "origin_country",
                 "features", "bill_of_lading", "base_foreign_price", "base_currency", "departure_date",
                 "eta_date", "photos", "deposit_paid"];
    names.forEach(clearError);
    while (errorList.firstChild) { errorList.removeChild(errorList.firstChild); }

    var problems = validateForm();
    if (problems.length === 0) {              // all good: let the browser send the form
      errorBox.hidden = true;
      return;
    }

    event.preventDefault();
    problems.forEach(function (problem) {
      showError(problem[0], problem[1]);
      var li = document.createElement("li");
      li.textContent = problem[1];
      errorList.appendChild(li);
    });
    errorBox.hidden = false;
    errorBox.scrollIntoView({ behavior: "smooth", block: "start" });
    var first = document.getElementById(problems[0][0]);
    if (first) { first.focus({ preventScroll: true }); }
  });

  // ---- Clear a field's error as soon as the user fixes it ----------------------
  form.addEventListener("input", function (event) {
    if (event.target.id) { clearError(event.target.id); }
  });
  form.addEventListener("change", function (event) {
    // (the photo picker has its own handler below, which decides whether to show an error)
    if (event.target.id && event.target !== photoInput) { clearError(event.target.id); }
  });

  // ---- Photo preview -------------------------------------------------------------
  photoInput.addEventListener("change", function () {
    previewUrls.forEach(function (url) { URL.revokeObjectURL(url); });
    previewUrls = [];
    while (previews.firstChild) { previews.removeChild(previews.firstChild); }

    clearError("photos");
    var problem = checkPhotos();
    if (problem) { showError("photos", problem); return; }

    Array.prototype.forEach.call(photoInput.files, function (file) {
      var url = URL.createObjectURL(file);
      previewUrls.push(url);
      var img = document.createElement("img");
      img.src = url;
      img.alt = "Preview of " + file.name;
      previews.appendChild(img);
    });
  });
})();

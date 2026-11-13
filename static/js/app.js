/* BSU Medical Centre portal · progressive enhancement (the site works without JavaScript) */
(function () {
  "use strict";

  // ---------- theme toggle ----------
  function currentTheme() {
    return document.documentElement.getAttribute("data-theme") || "light";
  }
  document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try { localStorage.setItem("bsu-theme", next); } catch (e) {}
    });
  });

  // ---------- mobile navigation ----------
  var navToggle = document.querySelector("[data-nav-toggle]");
  var siteNav = document.getElementById("site-nav");
  if (navToggle && siteNav) {
    navToggle.addEventListener("click", function () {
      var open = siteNav.classList.toggle("open");
      navToggle.setAttribute("aria-expanded", String(open));
    });
  }

  // ---------- flash messages ----------
  document.querySelectorAll("[data-dismiss]").forEach(function (btn) {
    btn.addEventListener("click", function () { btn.parentElement.remove(); });
  });
  document.querySelectorAll(".flash-stack .alert").forEach(function (alert) {
    setTimeout(function () { alert.style.transition = "opacity .4s"; alert.style.opacity = "0"; }, 7000);
    setTimeout(function () { alert.remove(); }, 7500);
  });

  // ---------- confirmations ----------
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!window.confirm(form.getAttribute("data-confirm"))) event.preventDefault();
    });
  });

  // ---------- show / hide password ----------
  document.querySelectorAll("input[type=password]").forEach(function (input) {
    if (input.getAttribute("data-toggle-ready")) return;
    input.setAttribute("data-toggle-ready", "1");
    var wrap = document.createElement("div");
    wrap.className = "pw-wrap";
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "pw-toggle";
    btn.textContent = "Show";
    btn.setAttribute("aria-label", "Show password");
    btn.setAttribute("aria-pressed", "false");
    btn.addEventListener("click", function () {
      var reveal = input.type === "password";
      input.type = reveal ? "text" : "password";
      input.classList.toggle("pw-revealed", reveal);
      btn.textContent = reveal ? "Hide" : "Show";
      btn.setAttribute("aria-label", reveal ? "Hide password" : "Show password");
      btn.setAttribute("aria-pressed", String(reveal));
      input.focus();
    });
    wrap.appendChild(btn);
  });

  // ---------- password strength meter ----------
  function scorePassword(p) {
    var score = 0;
    if (p.length >= 8) score++;
    if (p.length >= 12) score++;
    if (/[a-z]/.test(p) && /[A-Z]/.test(p)) score++;
    if (/\d/.test(p)) score++;
    if (/[^A-Za-z0-9]/.test(p)) score++;
    return Math.min(score, 4);
  }
  var labels = ["Too short", "Weak", "Fair", "Good", "Strong"];
  var colours = ["#CBD5E1", "#C8102E", "#F59E0B", "#0F9D8F", "#15803D"];
  document.querySelectorAll("input[data-password-meter]").forEach(function (input) {
    var group = input.closest(".form-group");
    var bar = group && group.querySelector("[data-meter-bar]");
    var text = group && group.querySelector("[data-meter-text]");
    input.addEventListener("input", function () {
      var value = input.value;
      var score = value.length ? scorePassword(value) : 0;
      if (!value.length) score = 0;
      if (bar) { bar.style.width = (score * 25) + "%"; bar.style.background = colours[score]; }
      if (text) { text.textContent = value.length ? "Strength: " + labels[score] : "Use at least 8 characters, mixing letters, numbers and symbols."; }
    });
  });

  // ---------- booking summary ----------
  var summary = document.querySelector("[data-booking-form]");
  function formatDate(value) {
    if (!value) return "—";
    var d = new Date(value + "T00:00:00");
    if (isNaN(d)) return value;
    return d.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", year: "numeric" });
  }
  function updateSummary() {
    if (!summary) return;
    var doctor = summary.querySelector("input[name=doctor]:checked");
    var setText = function (sel, text) { var el = summary.querySelector(sel); if (el) el.textContent = text; };
    setText("[data-summary-doctor]", doctor ? doctor.getAttribute("data-doctor-name") : "Not selected");
    setText("[data-summary-dept]", doctor ? doctor.getAttribute("data-doctor-dept") : "—");
    var dateInput = summary.querySelector("[data-date]");
    setText("[data-summary-date]", dateInput ? formatDate(dateInput.value) : "—");
    var selected = summary.querySelector(".slot-btn[aria-pressed='true']");
    setText("[data-summary-time]", selected ? selected.textContent : "—");
  }

  // ---------- department filter (booking page) ----------
  document.querySelectorAll("[data-dept-filter]").forEach(function (chip) {
    chip.addEventListener("click", function () {
      var slug = chip.getAttribute("data-dept-filter");
      document.querySelectorAll("[data-dept-filter]").forEach(function (c) { c.classList.toggle("active", c === chip); });
      document.querySelectorAll("[data-doctor-card]").forEach(function (card) {
        card.classList.toggle("hidden", !!slug && card.getAttribute("data-dept") !== slug);
      });
    });
  });

  // ---------- slot picker ----------
  function initSlotPicker(picker) {
    var api = picker.getAttribute("data-api-url");
    var dateInput = picker.querySelector("[data-date]");
    var hidden = picker.querySelector("[data-start]");
    var grid = picker.querySelector("[data-slots]");
    var msg = picker.querySelector("[data-slot-msg]");
    var status = picker.querySelector("[data-slot-status]");
    var excludeRef = picker.getAttribute("data-exclude-ref") || "";
    var radioName = picker.getAttribute("data-doctor-radio");
    var fixedDoctor = picker.getAttribute("data-doctor-id");
    var requestId = 0;

    function doctorId() {
      if (fixedDoctor) return fixedDoctor;
      var checked = document.querySelector("input[name=" + radioName + "]:checked");
      return checked ? checked.value : "";
    }

    function setEmpty(text) {
      grid.innerHTML = "";
      var box = document.createElement("div");
      box.className = "slot-empty";
      box.textContent = text;
      grid.appendChild(box);
    }

    function selectSlot(button, value) {
      grid.querySelectorAll(".slot-btn").forEach(function (b) { b.setAttribute("aria-pressed", "false"); });
      button.setAttribute("aria-pressed", "true");
      hidden.value = value;
      msg.textContent = "";
      updateSummary();
    }

    function render(data, preferred) {
      grid.innerHTML = "";
      msg.textContent = "";
      if (!data.slots || !data.slots.length) {
        setEmpty(data.message || "No free slots on this day.");
        hidden.value = "";
        updateSummary();
        return;
      }
      data.slots.forEach(function (slot) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "slot-btn";
        btn.textContent = slot.label;
        btn.setAttribute("aria-pressed", "false");
        btn.addEventListener("click", function () { selectSlot(btn, slot.value); });
        grid.appendChild(btn);
        if (preferred && slot.value === preferred) selectSlot(btn, slot.value);
      });
      if (!picker.querySelector("[aria-pressed='true']")) { hidden.value = ""; }
      updateSummary();
    }

    function load(preferred) {
      var doc = doctorId();
      var day = dateInput.value;
      if (!doc || !day) {
        setEmpty(doc ? "Choose a date to see free times." : "Choose a doctor to see free times.");
        hidden.value = "";
        updateSummary();
        return;
      }
      var id = ++requestId;
      if (status) status.innerHTML = '<span class="spinner" aria-label="Loading times"></span>';
      var params = new URLSearchParams({ doctor: doc, date: day });
      if (excludeRef) params.set("exclude", excludeRef);
      fetch(api + "?" + params.toString(), { headers: { "Accept": "application/json" }, credentials: "same-origin" })
        .then(function (r) { return r.json().then(function (body) { return { ok: r.ok, body: body }; }); })
        .then(function (res) {
          if (id !== requestId) return;
          if (status) status.textContent = "";
          if (!res.ok) { setEmpty("Please choose a doctor and date."); msg.textContent = res.body.error || ""; return; }
          render(res.body, preferred);
        })
        .catch(function () {
          if (id !== requestId) return;
          if (status) status.textContent = "";
          msg.textContent = "We could not load times. Check your connection and try again.";
        });
    }

    dateInput.addEventListener("change", function () { hidden.value = ""; load(""); });
    if (radioName) {
      document.querySelectorAll("input[name=" + radioName + "]").forEach(function (radio) {
        radio.addEventListener("change", function () { hidden.value = ""; load(""); });
      });
    }
    load(hidden.value);
  }
  document.querySelectorAll("[data-slot-picker]").forEach(initSlotPicker);
  updateSummary();
})();

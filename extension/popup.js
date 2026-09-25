/**
 * popup.js - Secure Extension Popup Logic
 *
 * Security Features:
 *  - Authenticated Backend Communication: Uses X-AFF-KEY header to communicate with localhost.
 *  - Safe DOM Construction: Uses textContent and element nodes instead of raw innerHTML.
 *  - Active Domain Indicator: Displays the current active tab's hostname before autofilling.
 */

const API = "http://127.0.0.1:5000/api";
const AFF_AUTH_KEY = "AFF-SECURE-LOCAL-EXTENSION-KEY-V1";

// ── DOM references ────────────────────────────────────────────────────────────
const tabBtns = document.querySelectorAll(".tab-btn");
const panels  = document.querySelectorAll(".panel");

const statusDot  = document.getElementById("status-dot");
const statusText = document.getElementById("status-text");
const activeSiteText = document.getElementById("active-site-text");

// Fill panel
const fillProfileSelect = document.getElementById("fill-profile-select");
const btnAutofill       = document.getElementById("btn-autofill");
const btnFillLabel      = document.getElementById("btn-fill-label");
const fillSpinner       = document.getElementById("fill-spinner");
const fillStatus        = document.getElementById("fill-status");

// Profiles panel
const profileList       = document.getElementById("profile-list");
const profileEmptyState = document.getElementById("profile-empty-state");

// Add Profile panel
const profileNameInput  = document.getElementById("profile-name");
const uploadZone        = document.getElementById("upload-zone");
const resumeFileInput   = document.getElementById("resume-file-input");
const uploadFilename    = document.getElementById("upload-filename");
const parsedPreview     = document.getElementById("parsed-preview");
const parsedFieldsList  = document.getElementById("parsed-fields-list");
const customFieldsList  = document.getElementById("custom-fields-list");
const btnAddField       = document.getElementById("btn-add-field");
const btnSaveProfile    = document.getElementById("btn-save-profile");
const saveStatus        = document.getElementById("save-status");

// ── State ─────────────────────────────────────────────────────────────────────
let profiles      = [];
let parsedFields  = {};
let customFields  = [];

const MANUAL_FIELD_MAP = {
  full_name:       "f-full-name",
  email:           "f-email",
  phone:           "f-phone",
  address:         "f-address",
  company:         "f-company",
  job_title:       "f-job-title",
  dates:           "f-dates",
  university:      "f-university",
  degree:          "f-degree",
  graduation_date: "f-grad-date",
  school:          "f-school",
  school_year:     "f-school-year",
  languages:       "f-languages",
  language_level:  "f-lang-level",
  linkedin:        "f-linkedin",
  github:          "f-github",
  skills:          "f-skills",
};

// ── Utilities ─────────────────────────────────────────────────────────────────

function showStatus(el, type, msg) {
  el.className = `fill-status ${type}`;
  el.textContent = msg;
  el.style.display = "block";
  if (type === "success") {
    setTimeout(() => { el.style.display = "none"; }, 4000);
  }
}

function setLoading(loading) {
  btnAutofill.disabled = loading || !fillProfileSelect.value;
  btnFillLabel.textContent = loading ? "Filling…" : "Auto Fill This Form";
  fillSpinner.classList.toggle("visible", loading);
}

// ── Tab navigation ────────────────────────────────────────────────────────────
tabBtns.forEach((btn) => {
  btn.addEventListener("click", () => {
    tabBtns.forEach((b) => { b.classList.remove("active"); b.setAttribute("aria-selected", "false"); });
    panels.forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    btn.setAttribute("aria-selected", "true");
    document.getElementById(btn.getAttribute("aria-controls")).classList.add("active");
  });
});

// ── Detect Active Site ────────────────────────────────────────────────────────
async function detectActiveSite() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab && tab.url) {
      if (tab.url.startsWith("file://")) {
        const filename = tab.url.split("/").pop();
        activeSiteText.textContent = `Local File: ${filename || "HTML file"}`;
      } else if (tab.url.startsWith("http://") || tab.url.startsWith("https://")) {
        const urlObj = new URL(tab.url);
        activeSiteText.textContent = `Target Site: ${urlObj.hostname}`;
      } else {
        activeSiteText.textContent = `Page: ${tab.title || "active tab"}`;
      }
      return;
    }
  } catch {}
  activeSiteText.textContent = "Target: Current active tab";
}

// ── Backend health check ──────────────────────────────────────────────────────
async function checkHealth() {
  try {
    const res = await fetch(`${API}/health`, { signal: AbortSignal.timeout(2000) });
    if (res.ok) {
      statusDot.classList.add("online");
      statusText.textContent = "Backend secured";
      return true;
    }
  } catch {}
  statusDot.classList.remove("online");
  statusText.textContent = "Backend offline";
  return false;
}

// ── Profile loading ───────────────────────────────────────────────────────────
async function loadProfiles() {
  try {
    const res = await fetch(`${API}/profiles`, {
      headers: { "X-AFF-KEY": AFF_AUTH_KEY },
    });
    if (res.ok) {
      profiles = await res.json();
    } else {
      profiles = [];
    }
  } catch {
    profiles = [];
  }
  renderProfileDropdown();
  renderProfileList();
}

function renderProfileDropdown() {
  const current = fillProfileSelect.value;
  fillProfileSelect.innerHTML = "";
  
  const defaultOpt = document.createElement("option");
  defaultOpt.value = "";
  defaultOpt.textContent = "— choose a profile —";
  fillProfileSelect.appendChild(defaultOpt);

  profiles.forEach((p) => {
    const opt = document.createElement("option");
    opt.value = p.id;
    opt.textContent = p.name;
    if (String(p.id) === current) opt.selected = true;
    fillProfileSelect.appendChild(opt);
  });
  btnAutofill.disabled = !fillProfileSelect.value;
}

// Safe DOM rendering (prevents XSS)
function renderProfileList() {
  profileList.innerHTML = "";
  if (profiles.length === 0) {
    profileEmptyState.style.display = "block";
    return;
  }
  profileEmptyState.style.display = "none";

  profiles.forEach((p) => {
    const date = new Date(p.updated_at).toLocaleDateString("en-IN", {
      day: "numeric", month: "short", year: "numeric",
    });

    const item = document.createElement("div");
    item.className = "profile-item";

    const info = document.createElement("div");
    info.className = "profile-item-info";

    const nameEl = document.createElement("div");
    nameEl.className = "profile-name";
    nameEl.textContent = p.name;

    const metaEl = document.createElement("div");
    metaEl.className = "profile-meta";
    metaEl.textContent = `Updated ${date}`;

    info.appendChild(nameEl);
    info.appendChild(metaEl);

    const actions = document.createElement("div");
    actions.className = "profile-item-actions";

    const useBtn = document.createElement("button");
    useBtn.className = "btn btn-outline btn-sm";
    useBtn.textContent = "Use";
    useBtn.addEventListener("click", () => {
      fillProfileSelect.value = p.id;
      btnAutofill.disabled = false;
      document.getElementById("tab-fill").click();
    });

    const delBtn = document.createElement("button");
    delBtn.className = "btn btn-danger btn-sm";
    delBtn.textContent = "Delete";
    delBtn.addEventListener("click", async () => {
      if (!confirm(`Delete profile "${p.name}"?`)) return;
      await fetch(`${API}/profiles/${p.id}`, {
        method: "DELETE",
        headers: { "X-AFF-KEY": AFF_AUTH_KEY },
      });
      await loadProfiles();
    });

    actions.appendChild(useBtn);
    actions.appendChild(delBtn);

    item.appendChild(info);
    item.appendChild(actions);
    profileList.appendChild(item);
  });
}

fillProfileSelect.addEventListener("change", () => {
  btnAutofill.disabled = !fillProfileSelect.value;
  fillStatus.style.display = "none";
});

// ── Autofill ──────────────────────────────────────────────────────────────────
btnAutofill.addEventListener("click", async () => {
  const profileId = parseInt(fillProfileSelect.value);
  if (!profileId) return;

  setLoading(true);
  fillStatus.style.display = "none";

  try {
    const response = await chrome.runtime.sendMessage({
      type: "TRIGGER_AUTOFILL",
      profileId,
    });
    if (response && response.success) {
      const count = response.result?.filledCount ?? "some";
      showStatus(fillStatus, "success", `✓ Safely filled ${count} field${count !== 1 ? "s" : ""}!`);
    } else {
      showStatus(fillStatus, "error", response?.error || "Failed to fill form.");
    }
  } catch (err) {
    showStatus(fillStatus, "error", err.message || "Unexpected error.");
  } finally {
    setLoading(false);
  }
});

// ── Resume upload ─────────────────────────────────────────────────────────────
uploadZone.addEventListener("click", () => resumeFileInput.click());
uploadZone.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") resumeFileInput.click(); });

uploadZone.addEventListener("dragover", (e) => { e.preventDefault(); uploadZone.classList.add("drag-over"); });
uploadZone.addEventListener("dragleave", () => uploadZone.classList.remove("drag-over"));
uploadZone.addEventListener("drop", (e) => {
  e.preventDefault();
  uploadZone.classList.remove("drag-over");
  const file = e.dataTransfer.files[0];
  if (file) handleResumeFile(file);
});

resumeFileInput.addEventListener("change", () => {
  const file = resumeFileInput.files[0];
  if (file) handleResumeFile(file);
});

async function handleResumeFile(file) {
  if (file.size > 10 * 1024 * 1024) {
    showStatus(saveStatus, "error", "File exceeds 10MB limit.");
    return;
  }

  uploadFilename.textContent = file.name;
  parsedPreview.classList.remove("visible");
  parsedFields = {};

  const formData = new FormData();
  formData.append("resume", file);
  formData.append("name", (profileNameInput.value.trim()) || file.name.replace(/\.[^.]+$/, ""));

  try {
    const res = await fetch(`${API}/profiles/upload-resume`, {
      method: "POST",
      headers: { "X-AFF-KEY": AFF_AUTH_KEY },
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `Upload error (${res.status})`);
    }
    const data = await res.json();
    parsedFields = data.fields || {};
    renderParsedPreview();
    prefillManualFieldsFromParsed();
    await loadProfiles();
    showStatus(saveStatus, "success", `Parsed ${Object.keys(parsedFields).length} fields & safely saved!`);
  } catch (err) {
    showStatus(saveStatus, "error", "Resume error: " + err.message);
  }
}

function renderParsedPreview() {
  parsedFieldsList.innerHTML = "";
  const entries = Object.entries(parsedFields);
  if (entries.length === 0) {
    parsedPreview.classList.remove("visible");
    return;
  }
  parsedPreview.classList.add("visible");

  entries.forEach(([k, v]) => {
    if (!v) return;
    const row = document.createElement("div");
    row.className = "parsed-field-row";

    const keySpan = document.createElement("span");
    keySpan.className = "parsed-field-key";
    keySpan.textContent = k.replace(/_/g, " ");

    const valSpan = document.createElement("span");
    valSpan.className = "parsed-field-val";
    valSpan.textContent = String(v);

    row.appendChild(keySpan);
    row.appendChild(valSpan);
    parsedFieldsList.appendChild(row);
  });
}

function prefillManualFieldsFromParsed() {
  for (const [key, elId] of Object.entries(MANUAL_FIELD_MAP)) {
    if (parsedFields[key]) {
      const el = document.getElementById(elId);
      if (el) el.value = parsedFields[key];
    }
  }
}

// ── Custom fields ─────────────────────────────────────────────────────────────
btnAddField.addEventListener("click", () => {
  addCustomFieldRow();
});

function addCustomFieldRow(key = "", value = "") {
  const idx = customFields.length;
  customFields.push({ key, value });

  const row = document.createElement("div");
  row.className = "custom-field-row";
  row.dataset.idx = idx;

  const keyInput = document.createElement("input");
  keyInput.className = "form-input";
  keyInput.type = "text";
  keyInput.placeholder = "Field name";
  keyInput.value = key;

  const valInput = document.createElement("input");
  valInput.className = "form-input";
  valInput.type = "text";
  valInput.placeholder = "Value";
  valInput.value = value;

  const removeBtn = document.createElement("button");
  removeBtn.className = "btn-remove-field";
  removeBtn.type = "button";
  removeBtn.textContent = "✕";

  keyInput.addEventListener("input",   () => { customFields[idx].key   = keyInput.value; });
  valInput.addEventListener("input",   () => { customFields[idx].value = valInput.value; });
  removeBtn.addEventListener("click",  () => { row.remove(); customFields.splice(idx, 1); });

  row.appendChild(keyInput);
  row.appendChild(valInput);
  row.appendChild(removeBtn);
  customFieldsList.appendChild(row);
}

// ── Save profile (manual) ─────────────────────────────────────────────────────
btnSaveProfile.addEventListener("click", async () => {
  const name = profileNameInput.value.trim();
  if (!name) {
    showStatus(saveStatus, "error", "Please enter a profile name.");
    profileNameInput.focus();
    return;
  }

  const fields = { ...parsedFields };
  for (const [key, elId] of Object.entries(MANUAL_FIELD_MAP)) {
    const val = (document.getElementById(elId)?.value || "").trim();
    if (val) fields[key] = val;
  }

  if (fields.full_name) {
    const parts = fields.full_name.split(/\s+/);
    fields.first_name = parts[0] || "";
    fields.last_name  = parts.slice(1).join(" ") || "";
  }

  customFields.forEach(({ key, value }) => {
    if (key.trim()) fields[key.trim()] = value;
  });

  if (Object.keys(fields).length === 0) {
    showStatus(saveStatus, "error", "Please enter at least one field or upload a resume.");
    return;
  }

  btnSaveProfile.disabled = true;
  try {
    const res = await fetch(`${API}/profiles`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-AFF-KEY": AFF_AUTH_KEY,
      },
      body: JSON.stringify({ name, fields }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Save failed");
    }
    showStatus(saveStatus, "success", `Profile "${name}" saved securely!`);
    await loadProfiles();
  } catch (err) {
    showStatus(saveStatus, "error", err.message);
  } finally {
    btnSaveProfile.disabled = false;
  }
});

// ── Init ──────────────────────────────────────────────────────────────────────
(async () => {
  await detectActiveSite();
  await checkHealth();
  await loadProfiles();
})();

/**
 * content.js - Hardened Content Script for AutoFormFiller
 *
 * Security Features:
 *  - Strict Honeypot & Invisible Field Protection: Verifies bounding box dimensions,
 *    opacity, visibility, and off-screen coordinates to prevent rogue sites from stealing
 *    sensitive user data through hidden inputs.
 *  - Sanitized Field Extraction: Never captures or populates password or hidden fields.
 *  - Safe DOM Native Events: Dispatches real browser events (input, change) so SPA frameworks
 *    (React, Vue, Angular) register changes naturally.
 */

// ── Strict Visibility & Anti-Honeypot Filter ──────────────────────────────────

function isSecurelyVisible(el) {
  if (!el) return false;

  // Never autofill password fields or hidden fields
  const type = (el.type || "").toLowerCase();
  if (type === "password" || type === "hidden" || type === "submit" || type === "button" || type === "file") {
    return false;
  }

  // Check CSS styles
  const style = window.getComputedStyle(el);
  if (
    style.display === "none" ||
    style.visibility === "hidden" ||
    parseFloat(style.opacity || "1") < 0.1 ||
    style.pointerEvents === "none"
  ) {
    return false;
  }

  // Check accessibility hidden attribute
  if (el.getAttribute("aria-hidden") === "true") {
    return false;
  }

  // Check element layout dimensions (prevents 0x0 or 1x1 honeypot traps)
  const rect = el.getBoundingClientRect();
  if (rect.width < 10 || rect.height < 10) {
    return false;
  }

  // Check if positioned way off-screen (classic CSS data exfiltration trap)
  if (rect.right < -100 || rect.bottom < -100 || rect.left > window.innerWidth + 5000 || rect.top > window.innerHeight + 25000) {
    return false;
  }

  // Check CSS clip-path or clip
  if (style.clip === "rect(0px, 0px, 0px, 0px)" || style.clipPath === "inset(50%)") {
    return false;
  }

  return true;
}

// ── Field Detection ───────────────────────────────────────────────────────────

function collectFormFields() {
  const selectors = [
    'input:not([type="hidden"]):not([type="password"]):not([type="submit"]):not([type="button"]):not([type="reset"]):not([type="file"]):not([type="image"])',
    "textarea",
    "select",
  ].join(",");

  const elements = Array.from(document.querySelectorAll(selectors));
  const fields = [];

  for (let i = 0; i < elements.length; i++) {
    const el = elements[i];

    // Security check: Must pass anti-honeypot verification
    if (!isSecurelyVisible(el)) {
      continue;
    }

    // Resolve associated label text safely
    let labelText = "";
    if (el.id) {
      const labelEl = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (labelEl) labelText = labelEl.innerText.trim();
    }
    if (!labelText && el.closest("label")) {
      labelText = el.closest("label").innerText.trim();
    }
    if (!labelText && el.parentElement) {
      const prev = el.previousElementSibling;
      if (prev && (prev.tagName === "LABEL" || prev.tagName === "SPAN" || prev.tagName === "P")) {
        labelText = prev.innerText.trim();
      }
    }

    const uid = el.id || el.name || `aff_field_${i}`;

    fields.push({
      uid: uid,
      id: el.id || "",
      name: el.name || "",
      type: el.type || el.tagName.toLowerCase(),
      placeholder: el.placeholder || "",
      label: labelText.substring(0, 100),
      aria_label: (el.getAttribute("aria-label") || "").substring(0, 100),
      value: (el.value || "").substring(0, 200),
    });
  }

  return fields;
}

// ── Field Filling ─────────────────────────────────────────────────────────────

function fillFields(fillMap) {
  let count = 0;
  const selectors = [
    'input:not([type="hidden"]):not([type="password"]):not([type="submit"]):not([type="button"]):not([type="reset"]):not([type="file"])',
    "textarea",
    "select",
  ].join(",");

  const elements = Array.from(document.querySelectorAll(selectors));

  for (let i = 0; i < elements.length; i++) {
    const el = elements[i];

    // Re-verify visibility before writing data (prevents race-condition DOM traps)
    if (!isSecurelyVisible(el)) {
      continue;
    }

    const uid = el.id || el.name || `aff_field_${i}`;

    let val = undefined;
    if (el.id && fillMap.hasOwnProperty(el.id)) {
      val = fillMap[el.id];
    } else if (el.name && fillMap.hasOwnProperty(el.name)) {
      val = fillMap[el.name];
    } else if (fillMap.hasOwnProperty(uid)) {
      val = fillMap[uid];
    }

    if (val !== undefined && val !== null && val !== "") {
      setNativeValue(el, val);
      count++;
    }
  }

  showFillBanner(count);
  return count;
}

function setNativeValue(el, value) {
  const tag = el.tagName.toLowerCase();

  if (tag === "select") {
    const lowerVal = String(value).toLowerCase();
    let matched = false;
    for (let opt of el.options) {
      if (
        opt.value.toLowerCase() === lowerVal ||
        opt.text.toLowerCase().includes(lowerVal) ||
        lowerVal.includes(opt.text.toLowerCase())
      ) {
        el.value = opt.value;
        matched = true;
        break;
      }
    }
    if (!matched && el.options.length > 1) {
      el.selectedIndex = 1;
    }
  } else if (el.type === "checkbox" || el.type === "radio") {
    el.checked = true;
  } else {
    const nativeSetter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      "value"
    );
    if (nativeSetter && el.tagName === "INPUT") {
      nativeSetter.set.call(el, value);
    } else {
      el.value = value;
    }
  }

  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));

  // Visual highlight animation
  el.style.transition = "box-shadow 0.3s ease, border-color 0.3s ease";
  el.style.boxShadow = "0 0 0 3px rgba(13, 148, 136, 0.45)";
  el.style.borderColor = "#0D9488";
  setTimeout(() => {
    el.style.boxShadow = "";
    el.style.borderColor = "";
    el.style.transition = "";
  }, 2200);
}

// ── Notification Banner (Safe DOM creation) ───────────────────────────────────

function showFillBanner(count) {
  const existing = document.getElementById("aff-fill-banner");
  if (existing) existing.remove();

  const banner = document.createElement("div");
  banner.id = "aff-fill-banner";
  banner.style.cssText = `
    position: fixed;
    top: 16px;
    right: 16px;
    z-index: 2147483647;
    background: #0D9488;
    color: #ffffff;
    font-family: 'Inter', system-ui, sans-serif;
    font-size: 14px;
    font-weight: 600;
    padding: 12px 20px;
    border-radius: 8px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.35);
    display: flex;
    align-items: center;
    gap: 8px;
    animation: affSlideIn 0.3s cubic-bezier(0.34,1.56,0.64,1) forwards;
  `;

  if (!document.getElementById("aff-banner-anim")) {
    const style = document.createElement("style");
    style.id = "aff-banner-anim";
    style.textContent = `
      @keyframes affSlideIn {
        from { transform: translateX(120%); opacity: 0; }
        to   { transform: translateX(0);    opacity: 1; }
      }
    `;
    document.head.appendChild(style);
  }

  const textNode = document.createTextNode(
    `AutoFormFiller: safely filled ${count} field${count !== 1 ? "s" : ""}`
  );
  banner.appendChild(textNode);
  document.body.appendChild(banner);

  setTimeout(() => {
    banner.style.transition = "opacity 0.4s ease";
    banner.style.opacity = "0";
    setTimeout(() => banner.remove(), 400);
  }, 3500);
}

// ── Message Listener ──────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "GET_FORM_FIELDS") {
    const fields = collectFormFields();
    sendResponse({ fields });
    return false;
  }

  if (message.type === "FILL_FIELDS") {
    const count = fillFields(message.fillMap);
    sendResponse({ filledCount: count });
    return false;
  }
});

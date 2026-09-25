/**
 * background.js - Secure Service Worker for AutoFormFiller (Manifest V3)
 *
 * Responsibilities:
 *  - Relays autofill requests from popup → content script → backend API.
 *  - Uses X-AFF-KEY authentication header to communicate securely with localhost.
 *  - Uses activeTab injection for on-demand DOM access.
 */

const API_BASE = "http://127.0.0.1:5000/api";
const AFF_AUTH_KEY = "AFF-SECURE-LOCAL-EXTENSION-KEY-V1";

// ── Message handler ───────────────────────────────────────────────────────────
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "TRIGGER_AUTOFILL") {
    handleAutofill(message.profileId)
      .then((result) => sendResponse({ success: true, result }))
      .catch((err) => sendResponse({ success: false, error: err.message }));
    return true; // keep channel open for async response
  }

  if (message.type === "SET_ACTIVE_PROFILE") {
    chrome.storage.local.set({ activeProfileId: message.profileId });
    sendResponse({ success: true });
    return false;
  }

  if (message.type === "GET_ACTIVE_PROFILE") {
    chrome.storage.local.get("activeProfileId", (data) => {
      sendResponse({ profileId: data.activeProfileId || null });
    });
    return true;
  }
});

// ── Autofill orchestration ────────────────────────────────────────────────────
async function handleAutofill(profileId) {
  // 1. Get current active tab
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.id) {
    throw new Error("No active tab detected.");
  }

  // Prevent running on restricted internal URLs (chrome://, about:, edge://)
  if (tab.url && (tab.url.startsWith("chrome://") || tab.url.startsWith("edge://") || tab.url.startsWith("about:"))) {
    throw new Error("Browser security prevents running autofill on internal browser pages.");
  }

  // 2. Ensure content script is injected on active tab
  let descriptors = [];
  try {
    const res = await chrome.tabs.sendMessage(tab.id, { type: "GET_FORM_FIELDS" });
    descriptors = res ? res.fields : [];
  } catch {
    // Inject content.js on demand via activeTab permission
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ["content.js"],
    });
    const res = await chrome.tabs.sendMessage(tab.id, { type: "GET_FORM_FIELDS" });
    descriptors = res ? res.fields : [];
  }

  if (!descriptors || descriptors.length === 0) {
    throw new Error("No fillable, visible form fields detected on this page.");
  }

  // 3. Request matched values from secured backend
  const res = await fetch(`${API_BASE}/autofill`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-AFF-KEY": AFF_AUTH_KEY,
    },
    body: JSON.stringify({ profile_id: profileId, fields: descriptors }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Backend responded with error (${res.status})`);
  }

  const fillMap = await res.json();

  // 4. Send fill command to content script
  const fillResult = await chrome.tabs.sendMessage(tab.id, {
    type: "FILL_FIELDS",
    fillMap,
  });

  return { filledCount: fillResult?.filledCount ?? Object.keys(fillMap).length };
}

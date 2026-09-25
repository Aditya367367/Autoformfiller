# 🚀 AutoFormFiller

**AutoFormFiller** is an intelligent, privacy-first browser extension (Google Chrome, Brave, Microsoft Edge) and local Python/SQLite backend that automatically and securely fills out web forms using details extracted from your resume (PDF, DOCX, TXT) or customized manual profiles.

> 📄 **Official PDF Documentation:** Available at [`AutoFormFiller_Documentation.pdf`](AutoFormFiller_Documentation.pdf) (Complete technical whitepaper, developer manual, and security specification).

---

## 🔒 Built-in Security Architecture

AutoFormFiller incorporates professional cybersecurity defenses against common browser extension & localhost daemon attack vectors:

1. **Anti-CSRF & Localhost Protection (`X-AFF-KEY`)**:
   - The backend validates an authenticated extension security key on every request.
   - CORS is strictly scoped to browser extensions (`chrome-extension://*`) and localhost (no wildcards `*` or `null`).
   - Drive-by web attacks from untrusted websites attempting to read or tamper with your local profile data are immediately blocked by browser CORS preflights.

2. **Anti-Honeypot & Data Harvesting Defense**:
   - `content.js` strictly verifies layout bounding box dimensions (`width >= 10`, `height >= 10`), off-screen coordinate boundaries, opacity, visibility, and CSS clipping before interacting with any input.
   - Prevents malicious pages from using hidden or zero-size inputs to covertly exfiltrate personal data.
   - Never touches or populates `password` or `hidden` inputs.

3. **Principle of Least Privilege in Permissions**:
   - Removed broad `<all_urls>` host permissions from `manifest.json`.
   - Network requests are locked down strictly to `http://127.0.0.1:5000/*`.
   - Relies on Chrome's `activeTab` API to access DOM inputs only on the focused tab when the user explicitly clicks the extension.

4. **Resource & Upload Protection**:
   - 10MB `MAX_CONTENT_LENGTH` enforcement on file uploads prevents memory exhaustion DoS.
   - Filenames are sanitized with `werkzeug.utils.secure_filename`.
   - File extensions are validated against an allowed whitelist (`.pdf`, `.docx`, `.doc`, `.txt`).

5. **Safe DOM Construction**:
   - Extension UI relies on native DOM nodes (`document.createElement`, `textContent`) preventing DOM-based XSS.

---

## 📁 Project Architecture

```
autoformfiller/
├── backend/
│   ├── app.py                      # Hardened Flask REST API server (port 5000)
│   ├── db.py                       # SQLite database interface & migrations
│   ├── resume_parser.py            # Multi-format resume parser (PDF, DOCX, TXT)
│   ├── requirements.txt            # Python backend dependencies
│   └── autoformfiller.db           # SQLite database (auto-created on startup)
├── extension/
│   ├── manifest.json               # Scoped Chrome Manifest V3 configuration
│   ├── popup.html                  # Extension popup user interface with domain badge
│   ├── popup.css                   # Premium Dark Mode styles (Design System)
│   ├── popup.js                    # Secure frontend logic & API bridge
│   ├── content.js                  # In-page DOM form detection & anti-honeypot injector
│   ├── background.js               # Authenticated extension service worker
│   └── icons/                      # Extension icons (16px, 48px, 128px)
├── docs/
│   └── documentation.html          # Source HTML for the PDF documentation
├── AutoFormFiller_Documentation.pdf # Complete PDF Technical Documentation
├── demo_form.html                  # Interactive test form for testing autofill
├── brain.md                        # Task tracker & analysis log
└── README.md                       # Setup, Developer Guide, & Author info
```

---

## 🛠️ Step 1: Backend Setup (Python & venv)

Open your terminal and run the following commands to create a virtual environment and install dependencies:

```bash
# 1. Navigate to the project root directory
cd /home/ADIXPRI/Desktop/autoformfiller

# 2. Create a virtual environment named 'venv'
python3 -m venv venv

# 3. Activate the virtual environment
source venv/bin/activate

# 4. Install backend dependencies
pip install -r backend/requirements.txt
```

---

## ▶️ Step 2: Run the Backend Server

With the virtual environment activated, start the Flask backend:

```bash
# Ensure you are in the project root and venv is active:
python backend/app.py
```

The server will start at:
```
http://127.0.0.1:5000
```
> SQLite database (`backend/autoformfiller.db`) will be automatically initialized on first startup.

To verify the server is running, visit `http://127.0.0.1:5000/api/health` in your browser. It will return `{"status":"ok", "secure": true}`.

---

## 🧩 Step 3: Install the Extension in Your Browser

Works on **Google Chrome**, **Brave**, **Microsoft Edge**, or any Chromium-based browser:

1. Open your browser and navigate to the extensions page:
   - **Chrome**: `chrome://extensions/`
   - **Brave**: `brave://extensions/`
   - **Edge**: `edge://extensions/`
2. Enable **Developer mode** (toggle switch in the top-right corner).
3. Click the **Load unpacked** button.
4. Select the directory:
   ```
   /home/ADIXPRI/Desktop/autoformfiller/extension
   ```
5. The **AutoFormFiller** extension is now installed! Pin it to your browser toolbar for quick access.

---

## 🧪 Step 4: How to Use & Test

### 1. Add User Details (Resume or Manual)
1. Click the **AutoFormFiller** icon in your browser toolbar.
2. Verify the top status shows **"Backend secured"** (green dot).
3. Switch to the **"Add Profile"** tab:
   - **Option A (Resume Upload)**: Drag & drop or click to upload your resume (`.pdf`, `.docx`, or `.txt`). The backend will automatically extract your name, current company, dates, university, degree, school, languages, proficiency levels, and technical skills.
   - **Option B (Manual Entry)**: Enter or edit any details directly and click **"Save Profile"**.
4. Your profile is stored securely in your local SQLite database.

### 2. Auto-Fill a Form
1. Open the included demo test page in your browser:
   - In Chrome, press `Ctrl + O` and open:
     ```
     /home/ADIXPRI/Desktop/autoformfiller/demo_form.html
     ```
   *(or navigate to any web form, job application, or registration page on the internet).*
2. Click the **AutoFormFiller** extension icon.
3. On the **"Fill Form"** tab, notice the active site verification badge showing your target page.
4. Select your profile from the dropdown and click **"Auto Fill This Form"**.
5. All visible, matching inputs will be filled with green highlight animations and a confirmation banner!

---

## 💻 Developer Guide: How to Extend & Add Features

AutoFormFiller is designed with modular abstractions to allow engineers to add new field mappings, custom extractors, and UI components easily.

### 1. Adding New Form Field Mappings
All field-matching keywords are registered in `FIELD_MAPPING` inside [`backend/app.py`](backend/app.py):

```python
# In backend/app.py -> FIELD_MAPPING
FIELD_MAPPING = {
    # Existing fields...
    "salary_expectation": [
        "salary", "expected_salary", "ctc", "expected_ctc", 
        "compensation", "remuneration", "target_pay"
    ],
    "notice_period": [
        "notice_period", "notice", "availability", 
        "joining_time", "start_immediately", "days_notice"
    ],
}
```

### 2. Extending Resume Extraction Logic
To add regex or keyword pattern rules for new sections or fields, update [`backend/resume_parser.py`](backend/resume_parser.py):

```python
# In backend/resume_parser.py -> _extract_fields_from_text()
def _extract_fields_from_text(text: str) -> dict:
    fields = {}
    # ... existing extraction logic ...

    # Example: Custom Notice Period Regex
    notice_match = re.search(r"(\d+)\s*(?:days?|months?)\s*notice", text, re.IGNORECASE)
    if notice_match:
        fields["notice_period"] = notice_match.group(0).strip()

    return fields
```

### 3. Adding Support for Custom Web Components
If a website uses non-standard input tags (such as custom shadow DOM elements or content-editable divs), extend the query selector in [`extension/content.js`](extension/content.js):

```javascript
// In extension/content.js -> collectFormFields()
const selectors = [
  'input:not([type="hidden"]):not([type="password"]):not([type="submit"])',
  'textarea',
  'select',
  'div[contenteditable="true"]', // Custom component support
  'custom-input-tag'
].join(",");
```

---

## 📜 Open Source License (MIT License)

AutoFormFiller is licensed under the permissive **MIT License**:

```
MIT License

Copyright (c) 2026 Aditya Chauhan

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 👨‍💻 Lead Author & Developer Profile

**AutoFormFiller** is architected, developed, and maintained by:

### **Aditya Chauhan**
*Full-Stack Developer | Python · Django · React.js · Next.js · Node.js*

- **Location:** Mumbai, Maharashtra, India
- **Email:** [suryachauhan367367@gmail.com](mailto:suryachauhan367367@gmail.com)
- **Phone:** +91 8369899103
- **LinkedIn:** [linkedin.com/in/aditya-chauhan-1b1a95228](https://linkedin.com/in/aditya-chauhan-1b1a95228)
- **GitHub:** [github.com/Aditya367367](https://github.com/Aditya367367)

---

*Open for pull requests, feature requests, and open-source contributions!*

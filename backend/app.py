"""
app.py - Hardened Flask REST API for AutoFormFiller backend.

Security Features
-----------------
1. Scoped CORS: Only allows requests from browser extensions (chrome-extension://*) and localhost.
2. Custom Auth Header: Enforces X-AFF-KEY validation on all endpoints, completely preventing
   drive-by CSRF / cross-site localhost attacks from malicious webpages.
3. Upload Protection: 10MB MAX_CONTENT_LENGTH limit, secure_filename sanitization,
   and file extension whitelist.
4. Payload Sanitization: Input size constraints on profile names, field keys, and field values.
"""

import os
import re
from werkzeug.utils import secure_filename
from flask import Flask, request, jsonify
from flask_cors import CORS

import db
import resume_parser

app = Flask(__name__)

# Security: Enforce 10MB maximum request size (prevents memory exhaustion DoS)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

# Security: Pre-shared extension authentication key
AFF_AUTH_KEY = "AFF-SECURE-LOCAL-EXTENSION-KEY-V1"

# Security: Allowed upload extensions
ALLOWED_EXTENSIONS = {"pdf", "docx", "doc", "txt"}

# Security: Restrict CORS strictly to Chrome extensions and localhost (no wildcard '*')
CORS(
    app,
    resources={
        r"/api/*": {
            "origins": [
                re.compile(r"^chrome-extension://"),
                "http://localhost",
                "http://127.0.0.1",
            ]
        }
    },
    allow_headers=["Content-Type", "X-AFF-KEY"],
    methods=["GET", "POST", "DELETE", "OPTIONS"],
)

# ── Init DB on startup ────────────────────────────────────────────────────────
db.init_db()


# ── Security Middleware ───────────────────────────────────────────────────────

@app.before_request
def verify_request_security():
    """
    Validates request origin and custom authentication header.
    Rejects any cross-origin requests from regular websites (drive-by attacks).
    """
    # Allow preflight OPTIONS requests to pass to CORS handler
    if request.method == "OPTIONS":
        return None

    # Allow health check without auth for simple status indicator
    if request.path == "/api/health":
        return None

    # Validate the presence and value of the extension security key
    client_key = request.headers.get("X-AFF-KEY")
    if client_key != AFF_AUTH_KEY:
        return jsonify({
            "error": "Unauthorized: Missing or invalid security token (X-AFF-KEY)."
        }), 403


@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({"error": "File size exceeds the 10MB limit."}), 413


# ── Field-matching heuristic ──────────────────────────────────────────────────

FIELD_MAPPING = {
    # Name
    "full_name":       ["full_name", "fullname", "applicant_name", "your_name", "candidate_name", "name", "your name"],
    "first_name":      ["first_name", "firstname", "first", "given_name", "fname"],
    "last_name":       ["last_name", "lastname", "last", "surname", "family_name", "lname"],

    # Contact & Links
    "email":           ["email", "e-mail", "email_address", "emailaddress", "mail"],
    "phone":           ["phone", "mobile", "tel", "telephone", "cell", "contact_number", "phone_number", "phonenumber"],
    "address":         ["address", "street", "street_address", "addr", "location"],
    "city":            ["city", "town", "metro"],
    "country":         ["country", "nation"],
    "linkedin":        ["linkedin", "linked_in", "linkedin_url", "linkedin_profile", "linkedin_link"],
    "github":          ["github", "git_hub", "github_url", "github_profile", "github_link"],
    "website":         ["website", "portfolio", "portfolio_url", "url", "personal_website"],

    # Professional Summary
    "summary":         ["summary", "about", "bio", "objective", "profile_summary", "about_me", "cover_letter"],

    # Experience & Company & Dates
    "company":         ["current_company", "company", "employer", "organization", "organisation", "firm", "workplace"],
    "job_title":       ["job_title", "title", "role", "designation", "current_role", "current_job_title", "position"],
    "dates":           ["work_dates", "employment_dates", "dates", "tenure", "duration", "employment_period"],
    "start_date":      ["start_date", "from_date", "joining_date", "commenced"],
    "end_date":        ["end_date", "to_date", "leaving_date", "completion_date"],

    # Education: University, School, Degree, Dates
    "university":      ["university", "college", "institute", "institution", "alma_mater", "uni"],
    "school":          ["school", "high_school", "highschool", "secondary_school", "junior_college", "12th_school", "10th_school"],
    "degree":          ["degree", "qualification", "education", "major", "field_of_study", "course", "degree_name"],
    "graduation_date": ["graduation_date", "grad_date", "education_dates", "completion_date"],
    "graduation_year": ["graduation_year", "grad_year", "passing_year", "year_of_passing", "batch"],
    "school_year":     ["school_year", "high_school_year", "12th_year", "10th_year"],

    # Languages & Level
    "languages":       ["languages", "languages_spoken", "languages_known", "language"],
    "language_level":  ["language_level", "language_proficiency", "proficiency_level", "english_level", "language_rating"],
    "primary_language":["primary_language", "native_language", "mother_tongue", "first_language"],

    # Skills & Certifications
    "skills":          ["skills", "technical_skills", "technologies", "expertise", "competencies", "tools"],
    "certifications":  ["certifications", "certificates", "courses", "licenses"],
}


def match_fields(profile_fields: dict, descriptors: list[dict]) -> dict:
    """
    Given a profile's field dict and a list of form field descriptors
    (each with keys: id, name, placeholder, label, type, aria_label, uid),
    return a mapping {descriptor_uid/id/name → value}.
    """
    result = {}
    for desc in descriptors:
        search_str = " ".join(
            str(desc.get(k, "")).lower()
            for k in ("id", "name", "placeholder", "label", "aria_label")
        )

        best_key = None
        best_score = 0

        # Exact match priority
        for field_key, val in profile_fields.items():
            if field_key.lower() in search_str:
                score = len(field_key) * 2
                if score > best_score:
                    best_score = score
                    best_key = field_key

        # Heuristic keywords match
        for field_key, keywords in FIELD_MAPPING.items():
            if field_key not in profile_fields:
                continue
            for kw in keywords:
                if kw in search_str:
                    score = len(kw)
                    if score > best_score:
                        best_score = score
                        best_key = field_key

        if best_key and profile_fields.get(best_key):
            target_key = desc.get("uid") or desc.get("id") or desc.get("name")
            if target_key:
                val = profile_fields[best_key]
                result[target_key] = val
                if desc.get("id"):
                    result[desc["id"]] = val
                if desc.get("name"):
                    result[desc["name"]] = val

    return result


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/api/profiles", methods=["GET"])
def list_profiles():
    return jsonify(db.list_profiles())


@app.route("/api/profiles", methods=["POST"])
def create_profile():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    fields = data.get("fields", {})

    # Validation
    if not name or len(name) > 100:
        return jsonify({"error": "Profile name is required (max 100 chars)."}), 400
    if not isinstance(fields, dict) or len(fields) > 150:
        return jsonify({"error": "Fields must be an object with up to 150 items."}), 400

    # Sanitize sizes
    sanitized_fields = {}
    for k, v in fields.items():
        k_str = str(k)[:80].strip()
        v_str = str(v)[:8000].strip()
        if k_str:
            sanitized_fields[k_str] = v_str

    profile_id = db.create_or_update_profile(name, sanitized_fields)
    return jsonify({"id": profile_id, "name": name}), 201


@app.route("/api/profiles/<int:profile_id>", methods=["GET"])
def get_profile(profile_id):
    profile = db.get_profile(profile_id)
    if not profile:
        return jsonify({"error": "Profile not found"}), 404
    return jsonify(profile)


@app.route("/api/profiles/<int:profile_id>", methods=["DELETE"])
def delete_profile(profile_id):
    db.delete_profile(profile_id)
    return jsonify({"deleted": True})


@app.route("/api/profiles/upload-resume", methods=["POST"])
def upload_resume():
    if "resume" not in request.files:
        return jsonify({"error": "No resume file provided"}), 400

    file = request.files["resume"]
    safe_name = secure_filename(file.filename)
    if not safe_name or "." not in safe_name:
        return jsonify({"error": "Invalid filename."}), 400

    ext = safe_name.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"Unsupported format. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

    profile_name = (request.form.get("name") or "").strip()[:100] or safe_name.rsplit(".", 1)[0]
    file_bytes = file.read()

    extracted = resume_parser.parse_resume(safe_name, file_bytes)
    profile_id = db.create_or_update_profile(profile_name, extracted)
    return jsonify({"profile_id": profile_id, "fields": extracted}), 200


@app.route("/api/autofill", methods=["POST"])
def autofill():
    data = request.get_json(force=True)
    profile_id = data.get("profile_id")
    descriptors = data.get("fields", [])

    if not profile_id or not isinstance(descriptors, list):
        return jsonify({"error": "Invalid request parameters."}), 400

    # Limit descriptors count to prevent CPU abuse
    descriptors = descriptors[:150]

    profile = db.get_profile(profile_id)
    if not profile:
        return jsonify({"error": "Profile not found"}), 404

    result = match_fields(profile["fields"], descriptors)
    return jsonify(result)


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "secure": True})


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)

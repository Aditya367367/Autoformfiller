"""
resume_parser.py - Comprehensive resume parser for PDF, DOCX, and TXT files.
Extracts contact info, summary, experience (company, role, dates),
education (degree, university, school, dates, graduation year),
skills, languages, language proficiency levels, and certifications.
"""

import re
import io

# ── Base regex patterns ───────────────────────────────────────────────────────
PATTERNS = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}", re.IGNORECASE),
    "phone": re.compile(r"(?:\+?\d[\d\s\-().]{8,}\d)", re.IGNORECASE),
    "linkedin": re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-]+", re.IGNORECASE),
    "github": re.compile(r"(?:https?://)?(?:www\.)?github\.com/[\w\-]+", re.IGNORECASE),
    "website": re.compile(r"https?://(?:(?!linkedin\.com|github\.com)[^\s])+", re.IGNORECASE),
}

DATE_RANGE_PATTERN = re.compile(
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\d{4})"
    r"\s*(?:–|-|to)\s*"
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\d{4}|Present|Current|Ongoing)",
    re.IGNORECASE
)


def _clean_name(raw: str) -> str:
    parts = raw.split()
    return " ".join(p.capitalize() for p in parts)


def _extract_name_and_header(lines: list[str]) -> dict:
    """Extract name, role headline, and basic location from top lines."""
    info = {}
    candidate_lines = [l.strip() for l in lines[:10] if l.strip()]
    if not candidate_lines:
        return info

    # Line 0 is usually candidate name
    for i, line in enumerate(candidate_lines[:4]):
        if not re.search(r"@|https?://|www\.|\+?\d{4,}", line):
            if len(line.split()) <= 5 and re.match(r"^[A-Za-z\s.\'\-]+$", line):
                info["full_name"] = _clean_name(line)
                name_parts = info["full_name"].split()
                info["first_name"] = name_parts[0]
                info["last_name"] = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
                
                # Check next line for title / headline
                if i + 1 < len(candidate_lines):
                    next_line = candidate_lines[i + 1]
                    if any(kw in next_line.lower() for kw in ["developer", "engineer", "designer", "manager", "architect", "analyst", "lead", "specialist"]) or "|" in next_line:
                        headline = next_line.split("|")[0].strip()
                        info["headline"] = headline
                        info["job_title"] = headline
                break

    return info


def _segment_sections(text: str) -> dict[str, str]:
    """Split resume text into sections using common resume header keywords."""
    section_keywords = [
        "SUMMARY", "PROFESSIONAL SUMMARY", "ABOUT ME", "OBJECTIVE",
        "EXPERIENCE", "WORK EXPERIENCE", "EMPLOYMENT HISTORY", "PROFESSIONAL EXPERIENCE",
        "PROJECTS", "PERSONAL PROJECTS", "KEY PROJECTS",
        "TECHNICAL SKILLS", "SKILLS", "CORE COMPETENCIES", "TECHNOLOGIES",
        "EDUCATION", "ACADEMIC BACKGROUND", "QUALIFICATIONS",
        "CERTIFICATIONS & LANGUAGES", "CERTIFICATIONS", "LICENSES & CERTIFICATIONS",
        "LANGUAGES", "LANGUAGES & PROFICIENCY"
    ]

    pattern = re.compile(
        r"^[ \t]*(" + "|".join(re.escape(k) for k in section_keywords) + r")[ \t]*$",
        re.MULTILINE | re.IGNORECASE
    )

    matches = list(pattern.finditer(text))
    sections = {}
    if not matches:
        return sections

    for i, match in enumerate(matches):
        sec_name = match.group(1).strip().upper()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[sec_name] = text[start:end].strip()

    return sections


def _extract_fields_from_text(text: str) -> dict:
    """Extract comprehensive structured fields from raw text."""
    fields = {}
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # 1. Header (Name, First/Last Name, Headline)
    header_info = _extract_name_and_header(lines)
    fields.update(header_info)

    # 2. Contact details via regex
    for key, pattern in PATTERNS.items():
        match = pattern.search(text)
        if match:
            val = match.group(0).strip()
            if key in ("linkedin", "github") and not val.startswith("http"):
                val = "https://" + val
            fields[key] = val

    # 3. Location / City / Country detection
    # Example: Mumbai, India | +91... or New York, NY
    loc_match = re.search(r"^([A-Za-z\s]+),\s*([A-Za-z\s]+)\s*\|", text, re.MULTILINE)
    if loc_match:
        city = loc_match.group(1).strip()
        country = loc_match.group(2).strip()
        fields["city"] = city
        fields["country"] = country
        fields["address"] = f"{city}, {country}"
    else:
        # Fallback address heuristic
        for line in lines[:8]:
            if "," in line and any(c in line.lower() for c in ["india", "usa", "uk", "canada", "remote", "mumbai", "delhi", "bangalore", "london"]):
                cleaned = line.split("|")[0].strip()
                fields["address"] = cleaned
                if "," in cleaned:
                    parts = cleaned.split(",")
                    fields["city"] = parts[0].strip()
                    fields["country"] = parts[-1].strip()
                break

    # 4. Parse Sections
    sections = _segment_sections(text)

    # Summary section
    summary_key = next((k for k in sections if "SUMMARY" in k or "ABOUT" in k or "OBJECTIVE" in k), None)
    if summary_key:
        fields["summary"] = " ".join(sections[summary_key].split())

    # 5. Experience Section: Company, Dates, Role
    exp_key = next((k for k in sections if "EXPERIENCE" in k or "EMPLOYMENT" in k), None)
    if exp_key:
        exp_text = sections[exp_key]
        exp_entries = []
        for line in exp_text.splitlines():
            line_s = line.strip()
            dm = DATE_RANGE_PATTERN.search(line_s)
            if dm and any(sep in line_s for sep in ["—", " - ", " at ", "|"]):
                exp_entries.append((line_s, dm))

        if exp_entries:
            # Most recent / Current job
            first_line, dm = exp_entries[0]
            dates_str = dm.group(0).strip()
            fields["dates"] = dates_str
            fields["experience_dates"] = dates_str
            fields["work_dates"] = dates_str
            fields["start_date"] = dm.group(1).strip()
            fields["end_date"] = dm.group(2).strip()

            before_date = first_line[:dm.start()].strip()
            # Split role and company by em-dash or separator
            sep = "—" if "—" in before_date else (" - " if " - " in before_date else (" at " if " at " in before_date else None))
            if sep:
                parts = before_date.split(sep, 1)
                role = parts[0].strip()
                company = parts[1].strip()
                fields["job_title"] = role
                fields["current_job_title"] = role
                fields["company"] = company
                fields["current_company"] = company
            else:
                fields["company"] = before_date
                fields["current_company"] = before_date

            # Previous company if available
            if len(exp_entries) > 1:
                prev_line, prev_dm = exp_entries[1]
                before_prev = prev_line[:prev_dm.start()].strip()
                prev_sep = "—" if "—" in before_prev else (" - " if " - " in before_prev else (" at " if " at " in before_prev else None))
                if prev_sep:
                    parts = before_prev.split(prev_sep, 1)
                    fields["previous_job_title"] = parts[0].strip()
                    fields["previous_company"] = parts[1].strip()

    # 6. Education Section: Degree, University, School, Dates, Graduation Year
    edu_key = next((k for k in sections if "EDUCATION" in k or "ACADEMIC" in k or "QUALIFICATION" in k), None)
    if edu_key:
        edu_text = sections[edu_key]
        for line in edu_text.splitlines():
            line_s = line.strip()
            if not line_s:
                continue

            # University / Degree detection (BCA, B.Tech, Master, Bachelor, etc.)
            deg_keywords = ["bachelor", "master", "bca", "mca", "b.tech", "m.tech", "b.sc", "m.sc", "b.e", "btech", "degree", "diploma", "phd"]
            if any(dk in line_s.lower() for dk in deg_keywords):
                # Splits by — or |
                parts = re.split(r"\s*[—|]\s*", line_s)
                if len(parts) >= 2:
                    fields["degree"] = parts[0].strip()
                    fields["education"] = parts[0].strip()
                    fields["university"] = parts[1].strip()
                    fields["college"] = parts[1].strip()
                if len(parts) >= 3:
                    fields["graduation_date"] = parts[2].strip()
                    fields["education_dates"] = parts[2].strip()
                    # Find all 4-digit years in date string, last is graduation year
                    all_years = re.findall(r"\b(19\d\d|20\d\d)\b", parts[2])
                    if all_years:
                        fields["graduation_year"] = all_years[-1]
                elif len(parts) == 2:
                    all_years = re.findall(r"\b(19\d\d|20\d\d)\b", line_s)
                    if all_years:
                        fields["graduation_year"] = all_years[-1]

            # High School / School detection (HSC, SSC, School, College, 12th, 10th)
            school_keywords = ["hsc", "ssc", "school", "junior college", "12th", "10th", "high school", "cbse", "icse"]
            if any(sk in line_s.lower() for sk in school_keywords):
                # Look for school / college name
                sch_m = re.search(r"(?:HSC[^\,]*\,)?\s*([A-Za-z0-9\s]+(?:College|School|Vidya[a-z]*|Kandivali|Academy)[^\—\-|]*)", line_s, re.I)
                if sch_m:
                    fields["school"] = sch_m.group(1).strip()
                    fields["high_school"] = fields["school"]
                else:
                    parts = re.split(r"\s*[—|]\s*", line_s)
                    if parts:
                        fields["school"] = parts[0].strip()
                        fields["high_school"] = parts[0].strip()

                # School year
                sch_years = re.findall(r"\b(19\d\d|20\d\d)\b", line_s)
                if sch_years:
                    fields["school_year"] = sch_years[0]

                # Secondary school if SSC present
                if "ssc" in line_s.lower() and "|" in line_s:
                    ssc_part = line_s.split("|")[-1].strip()
                    fields["secondary_school"] = ssc_part

    # 7. Technical Skills Section
    skills_key = next((k for k in sections if "SKILL" in k or "COMPETENC" in k or "TECHNOLOG" in k), None)
    if skills_key:
        skills_text = sections[skills_key]
        all_skills = []
        for line in skills_text.splitlines():
            line_s = line.strip()
            if ":" in line_s:
                cat, items = line_s.split(":", 1)
                cat_clean = cat.strip().lower().replace(" ", "_").replace("&", "and")
                fields[f"skills_{cat_clean}"] = items.strip()
                all_skills.extend([s.strip() for s in items.split(",") if s.strip()])
            elif line_s:
                all_skills.extend([s.strip() for s in line_s.split(",") if s.strip()])
        if all_skills:
            fields["skills"] = ", ".join(all_skills)
            fields["technical_skills"] = fields["skills"]

    # 8. Languages & Language Level
    # Look in CERTIFICATIONS & LANGUAGES or LANGUAGES
    lang_key = next((k for k in sections if "LANG" in k), None)
    lang_source = sections.get(lang_key, "") if lang_key else ""
    if not lang_source:
        # Fallback to search in whole text
        lang_source = text

    if "Languages:" in lang_source:
        lang_lines = [l for l in lang_source.splitlines() if "Languages:" in l]
        if lang_lines:
            raw_lang = lang_lines[0].split("Languages:", 1)[1].strip()
            fields["languages"] = raw_lang
            fields["languages_spoken"] = raw_lang

            # Extract individual languages and proficiency levels
            # e.g., "English, Hindi (Fluent), Japanese (Beginner)"
            lang_items = [li.strip() for li in raw_lang.split(",") if li.strip()]
            levels_summary = []
            for i, li in enumerate(lang_items, 1):
                level_m = re.search(r"([A-Za-z\s]+)\s*\(([^)]+)\)", li)
                if level_m:
                    l_name = level_m.group(1).strip()
                    l_level = level_m.group(2).strip()
                else:
                    l_name = li.strip()
                    l_level = "Fluent" if i == 1 else "Conversational"

                fields[f"language_{i}"] = l_name
                fields[f"language_{i}_level"] = l_level
                levels_summary.append(f"{l_name}: {l_level}")

                if i == 1:
                    fields["primary_language"] = l_name
                    fields["primary_language_level"] = l_level
                    fields["language_level"] = l_level

            if levels_summary:
                fields["language_proficiency"] = ", ".join(levels_summary)

    # 9. Certifications
    cert_key = next((k for k in sections if "CERTIF" in k), None)
    cert_source = sections.get(cert_key, "") if cert_key else lang_source
    if "Certifications:" in cert_source:
        cert_lines = [l for l in cert_source.splitlines() if "Certifications:" in l]
        if cert_lines:
            fields["certifications"] = cert_lines[0].split("Certifications:", 1)[1].strip()

    return fields


# ── Public API ────────────────────────────────────────────────────────────────

def parse_pdf(file_bytes: bytes) -> dict:
    """Extract text from a PDF file and return comprehensive structured fields."""
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            pages_text = [page.extract_text() or "" for page in pdf.pages]
        text = "\n".join(pages_text)
    except Exception as e:
        return {"parse_error": str(e)}
    return _extract_fields_from_text(text)


def parse_docx(file_bytes: bytes) -> dict:
    """Extract text from a DOCX file and return comprehensive structured fields."""
    try:
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        paragraphs = [p.text for p in doc.paragraphs]
        text = "\n".join(paragraphs)
    except Exception as e:
        return {"parse_error": str(e)}
    return _extract_fields_from_text(text)


def parse_txt(file_bytes: bytes) -> dict:
    """Parse a plain-text resume."""
    try:
        text = file_bytes.decode("utf-8", errors="replace")
    except Exception as e:
        return {"parse_error": str(e)}
    return _extract_fields_from_text(text)


def parse_resume(filename: str, file_bytes: bytes) -> dict:
    """
    Dispatch to the correct parser based on file extension.
    Returns a dict of extracted fields.
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "pdf":
        return parse_pdf(file_bytes)
    elif ext in ("docx", "doc"):
        return parse_docx(file_bytes)
    else:
        return parse_txt(file_bytes)

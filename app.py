import base64
from html import escape
import os
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import streamlit as st
from google import genai
from google.genai.errors import APIError

from analyze_findings import analyze
from build_evidence import build_evidence
from reporting import generate_pdf_report, report_timestamp


GEMMA_MODEL = "gemma-4-31b-it"
REPOSITORY_PART = re.compile(r"^[A-Za-z0-9_.-]+$")


def normalize_github_url(value):
    parsed = urlsplit(value.strip())
    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or parsed.netloc.lower() != "github.com"
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Enter an HTTPS URL for a public github.com repository.")

    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) != 2:
        raise ValueError("Repository URLs must have the form https://github.com/owner/repository.")

    owner, repository = parts
    if repository.endswith(".git"):
        repository = repository[:-4]
    if (
        not REPOSITORY_PART.fullmatch(owner)
        or not REPOSITORY_PART.fullmatch(repository)
        or owner in {".", ".."}
        or repository in {".", ".."}
    ):
        raise ValueError("The GitHub owner or repository name is invalid.")

    return f"https://github.com/{owner}/{repository}.git"


def clone_repository(repository_url, destination):
    try:
        subprocess.run(
            [
                "git", "clone", "--depth", "1", "--no-tags",
                "--", repository_url, str(destination),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except FileNotFoundError as error:
        raise RuntimeError("Git was not found. Install Git and try again.") from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("Cloning the repository timed out after 3 minutes.") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() or "Git could not clone that repository."
        raise RuntimeError(detail) from error


def get_gemma_suggestions(api_key, evidence, findings):
    if not api_key:
        return (
            "Gemma analysis was not run. Set GEMINI_API_KEY or enter a key "
            "when submitting the repository to request suggestions."
        )

    dependencies = [
        {
            "package": item["package"],
            "declarations": item["declarations"],
        }
        for item in evidence["dependencies"]
    ]
    prompt = (
        "Review this static Python dependency scan. Give concise, actionable "
        "suggestions based only on the supplied data. Do not claim tests ran "
        "or that a version conflict is proven. State uncertainty clearly.\n\n"
        f"Dependencies: {dependencies}\n"
        f"Findings: {findings}"
    )
    try:
        with genai.Client(api_key=api_key) as client:
            response = client.models.generate_content(
                model=GEMMA_MODEL,
                contents=prompt,
            )
    except APIError as error:
        return f"Gemma request failed: {error.message}"

    return response.text or "Gemma returned no suggestion text."


def scan_repository(repository_url, api_key):
    with tempfile.TemporaryDirectory(prefix="dependency-rescue-") as temp_dir:
        checkout = Path(temp_dir) / "repository"
        clone_repository(repository_url, checkout)
        evidence = build_evidence(checkout)

    findings = analyze(evidence)
    evidence["repository_url"] = repository_url
    gemma_suggestions = get_gemma_suggestions(api_key, evidence, findings)
    report = {
        "repository_url": repository_url,
        "generated_at": report_timestamp(),
        "evidence": evidence,
        "findings": findings,
        "gemma_suggestions": gemma_suggestions,
    }
    report["pdf"] = generate_pdf_report(report)
    return report


def render_pdf(pdf_bytes):
    encoded_pdf = base64.b64encode(pdf_bytes).decode("ascii")
    st.components.v1.html(
        f"""
        <iframe
            src="data:application/pdf;base64,{encoded_pdf}"
            width="100%"
            height="900"
            style="border: 1px solid #dbe3ec; border-radius: 12px;"
            title="Dependency Rescue PDF report">
        </iframe>
        """,
        height=920,
        scrolling=False,
    )


def html_table(columns, rows):
    header = "".join(f"<th>{escape(str(column))}</th>" for column in columns)
    body = "".join(
        "<tr>"
        + "".join(
            f"<td>{escape(str(row.get(column, '')))}</td>"
            for column in columns
        )
        + "</tr>"
        for row in rows
    )
    return (
        '<div style="overflow-x:auto"><table style="width:100%;'
        'border-collapse:collapse"><thead><tr>'
        f"{header}"
        '</tr></thead><tbody>'
        f"{body}"
        '</tbody></table></div>'
    )


st.set_page_config(
    page_title="Dependency Rescue",
    page_icon="🧭",
    layout="wide",
)
st.title("Dependency Rescue")
st.write(
    "Scan a public GitHub repository for declared Python dependencies, "
    "static dependency findings, and candidate imports and calls."
)

with st.form("repository_scan"):
    repository_input = st.text_input(
        "Public GitHub repository URL",
        placeholder="https://github.com/owner/repository",
    )
    default_api_key = os.environ.get("GEMINI_API_KEY", "")
    gemma_api_key = st.text_input(
        "Gemma API key (optional)",
        value=default_api_key,
        type="password",
        help="If provided, dependency metadata and findings are sent to Google "
        "Gemini for suggestions. The key is not included in the report.",
    )
    submitted = st.form_submit_button("Scan repository", type="primary")

if submitted:
    try:
        normalized_url = normalize_github_url(repository_input)
    except ValueError as error:
        st.error(str(error))
    else:
        with st.spinner("Cloning and scanning the repository..."):
            try:
                st.session_state["scan_report"] = scan_repository(
                    normalized_url,
                    gemma_api_key.strip(),
                )
            except RuntimeError as error:
                st.session_state.pop("scan_report", None)
                st.error(str(error))
            except (OSError, UnicodeError, ValueError) as error:
                st.session_state.pop("scan_report", None)
                st.error(f"Could not analyze the repository: {error}")

report = st.session_state.get("scan_report")
if report:
    evidence = report["evidence"]
    dependencies = evidence["dependencies"]
    findings = report["findings"]
    st.success(f"Scan complete for {report['repository_url']}")

    metrics = st.columns(3)
    metrics[0].metric("Declared dependencies", len(dependencies))
    metrics[1].metric("Findings to review", len(findings))
    metrics[2].metric("Tests executed", "No")

    st.subheader("Identified dependencies")
    dependency_rows = []
    for dependency in dependencies:
        dependency_rows.append({
            "Package": dependency["package"],
            "Declarations": "; ".join(
                f"{item['requirement']} ({item['source']})"
                for item in dependency["declarations"]
            ),
            "Candidate imports": ", ".join(
                dependency["candidate_import_modules"]
            ) or "None found",
            "Import locations": ", ".join(
                f"{item['file']}:{item['line']}"
                for item in dependency["import_locations"]
            ) or "None found",
            "Candidate calls": ", ".join(
                f"{item['file']}:{item['line']} {item['written_call']}"
                for item in dependency["candidate_calls"]
            ) or "None found",
        })
    if dependency_rows:
            st.markdown(
                html_table(
                    [
                        "Package",
                        "Declarations",
                        "Candidate imports",
                        "Import locations",
                        "Candidate calls",
                    ],
                    dependency_rows,
                ),
                unsafe_allow_html=True,
            )
    else:
        st.info("No supported Python dependency declarations were found.")

    st.subheader("Findings")
    if findings:
        for finding in findings:
            with st.expander(f"{finding['package']} — {finding['status']}"):
                st.write(finding["summary"])
                st.write(f"Marker: {finding['marker'] or 'None'}")
                st.write(f"Limitation: {finding['limitation']}")
                st.markdown(
                    html_table(
                        ["source", "requirement"],
                        finding["declarations"],
                    ),
                    unsafe_allow_html=True,
                )
    else:
        st.info("No differing dependency constraints were identified.")

    st.subheader("Gemma suggestions")
    st.write(report["gemma_suggestions"])

    st.subheader("Dependency diff")
    st.caption("No version changes are proposed yet; this table is intentionally blank.")
    st.markdown(
        html_table(
            ["Package", "Current", "Proposed", "Change"],
            [],
        ),
        unsafe_allow_html=True,
    )

    with st.expander("Analysis limitations"):
        for limitation in evidence["limitations"]:
            st.write(f"- {limitation}")

    st.subheader("PDF report")
    st.download_button(
        "Download PDF report",
        data=report["pdf"],
        file_name="dependency-rescue-report.pdf",
        mime="application/pdf",
    )
    render_pdf(report["pdf"])

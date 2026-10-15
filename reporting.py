from datetime import datetime, timezone
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def generate_pdf_report(report):
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="Dependency Rescue Report",
        author="Dependency Rescue",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReportTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#12304a"),
        spaceAfter=8 * mm,
    ))
    styles.add(ParagraphStyle(
        name="SectionHeading",
        parent=styles["Heading2"],
        textColor=colors.HexColor("#147d76"),
        spaceBefore=5 * mm,
        spaceAfter=2 * mm,
    ))
    body = styles["BodyText"]
    body.leading = 14

    def paragraph(value):
        safe_value = str(value).encode("ascii", "replace").decode("ascii")
        return Paragraph(escape(safe_value).replace("\n", "<br/>"), body)

    story = [
        Paragraph("Dependency Rescue Report", styles["ReportTitle"]),
        paragraph(f"Repository: {report['repository_url']}"),
        paragraph(f"Generated: {report['generated_at']}"),
        paragraph("Analysis type: Static inspection (tests were not run)"),
        Spacer(1, 3 * mm),
        Paragraph("Identified dependencies", styles["SectionHeading"]),
    ]

    dependencies = report["evidence"]["dependencies"]
    if not dependencies:
        story.append(paragraph("No supported dependency declarations were found."))

    for dependency in dependencies:
        story.append(Paragraph(escape(dependency["package"]), styles["Heading3"]))
        declarations = dependency.get("declarations", [])
        story.extend(
            paragraph(
                f"Declared: {item['requirement']} ({item['source']})"
            )
            for item in declarations
        )
        modules = dependency.get("candidate_import_modules", [])
        story.append(paragraph(
            f"Candidate import modules: {', '.join(modules) or 'None found'}"
        ))
        locations = dependency.get("import_locations", [])
        if locations:
            story.append(paragraph("Import locations:"))
            story.extend(
                paragraph(
                    f"{item['file']}:{item['line']} - "
                    f"{item.get('statement') or item.get('local_name', '')}"
                )
                for item in locations
            )
        calls = dependency.get("candidate_calls", [])
        if calls:
            story.append(paragraph("Candidate calls:"))
            story.extend(
                paragraph(
                    f"{item['file']}:{item['line']} - "
                    f"{item['written_call']} -> {item['candidate_target']}"
                )
                for item in calls
            )

    story.append(Paragraph("Findings", styles["SectionHeading"]))
    findings = report["findings"]
    if not findings:
        story.append(paragraph("No differing dependency constraints were identified."))
    for finding in findings:
        story.append(Paragraph(
            escape(f"{finding['package']} - {finding['status']}"),
            styles["Heading3"],
        ))
        story.append(paragraph(finding["summary"]))
        for declaration in finding.get("declarations", []):
            story.append(paragraph(
                f"{declaration['source']} -> {declaration['requirement']}"
            ))
        story.append(paragraph(f"Limitation: {finding['limitation']}"))

    story.append(Paragraph("Gemma suggestions", styles["SectionHeading"]))
    story.append(paragraph(report["gemma_suggestions"]))

    story.append(Paragraph("Dependency diff", styles["SectionHeading"]))
    diff_table = Table(
        [["Package", "Current", "Proposed", "Change"]],
        colWidths=[35 * mm, 38 * mm, 38 * mm, 48 * mm],
    )
    diff_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f2f1")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#12304a")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(diff_table)

    story.append(Paragraph("Analysis limitations", styles["SectionHeading"]))
    for limitation in report["evidence"].get("limitations", []):
        story.append(paragraph(f"- {limitation}"))

    def add_page_number(canvas, _document):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawRightString(
            A4[0] - 18 * mm,
            10 * mm,
            f"Page {canvas.getPageNumber()}",
        )
        canvas.restoreState()

    document.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    return buffer.getvalue()


def report_timestamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

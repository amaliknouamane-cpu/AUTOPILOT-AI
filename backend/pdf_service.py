from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCUMENTS_DIR = PROJECT_ROOT / "documents"


def generate_quote_pdf(quote):
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)

    quote_id = quote["quote_id"]
    filename = f"quotation_{quote_id}.pdf"
    pdf_path = DOCUMENTS_DIR / filename

    document = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("AUTOPILOT AI", styles["Title"]))
    story.append(
        Paragraph("COMMERCIAL QUOTATION", styles["Heading2"])
    )
    story.append(Spacer(1, 8 * mm))

    story.append(Paragraph(
        f"<b>Quotation ID:</b> {quote_id}",
        styles["Normal"],
    ))
    story.append(Paragraph(
        f"<b>Customer:</b> {quote['customer']}",
        styles["Normal"],
    ))
    story.append(Paragraph(
        f"<b>Status:</b> {quote['status']}",
        styles["Normal"],
    ))
    story.append(Spacer(1, 8 * mm))

    table_data = [
        ["Product", "Quantity", "Unit Price (MAD)", "Subtotal (MAD)"]
    ]

    for item in quote["items"]:
        table_data.append([
            item["product_name"],
            str(item["quantity"]),
            f"{item['unit_price']:,.2f}",
            f"{item['subtotal']:,.2f}",
        ])

    table_data.append([
        "",
        "",
        "TOTAL (MAD)",
        f"{quote['total']:,.2f}",
    ])

    table = Table(
        table_data,
        colWidths=[55 * mm, 25 * mm, 40 * mm, 40 * mm],
        repeatRows=1,
    )

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17365D")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("PADDING", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#D9EAF7")),
        ("FONTNAME", (2, -1), (-1, -1), "Helvetica-Bold"),
    ]))

    story.append(table)
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(
        "Thank you for your interest in our products.",
        styles["Normal"],
    ))

    document.build(story)

    return str(pdf_path)

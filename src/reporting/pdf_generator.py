import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import inch

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from .report_styles import (
    title_style,
    subtitle_style,
    heading_style,
    normal_style,
    bullet_style,
    footer_style,
)

def add_page_number(canvas, doc):
    """
    Draw page number on every page.
    """

    canvas.saveState()

    canvas.setFont("Helvetica", 9)

    canvas.setFillColor(colors.grey)

    canvas.drawRightString(
        7.6 * inch,
        0.45 * inch,
        f"Page {canvas.getPageNumber()}",
    )

    canvas.restoreState()

def clean_text(text):

    if not text:
        return ""

    return (
        str(text)
        .replace("**", "")
        .replace("*", "")
        .replace("###", "")
        .replace("\n", " ")
        .strip()
    )
def format_date(date_value):

    try:

        return datetime.fromisoformat(
            str(date_value)
        ).strftime("%d %b %Y • %I:%M %p")

    except Exception:

        return str(date_value)
    
import re

def article_summary(article):

    summary = (
        article.get("summary")
        or article.get("description")
        or article.get("content")
        or ""
    )

    summary = clean_text(summary)

    summary = re.sub(r"\s+", " ", summary)

    summary = re.sub(
        r"([a-z])([A-Z])",
        r"\1 \2",
        summary,
    )

    if len(summary) > 320:
        summary = summary[:320] + "..."

    return summary

def generate_pdf(
    briefing: str,
    articles: list,
    output_path: str,
):
    """
    Generate a professional executive news report.
    """

    # =====================================================
    # Create Output Directory
    # =====================================================

    os.makedirs(
        os.path.dirname(output_path),
        exist_ok=True,
    )

    # =====================================================
    # PDF Document
    # =====================================================

    doc = SimpleDocTemplate(
        output_path,
        leftMargin=40,
        rightMargin=40,
        topMargin=35,
        bottomMargin=35,
    )

    elements = []

    current_datetime = datetime.now()

    # =====================================================
    # Executive Header
    # =====================================================

    header = Table(
        [[
            Paragraph(
                "<font color='white' size='24'><b>📰 NEWS INTELLIGENCE REPORT</b></font>",
                title_style,
            )
        ]],
        colWidths=[520],
    )

    header.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1F4E79")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 20),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 20),
        ])
    )

    elements.append(header)

    elements.append(Spacer(1, 15))

    elements.append(
        Paragraph(
            "Daily Executive Briefing",
            subtitle_style,
        )
    )

    elements.append(
        Paragraph(
            f"<b>Generated On:</b> {current_datetime.strftime('%d %B %Y %I:%M %p')}",
            normal_style,
        )
    )

    elements.append(
        Paragraph(
            "<b>Report Objective:</b> Provide a concise AI-powered executive briefing from multiple trusted news sources.",
            normal_style,
        )
    )

    elements.append(Spacer(1, 20))

    # =====================================================
    # Dashboard Data
    # =====================================================

    sources = sorted(
        {
            article.get("source", "Unknown")
            for article in articles
        }
    )

    topics = sorted(
        {
            article.get("topic", "General")
            for article in articles
        }
    )

    topic_label = "Topic" if len(topics) == 1 else "Topics"

    # =====================================================
    # Executive Dashboard
    # =====================================================

    elements.append(
        Paragraph(
            "EXECUTIVE DASHBOARD",
            heading_style,
        )
    )

    dashboard = Table(
        [[

            Paragraph(
                f"""
                <para align='center'>
                <font color='white' size='28'><b>{len(articles)}</b></font><br/>
                <font color='white' size='10'>Articles</font>
                </para>
                """,
                normal_style,
            ),

            Paragraph(
                f"""
                <para align='center'>
                <font size='28'><b>{len(sources)}</b></font><br/>
                <font size='10'>Sources</font>
                </para>
                """,
                normal_style,
            ),

            Paragraph(
                f"""
                <para align='center'>
                <font size='28'><b>{len(topics)}</b></font><br/>
                <font size='10'>{topic_label}</font>
                </para>
                """,
                normal_style,
            ),

            Paragraph(
                f"""
                <para align='center'>
                <font size='20'><b>{current_datetime.strftime('%d %b')}</b></font><br/>
                <font size='10'>{current_datetime.strftime('%Y')}</font>
                </para>
                """,
                normal_style,
            ),

        ]],
        colWidths=[120, 120, 120, 120],
    )

    dashboard.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#1F4E79")),
            ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#2E75B6")),
            ("BACKGROUND", (2, 0), (2, 0), colors.HexColor("#4F81BD")),
            ("BACKGROUND", (3, 0), (3, 0), colors.HexColor("#5B9BD5")),

            ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),

            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

            ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),

            ("TOPPADDING", (0, 0), (-1, -1), 18),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 18),

            ("GRID", (0, 0), (-1, -1), 1, colors.white),
        ])
    )

    elements.append(dashboard)

    elements.append(Spacer(1, 20))

    # =====================================================
    # Executive Snapshot
    # =====================================================

    elements.append(
        Paragraph(
            "EXECUTIVE SNAPSHOT",
            heading_style,
        )
    )

    snapshot_items = [
        f"• {len(articles)} Articles analyzed",
        f"• {len(sources)} Trusted news sources",
        f"• {len(topics)} {topic_label.lower()} identified",
        "• AI-generated executive summary",
        "• Multi-source news intelligence report",
    ]

    for item in snapshot_items:

        elements.append(
            Paragraph(
                item,
                bullet_style,
            )
        )

    elements.append(Spacer(1, 25))

    # =====================================================
    # Key Highlights
    # =====================================================

    elements.append(
        Paragraph(
            "KEY HIGHLIGHTS",
            heading_style,
        )
    )

    clean_briefing = clean_text(briefing)

    highlight_sentences = []

    for sentence in clean_briefing.split("."):

        sentence = sentence.strip()

        if len(sentence) > 25:
            highlight_sentences.append(sentence)

    if not highlight_sentences:

        highlight_sentences.append(
            "No executive summary was generated."
        )

    for item in highlight_sentences[:6]:

        elements.append(
            Paragraph(
                f"• {item}.",
                bullet_style,
            )
        )

    elements.append(Spacer(1, 20))

    # =====================================================
    # Top Headlines
    # =====================================================

    elements.append(
        Paragraph(
            "TOP HEADLINES",
            heading_style,
        )
    )

    elements.append(
        Paragraph(
            "<font color='#666666'>A quick overview of today's most important stories.</font>",
            normal_style,
        )
    )

    elements.append(Spacer(1, 10))

    headline_count = min(len(articles), 5)

    if headline_count == 0:

        elements.append(
            Paragraph(
                "No headlines available.",
                normal_style,
            )
        )

    else:

        for i, article in enumerate(
            articles[:headline_count],
            start=1,
        ):

            headline = article.get(
                "title",
                "Untitled",
            )

            elements.append(
                Paragraph(
                    f"""
                    <font color='#1F4E79' size='12'>
                        <font color="#1F4E79"><b>{i}.</b></font>
                    </font>

                    <font size='11'>
                        {headline}
                    </font>
                    """,
                    normal_style,
                )
            )

            elements.append(
                Spacer(1, 8)
            )

    elements.append(
        Spacer(1, 15)
    )

    # =====================================================
    # Executive News Analysis
    # =====================================================

    elements.append(
        Paragraph(
            "EXECUTIVE NEWS ANALYSIS",
            heading_style,
        )
    )

    if not articles:

        elements.append(
            Paragraph(
                "No news articles available.",
                normal_style,
            )
        )

    else:

        for index, article in enumerate(
            articles,
            start=1,
        ):

            # ==========================================
            # Extract Article Details
            # ==========================================

            title = article.get(
                "title",
                "Untitled",
            )

            source = article.get(
                "source",
                "Unknown",
            )

            topic = article.get(
                "topic",
                "General",
            )

            author = article.get(
                "author",
                "N/A",
            )

            published = format_date(
                article.get(
                    "published_at",
                    "N/A",
                )
            )

            url = article.get(
                "url",
                "N/A",
            )

            summary = article_summary(article)

            # ==========================================
            # Article Header
            # ==========================================

            card_header = Table(
                [[
                    Paragraph(
                        f"<font color='white' size='13'><b>ARTICLE {index} OF {len(articles)}</b></font>",
                        normal_style,
                    )
                ]],
                colWidths=[520],
            )

            card_header.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1F4E79")),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ])
            )

            elements.append(card_header)
            elements.append(Spacer(1, 12))

            # ==========================================
            # Top Story Badge
            # ==========================================

            if index == 1:

                elements.append(
                    Paragraph(
                        "<font color='#C0392B'><b>★ TOP STORY OF THE DAY</b></font>",
                        heading_style,
                    )
                )

                elements.append(Spacer(1, 5))

            # ==========================================
            # Article Title
            # ==========================================

            elements.append(
                Paragraph(
                    f"<font color='#0B5394' size='20'><b>{clean_text(title)}</b></font>",
                    heading_style,
                )
            )

            elements.append(Spacer(1, 10))

            # ==========================================
            # Metadata Table
            # ==========================================

            metadata = [
                ["Source", source],
                ["Category", topic],
                ["Published", published],
            ]

            if author and author != "N/A":

                metadata.insert(
                    2,
                    ["Author", author],
                )

            metadata_table = Table(
                metadata,
                colWidths=[130, 390],
            )

            metadata_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F4F6F6")),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ])
            )

            elements.append(metadata_table)

            elements.append(Spacer(1, 15))

            # ==========================================
            # Executive Insight
            # ==========================================

            insight_box = Table(
                [[
                    Paragraph(
                        f"""
                        <font color="#1F4E79" size="15">
                        <b>Executive Insight</b>
                        </font>

                        <br/><br/>

                        <font size='11'>
                        {summary}
                        </font>
                        """,
                        normal_style,
                    )
                ]],
                colWidths=[520],
            )

            insight_box.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FCFCFC")),
                    ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#D6EAF8")),
                    ("TOPPADDING", (0, 0), (-1, -1), 16),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
                    ("LEFTPADDING", (0, 0), (-1, -1), 18),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 18),
                ])
            )

            elements.append(insight_box)

            elements.append(Spacer(1, 15))

            # ==========================================
            # Read Full Article Button
            # ==========================================

            if url and url != "N/A":

                button = Table(
                    [[
                        Paragraph(
                            f'<link href="{url}"><font color="white"><b>🌐 OPEN ORIGINAL ARTICLE</b></font></link>',
                            normal_style,
                        )
                    ]],
                    colWidths=[260],
                )

                button.setStyle(
                    TableStyle([
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1565C0")),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ])
                )

                button.hAlign = "CENTER"

                elements.append(Spacer(1, 8))

                elements.append(button)

            elements.append(Spacer(1, 25))

        # =====================================================
        # Disclaimer
        # =====================================================

        elements.append(
            Paragraph(
                "DISCLAIMER",
                heading_style,
            )
        )

        disclaimer = Table(
            [[
                Paragraph(
                    """
                    This report was automatically generated using AI-assisted news
                    analysis from multiple news sources. Readers should refer to
                    the original published articles for complete context and
                    verification.
                    """,
                    normal_style,
                )
            ]],
            colWidths=[520],
        )

        disclaimer.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF8E7")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D4AC0D")),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ("LEFTPADDING", (0, 0), (-1, -1), 15),
                ("RIGHTPADDING", (0, 0), (-1, -1), 15),
            ])
        )

        elements.append(disclaimer)

        elements.append(Spacer(1, 25))

        # =====================================================
        # Footer
        # =====================================================

        footer = Table(
            [[
                Paragraph(
                    f"""
                    <font color='white' size='11'>
                    <b>News Intelligence Briefing Agent</b><br/>
                    Automated Executive Report<br/>
                    Generated on {current_datetime.strftime('%d %B %Y')}<br/>
                    Confidential Internal Report
                    </font>
                    """,
                    footer_style,
                )
            ]],
            colWidths=[520],
        )

        footer.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1F4E79")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ])
        )

        elements.append(footer)

        # =====================================================
        # Build PDF
        # =====================================================

        doc.build(
            elements,
            onFirstPage=add_page_number,
            onLaterPages=add_page_number,
        )

        return output_path
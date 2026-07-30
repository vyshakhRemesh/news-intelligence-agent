from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.colors import HexColor

styles = getSampleStyleSheet()

# -----------------------------
# Report Title
# -----------------------------
title_style = styles["Title"]
title_style.alignment = TA_CENTER
title_style.textColor = HexColor("#1F4E79")
title_style.spaceAfter = 20

# -----------------------------
# Section Heading
# -----------------------------
heading_style = styles["Heading2"]
heading_style.alignment = TA_LEFT
heading_style.textColor = HexColor("#0B5394")
heading_style.spaceBefore = 15
heading_style.spaceAfter = 10

# -----------------------------
# Normal Paragraph
# -----------------------------
normal_style = styles["BodyText"]
normal_style.leading = 20
normal_style.spaceAfter = 10

# -----------------------------
# Footer
# -----------------------------
footer_style = styles["Italic"]
footer_style.alignment = TA_CENTER
footer_style.textColor = HexColor("#666666")
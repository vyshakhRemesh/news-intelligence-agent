from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch

styles = getSampleStyleSheet()

# ==========================================
# Color Palette
# ==========================================

PRIMARY = HexColor("#1F4E79")
SECONDARY = HexColor("#2E75B6")
ACCENT = HexColor("#EAF2F8")
TEXT = HexColor("#333333")
LIGHT = HexColor("#777777")
SUCCESS = HexColor("#2E8B57")

# ==========================================
# Main Report Title
# ==========================================

title_style = styles["Title"]
title_style.alignment = TA_CENTER
title_style.textColor = PRIMARY
title_style.fontName = "Helvetica-Bold"
title_style.fontSize = 24
title_style.leading = 30
title_style.spaceAfter = 6

# ==========================================
# Subtitle
# ==========================================

subtitle_style = styles["Heading3"]
subtitle_style.alignment = TA_CENTER
subtitle_style.textColor = SECONDARY
subtitle_style.fontName = "Helvetica"
subtitle_style.fontSize = 14
subtitle_style.leading = 18
subtitle_style.spaceAfter = 20

# ==========================================
# Section Heading
# ==========================================

heading_style = styles["Heading2"]
heading_style.alignment = TA_LEFT
heading_style.textColor = PRIMARY
heading_style.fontName = "Helvetica-Bold"
heading_style.fontSize = 16
heading_style.leading = 20
heading_style.spaceBefore = 20
heading_style.spaceAfter = 10

# ==========================================
# Normal Text
# ==========================================

normal_style = styles["BodyText"]
normal_style.fontName = "Helvetica"
normal_style.fontSize = 10
normal_style.leading = 18
normal_style.textColor = TEXT
normal_style.spaceAfter = 8

# ==========================================
# Bullet Points
# ==========================================

bullet_style = styles["BodyText"]
bullet_style.fontName = "Helvetica"
bullet_style.fontSize = 11
bullet_style.leading = 18
bullet_style.leftIndent = 18
bullet_style.spaceAfter = 6
bullet_style.textColor = TEXT

# ==========================================
# Small Labels
# ==========================================

label_style = styles["BodyText"]
label_style.fontName = "Helvetica-Bold"
label_style.fontSize = 11
label_style.leading = 16
label_style.textColor = PRIMARY

# ==========================================
# Footer
# ==========================================

footer_style = styles["Italic"]
footer_style.alignment = TA_CENTER
footer_style.fontSize = 9
footer_style.textColor = LIGHT
footer_style.spaceBefore = 20
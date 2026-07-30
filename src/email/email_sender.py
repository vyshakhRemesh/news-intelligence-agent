import os
import smtplib
import logging

from email.message import EmailMessage
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


def send_email(pdf_path: str) -> bool:
    """
    Sends the generated PDF report via email.

    Args:
        pdf_path (str): Path of the generated PDF.

    Returns:
        bool: True if email sent successfully, otherwise False.
    """

    # -----------------------------
    # Read Email Configuration
    # -----------------------------
    email_address = os.getenv("EMAIL_ADDRESS")
    app_password = os.getenv("EMAIL_APP_PASSWORD")
    recipients = os.getenv("EMAIL_RECIPIENTS")

    recipient_list = [
        email.strip()
        for email in recipients.split(",")
    ] if recipients else []

    if not email_address or not app_password or not recipient_list:
        logger.error("Email configuration is missing.")
        return False

    try:

        # -----------------------------
        # Check PDF Exists
        # -----------------------------
        if not os.path.exists(pdf_path):
            logger.error(f"PDF not found: {pdf_path}")
            return False

        logger.info("Creating email message...")

        # -----------------------------
        # Create Email
        # -----------------------------
        message = EmailMessage()

        message["Subject"] = "Daily News Intelligence Report"
        message["From"] = email_address
        message["To"] = ", ".join(recipient_list)

        message.set_content(
            """
Hello,

Please find attached the latest AI-generated News Intelligence Report.

This report contains:
• Executive Summary
• Top News Articles
• Topic Analysis
• Trust Scores

Regards,
News Intelligence Briefing Agent
"""
        )

        logger.info("Attaching PDF report...")

        # -----------------------------
        # Attach PDF
        # -----------------------------
        with open(pdf_path, "rb") as pdf_file:

            message.add_attachment(
                pdf_file.read(),
                maintype="application",
                subtype="pdf",
                filename=os.path.basename(pdf_path),
            )

        logger.info("Connecting to Gmail SMTP server...")

        # -----------------------------
        # Connect to Gmail SMTP
        # -----------------------------
        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:

            smtp.starttls()

            logger.info("Logging into Gmail...")

            smtp.login(
                email_address,
                app_password,
            )

            logger.info("Sending email...")

            smtp.send_message(message)

        logger.info("Email sent successfully.")

        return True

    except Exception as e:

        logger.exception(f"Failed to send email: {e}")

        return False
"""
Sends test-link emails to Stage 1 shortlisted candidates. Lives in
stage1_pretest because sending the test link is the action that CLOSES
Stage 1 and triggers the wait for Stage 2 (test results).
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_test_link_email(
    candidate_email: str, candidate_name: str, email_body_template: str, sender_email: str, app_password: str
) -> bool:
    """
    Sends an automated email to a candidate using the provided template.
    Requires a Gmail account and a 16-character App Password.
    """
    try:
        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = candidate_email
        message["Subject"] = "Next Steps: Coding Assessment Invitation"

        body = email_body_template.replace("{name}", candidate_name)
        message.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, app_password)
        server.send_message(message)
        server.quit()

        return True

    except Exception as e:
        print(f"Failed to send email to {candidate_email}: {e}")
        return False

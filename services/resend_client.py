"""Email delivery via Resend.

Sends the daily call sheet email. Free tier: 100 emails/day.
https://resend.com/
"""

import resend
import config


def send_callsheet_email(html_content: str, subject: str) -> bool:
    """Send the daily call sheet email via Resend.

    Args:
        html_content: Rendered HTML of the call sheet.
        subject: Email subject line.

    Returns:
        True if sent successfully, False otherwise.
    """
    if not config.RESEND_API_KEY:
        print("  RESEND_API_KEY not set in .env")
        print("  Sign up free at https://resend.com/")
        print("  Skipping email — call sheet saved to database only.")
        return False

    if not config.CALLSHEET_TO_EMAIL:
        print("  CALLSHEET_TO_EMAIL not set in .env")
        return False

    resend.api_key = config.RESEND_API_KEY

    from_email = config.CALLSHEET_FROM_EMAIL or "onboarding@resend.dev"

    try:
        resp = resend.Emails.send({
            "from": from_email,
            "to": [config.CALLSHEET_TO_EMAIL],
            "subject": subject,
            "html": html_content,
        })

        if resp and resp.get("id"):
            print(f"  Email sent! (ID: {resp['id']})")
            return True
        else:
            print(f"  Email send failed: {resp}")
            return False

    except Exception as e:
        print(f"  Email error: {e}")
        return False

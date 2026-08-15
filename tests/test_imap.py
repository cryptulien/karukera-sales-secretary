from email.message import EmailMessage

from sales_secretary.imap_poll import message_to_event


def test_message_to_event_plain():
    msg = EmailMessage()
    msg["From"] = "Marie Dupont <marie@dupont.test>"
    msg["To"] = "contact@acme.test"
    msg["Subject"] = "Devis cuisine"
    msg["Message-ID"] = "<abc@dupont.test>"
    msg["Date"] = "Thu, 13 Aug 2026 16:42:00 +0200"
    msg.set_content("Bonjour, je voudrais un devis.")
    event = message_to_event(
        msg.as_bytes(),
        folder="INBOX",
        uidvalidity="99",
        uid="17",
    )
    assert event.id == "imap:INBOX:99:17"
    assert event.kind == "email"
    assert event.payload["from_email"] == "marie@dupont.test"
    assert event.payload["subject"] == "Devis cuisine"
    assert "devis" in event.payload["body"].lower()

from sales_secretary.ringover import call_to_event, extract_transcript


def test_call_to_event_inbound():
    event = call_to_event(
        {
            "call_id": 42,
            "direction": "in",
            "from_number": "0612345678",
            "to_number": "0142000000",
            "start_time": "2026-08-13T14:42:00+00:00",
            "total_duration": 0,
            "answered": False,
            "contact_name": "Marie Dupont",
            "transcription": "Je voudrais un devis cuisine.",
        }
    )
    assert event.id == "ringover:call:42"
    assert event.kind == "call"
    assert event.payload["phone"] == "+33612345678"
    assert event.payload["transcript"] == "Je voudrais un devis cuisine."
    assert event.payload["contact_name"] == "Marie Dupont"


def test_extract_transcript_from_empower_segments():
    text = extract_transcript(
        {
            "empower": {
                "transcription": {
                    "utterances": [
                        {"speaker": "client", "text": "Bonjour"},
                        {"speaker": "agent", "text": "Oui ?"},
                    ]
                }
            }
        }
    )
    assert "Bonjour" in text
    assert "Oui" in text

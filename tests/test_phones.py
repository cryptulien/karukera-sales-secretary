from sales_secretary.phones import normalize_phone, phone_search_tail


def test_normalize_french_local():
    assert normalize_phone("06 12 34 56 78") == "+33612345678"


def test_normalize_french_international():
    assert normalize_phone("+33 6 12 34 56 78") == "+33612345678"


def test_normalize_french_00_prefix():
    assert normalize_phone("0033612345678") == "+33612345678"


def test_normalize_nine_digits():
    assert normalize_phone("612345678") == "+33612345678"


def test_normalize_empty():
    assert normalize_phone("") is None
    assert normalize_phone(None) is None


def test_search_tail():
    assert phone_search_tail("+33612345678") == "612345678"

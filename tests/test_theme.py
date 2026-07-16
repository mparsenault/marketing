import theme


def test_known_company_color():
    assert theme.get_company_color("Elem") == "#7B4FCC"
    assert theme.get_company_color("Qualifab") == "#FDD900"


def test_unknown_company_default_color():
    assert theme.get_company_color("Inconnue") == "#8A96AA"
    assert theme.get_company_color("") == "#8A96AA"


def test_confidential_presentation_when_confidential_with_reason():
    p = theme.get_confidential_presentation(True, "Client sensible")
    assert p["icon"] == "🔒"
    assert p["row_dimmed"] is True
    assert p["tooltip"] == "Client sensible"


def test_confidential_presentation_when_confidential_without_reason():
    p = theme.get_confidential_presentation(True, "")
    assert p["icon"] == "🔒"
    assert p["row_dimmed"] is True
    assert p["tooltip"] == "Projet non-publiable"


def test_confidential_presentation_when_not_confidential():
    p = theme.get_confidential_presentation(False, "ignoré")
    assert p["icon"] == "🔓"
    assert p["row_dimmed"] is False
    assert p["tooltip"] == ""

import pytest

from data_cleaner import rules


def test_squeeze_and_empty_tokens():
    assert rules.squeeze("  Ana  María \t ") == "Ana María"
    assert all(rules.is_empty_token(v) for v in ["N/A", " null ", "-", "Sin dato", "#N/A"])
    assert not rules.is_empty_token("Ana")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("MARIA DE LOS ANGELES", "Maria de los Angeles"),
        ("juan pablo restrepo", "Juan Pablo Restrepo"),
        ("o'brien-pérez", "O'Brien-Pérez"),
        ("McDonald", "McDonald"),  # mixed case is left alone
        ("DE LA CRUZ", "De la Cruz"),  # a particle at the start is capitalized
    ],
)
def test_title_name(raw, expected):
    assert rules.title_name(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected", "applied", "problem"),
    [
        (
            " Ana.Perez@GMIAL.com. ",
            "ana.perez@gmail.com",
            ["email_format", "email_domain_typo"],
            None,
        ),
        ("mailto:luis@empresa.example", "luis@empresa.example", ["email_format"], None),
        ("ok@hotmail.com", "ok@hotmail.com", [], None),
        ("luis at gmail.com", "luisatgmail.com", ["email_format"], "not a valid email address"),
        ("camilo@", "camilo@", [], "not a valid email address"),
    ],
)
def test_normalize_email(raw, expected, applied, problem):
    assert rules.normalize_email(raw) == (expected, applied, problem)


def test_email_typo_fix_can_be_disabled():
    assert rules.normalize_email("a@gmial.com", fix_typos=False)[0] == "a@gmial.com"


@pytest.mark.parametrize(
    ("raw", "country", "expected"),
    [
        ("300 123 4567", "CO", "+573001234567"),
        ("(57) 300-123-4567", "CO", "+573001234567"),
        ("+57 300 1234567", "CO", "+573001234567"),
        ("0057 3001234567", "CO", "+573001234567"),
        ("(415) 555-0134", "US", "+14155550134"),
        ("1-415-555-0134", "US", "+14155550134"),
        ("+1 (415) 555-0134 ext 22", "US", "+14155550134"),
        ("07700 900123", "GB", "+447700900123"),  # national trunk 0 dropped
    ],
)
def test_normalize_phone(raw, country, expected):
    assert rules.normalize_phone(raw, country) == (expected, None)


def test_bad_phone_is_left_unchanged_with_a_problem():
    assert rules.normalize_phone("32535", "CO") == ("32535", "does not look like a CO phone number")
    assert rules.normalize_phone("+12", "CO")[1] == "phone number has an invalid length"


@pytest.mark.parametrize(
    ("raw", "order", "expected"),
    [
        ("25/12/2025", "DMY", "2025-12-25"),
        ("12/25/2025", "MDY", "2025-12-25"),
        ("03/04/2026", "DMY", "2026-04-03"),
        ("03/04/2026", "MDY", "2026-03-04"),
        ("5.3.24", "DMY", "2024-03-05"),
        ("2024/03/05 10:30", "MDY", "2024-03-05"),
        ("3 de marzo de 2024", "DMY", "2024-03-03"),
        ("12-Sep-2025", "MDY", "2025-09-12"),
        ("March 3rd, 2024", "DMY", "2024-03-03"),
        ("45000", "DMY", "2023-03-15"),  # Excel serial number
        ("31/02/2024", "DMY", None),
        ("13/31/2026", "MDY", None),
        ("next tuesday", "DMY", None),
    ],
)
def test_parse_date(raw, order, expected):
    assert rules.parse_date(raw, order) == expected


@pytest.mark.parametrize(
    ("raw", "decimal", "expected"),
    [
        ("$ 1.234.567,50", ",", "1234567.5"),
        ("COP 713.000", ",", "713000"),
        ("USD 1,234.50", ".", "1234.5"),
        ("(1.200)", ",", "-1200"),
        ("350-", ".", "-350"),
        ("1 500", ",", "1500"),
        ("0,50", ",", "0.5"),
        ("007", ".", "7"),
        ("-0", ".", "0"),
        ("15%", ".", None),
        ("TBD", ".", None),
    ],
)
def test_parse_number(raw, decimal, expected):
    assert rules.parse_number(raw, decimal) == expected

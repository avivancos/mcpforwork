"""Zero-LLM CV parser (S5.1, ported donor behaviors). Never invents fields."""

import json

from mcpforwork.domain.cv import extract_profile_from_cv
from mcpforwork.entrypoints.mcp import server

_CV = """Ada Lovelace
London, UK · +44 20 7946 0958
ada@example.com · https://www.linkedin.com/in/ada · https://github.com/ada
https://ada.dev

EXPERIENCE
Data Engineer at Acme (2020-2024): pipelines. Call 555 123 4567 for references.
"""


def test_extracts_all_header_fields() -> None:
    result = extract_profile_from_cv(_CV)
    c = result["candidate"]
    assert c["full_name"] == "Ada Lovelace"
    assert c["contact_email"] == "ada@example.com"
    assert "7946" in c["phone"]
    assert c["linkedin"] == "https://www.linkedin.com/in/ada"
    assert c["github"] == "https://github.com/ada"
    assert c["portfolio"] == "https://ada.dev"
    assert result["cv_text"] == _CV


def test_name_from_explicit_label() -> None:
    c = extract_profile_from_cv("Name: Grace Hopper\ngrace@x.com")["candidate"]
    assert c["full_name"] == "Grace Hopper"


def test_no_name_when_header_starts_with_email_or_section() -> None:
    assert extract_profile_from_cv("ada@x.com\nstuff")["candidate"]["full_name"] is None
    assert extract_profile_from_cv("EXPERIENCE\nAcme 2020")["candidate"]["full_name"] is None


def test_email_found_anywhere_but_phone_only_in_header() -> None:
    cv = "Ada Lovelace\nSUMMARY\nWorked 2020-2023.\nContact: ada@x.com, 555 123 4567"
    c = extract_profile_from_cv(cv)["candidate"]
    assert c["contact_email"] == "ada@x.com"  # whole-document scan
    assert c["phone"] is None  # body numbers (dates etc.) are not phones


def test_date_ranges_are_not_phones() -> None:
    c = extract_profile_from_cv("Ada\n2020-2023\nada@x.com")["candidate"]
    assert c["phone"] is None  # fewer than 7 digits


def test_low_confidence_fields_are_none_never_invented() -> None:
    c = extract_profile_from_cv("just some text with nothing in it")["candidate"]
    assert all(v is None for v in c.values())


def test_parse_cv_tool_returns_fields_but_never_writes(mcp_env) -> None:
    result = json.loads(server.parse_cv(_CV))
    assert result["candidate"]["full_name"] == "Ada Lovelace"
    assert "confirm" in result["next_action"].lower() or "confirm" in str(result).lower()
    # The tool must NOT have created a profile.
    assert "error" in json.loads(server.get_profile())

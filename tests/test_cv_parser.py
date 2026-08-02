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
    assert c["phone"] is None  # 8 digits < the 9-digit phone threshold


def test_header_that_starts_with_a_url_yields_no_name() -> None:
    assert extract_profile_from_cv("https://ada.dev\nada@x.com")["candidate"]["full_name"] is None


def test_a_phone_only_header_line_is_not_a_name() -> None:
    assert extract_profile_from_cv("+34 600 123 456\nada@x.com")["candidate"]["full_name"] is None


def test_a_bare_field_label_is_not_a_name() -> None:
    assert extract_profile_from_cv("Name:\nGrace")["candidate"]["full_name"] is None


def test_parser_is_linear_on_adversarial_input() -> None:
    # ReDoS regression: a long run of word chars with no '@' must not backtrack
    # quadratically. Bounded quantifiers keep this well under a second.
    import time

    payload = "a" * 200_000
    start = time.perf_counter()
    extract_profile_from_cv(payload)
    assert time.perf_counter() - start < 1.0


def test_low_confidence_fields_are_none_never_invented() -> None:
    c = extract_profile_from_cv("just some text with nothing in it")["candidate"]
    assert all(v is None for v in c.values())


def test_parse_cv_tool_returns_fields_but_never_writes(mcp_env) -> None:
    result = json.loads(server.parse_cv(_CV))
    assert result["candidate"]["full_name"] == "Ada Lovelace"
    assert "setup_hints" in result
    assert "confirm" in result["next_action"].lower()
    # The tool must NOT have created a profile.
    assert "error" in json.loads(server.get_profile())


def test_parse_cv_rejects_oversized_input(mcp_env) -> None:
    assert "error" in json.loads(server.parse_cv("x" * 300_000))


def test_parse_cv_and_profile_gaps_are_registered_tools() -> None:
    import asyncio

    names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert {"parse_cv", "profile_gaps"} <= names


_CV_FOCUSED = """Ada Lovelace
ada@example.com

SUMMARY
Remote contract / freelance Python engineer building agentic AI and LLM tools.

SKILLS
Python, FastAPI, LLM, MCP, LangChain, Docker, agents, transformers
Also: florb (not a real skill).

EXPERIENCE
Open to B2B invoice engagements and remote WFH.
"""


def test_setup_hints_surface_modality_and_allowlisted_skills() -> None:
    # S5.3: evidence-only hints so /setup can focus without inventing titles.
    result = extract_profile_from_cv(_CV_FOCUSED)
    hints = result["setup_hints"]
    assert "remote" in hints["work_modes"]
    assert set(hints["employment_types"]) >= {"contract", "freelance"}
    assert "python" in hints["skills_top"]
    assert "llm" in hints["skills_top"]
    assert "mcp" in hints["skills_top"]
    assert "florb" not in hints["skills_top"]
    assert any("remote" in s.lower() for s in hints["signals"])
    assert result["candidate"]["full_name"] == "Ada Lovelace"
    assert result["candidate"]["contact_email"] == "ada@example.com"


def test_setup_hints_are_empty_when_cv_has_no_modality_or_skills() -> None:
    result = extract_profile_from_cv("just some text with nothing in it")
    hints = result["setup_hints"]
    assert hints["work_modes"] == []
    assert hints["employment_types"] == []
    assert hints["skills_top"] == []
    assert hints["signals"] == []


def test_b2b_and_invoice_are_signals_not_employment_types() -> None:
    cv = "Ada\nada@x.com\nOpen to direct B2B / invoice work only."
    hints = extract_profile_from_cv(cv)["setup_hints"]
    assert hints["employment_types"] == []
    assert any("b2b" in s.lower() or "invoice" in s.lower() for s in hints["signals"])


def test_skills_top_is_capped_and_sorted_by_frequency_then_alpha() -> None:
    # python x3, docker x2, llm x1 — order by count desc, then name.
    cv = "Skills: python python python docker docker llm florb florb florb"
    top = extract_profile_from_cv(cv)["setup_hints"]["skills_top"]
    assert top[0] == "python"
    assert top[1] == "docker"
    assert "llm" in top
    assert "florb" not in top
    assert len(top) <= 12


def test_skills_top_hard_cap_is_twelve() -> None:
    # >12 distinct allowlisted skills → still at most 12.
    skills = [
        "python",
        "fastapi",
        "django",
        "flask",
        "llm",
        "mcp",
        "langchain",
        "docker",
        "kubernetes",
        "aws",
        "gcp",
        "azure",
        "terraform",
        "postgres",
        "redis",
        "kafka",
    ]
    assert len(skills) > 12
    top = extract_profile_from_cv("Skills: " + " ".join(skills))["setup_hints"]["skills_top"]
    assert len(top) == 12
    assert "florb" not in top


def test_hybrid_onsite_full_time_part_time_modality_hints() -> None:
    hints = extract_profile_from_cv("Open to hybrid or on-site full-time; also part-time seasons.")[
        "setup_hints"
    ]
    assert "hybrid" in hints["work_modes"]
    assert "onsite" in hints["work_modes"]
    assert "full_time" in hints["employment_types"]
    assert "part_time" in hints["employment_types"]

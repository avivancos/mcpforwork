"""Finding scoring is profile/sector-driven — NOT a hardcoded tech persona."""

from mcpforwork.domain.scoring import determine_action, score_finding


def test_a_nurse_profile_scores_a_nursing_role_above_a_software_role() -> None:
    profile = {
        "target_titles": ["Registered Nurse", "ICU Nurse"],
        "sectors": ["healthcare"],
        "work_modes": ["onsite"],
        "seniority": "senior",
    }
    nursing = {
        "title": "Senior Registered Nurse - ICU",
        "description": "Provide critical care nursing in our healthcare unit.",
    }
    software = {"title": "Backend Software Engineer", "description": "Build APIs in Python and Go."}
    assert score_finding(nursing, profile)[0] > score_finding(software, profile)[0]
    assert score_finding(nursing, profile)[0] >= 40


def test_a_welder_profile_scores_welding_above_nursing() -> None:
    # The mirror image proves there is no hardcoded persona.
    profile = {"target_titles": ["Welder", "Fabricator"], "sectors": ["manufacturing"]}
    welding = {"title": "MIG Welder / Fabricator", "description": "Steel fabrication and welding."}
    nursing = {"title": "Registered Nurse", "description": "Patient care in a hospital ward."}
    assert score_finding(welding, profile)[0] > score_finding(nursing, profile)[0]


def test_remote_and_salary_signals_add_points() -> None:
    profile = {"target_titles": ["Data Analyst"], "work_modes": ["remote"]}
    base = {"title": "Data Analyst", "description": "SQL reporting."}
    rich = {
        "title": "Data Analyst",
        "description": "SQL reporting. Offering $90k salary.",
        "remote_scope": "remote",
    }
    assert score_finding(rich, profile)[0] > score_finding(base, profile)[0]


def test_an_empty_profile_never_invents_relevance() -> None:
    score, breakdown = score_finding({"title": "Anything", "description": "words"}, {})
    assert breakdown["title"] == 0
    assert breakdown["sector"] == 0


def test_score_is_bounded_0_to_100() -> None:
    profile = {
        "target_titles": ["Senior Backend Engineer Python API Platform"],
        "sectors": ["fintech", "saas", "payments"],
        "work_modes": ["remote"],
        "seniority": "senior",
    }
    finding = {
        "title": "Senior Backend Engineer - Python API",
        "description": "Fintech saas payments platform, senior, $150k, remote.",
        "remote_scope": "remote",
        "salary_text": "$150k",
    }
    score, _ = score_finding(finding, profile)
    assert 0 <= score <= 100


def test_determine_action_at_threshold_boundaries() -> None:
    assert determine_action(70) == "strong"
    assert determine_action(69) == "review"
    assert determine_action(40) == "review"
    assert determine_action(39) == "new"


def test_each_signal_dimension_contributes_independently() -> None:
    profile = {"target_titles": ["Data Analyst"], "work_modes": ["remote"], "seniority": "senior"}
    base = {"title": "Data Analyst", "description": "reporting"}
    base_score = score_finding(base, profile)[0]
    assert score_finding({**base, "remote_scope": "remote"}, profile)[0] == base_score + 10
    assert score_finding({**base, "salary_text": "$90k"}, profile)[0] == base_score + 8
    assert (
        score_finding({"title": "Senior Data Analyst", "description": "reporting"}, profile)[0]
        == base_score + 10
    )

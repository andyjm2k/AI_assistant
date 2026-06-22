from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Sequence


PARTICIPANT_ORDER = [
    "ceo_agent",
    "product_manager_agent",
    "cfo_agent",
    "chief_marketer_agent",
    "architect_agent",
    "ux_designer_agent",
    "lead_engineer_agent",
    "qa_officer_agent",
    "user_proxy_agent",
]

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SCRATCH_DIR = _PROJECT_ROOT / "scratch"
_WRITE_TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".html", ".xml", ".yaml", ".yml"}


def next_participant_after(source: str | None) -> str:
    if source not in PARTICIPANT_ORDER:
        return "ceo_agent"
    index = PARTICIPANT_ORDER.index(source)
    return PARTICIPANT_ORDER[(index + 1) % len(PARTICIPANT_ORDER)]


def latest_participant_source(history: Sequence[Any]) -> str | None:
    for item in reversed(history):
        source = None
        if isinstance(item, dict):
            source = item.get("source") or item.get("name")
        else:
            source = getattr(item, "source", None) or getattr(item, "name", None)
        if source in PARTICIPANT_ORDER:
            return str(source)
    return None


def select_company_speaker_name(history: Sequence[Any]) -> str:
    return next_participant_after(latest_participant_source(history))


def write_scratch_text(path: str, content: str, append: bool = False) -> str:
    """Write a final text deliverable under CATBot scratch and return the saved scratch-relative path."""
    raw_path = str(path or "").strip().replace("\\", "/")
    if not raw_path:
        return "path is required."
    if raw_path.startswith("scratch/"):
        raw_path = raw_path[len("scratch/") :]
    if raw_path in {".", ".."} or not raw_path:
        return "Invalid scratch path."
    candidate = (_SCRATCH_DIR / raw_path).resolve()
    scratch_root = _SCRATCH_DIR.resolve()
    try:
        candidate.relative_to(scratch_root)
    except ValueError:
        return "Invalid scratch path: path must stay under scratch."
    if candidate.suffix.lower() not in _WRITE_TEXT_EXTENSIONS:
        allowed = ", ".join(sorted(_WRITE_TEXT_EXTENSIONS))
        return f"Unsupported text file extension '{candidate.suffix or '(none)'}'. Allowed: {allowed}."
    candidate.parent.mkdir(parents=True, exist_ok=True)
    text = str(content or "")
    if append:
        with candidate.open("a", encoding="utf-8") as handle:
            handle.write(text)
    else:
        candidate.write_text(text, encoding="utf-8")
    relative = candidate.relative_to(scratch_root).as_posix()
    return f"Wrote scratch/{relative} ({len(text.encode('utf-8'))} bytes)."


def load_role_tool_map() -> Dict[str, List[Any]]:
    """Load AG2 role tools with department-specific scope."""
    from src.autogen import team_builder as tb

    market_research = [tb.webSearch, tb.scrapeWebsite, tb.runDeepResearch]
    technical_research = [tb.webSearch, tb.scrapeWebsite, tb.runBrowserAgent]
    light_research = [tb.webSearch, tb.scrapeWebsite]
    return {
        "ceo_agent": [tb.mission_brief, tb.rally_message, write_scratch_text],
        "product_manager_agent": [tb.requirement_record, tb.prioritize_opportunity, *market_research],
        "cfo_agent": [tb.financial_projection, tb.business_case, *market_research],
        "chief_marketer_agent": [tb.go_to_market_plan, tb.market_growth_frame, *market_research],
        "architect_agent": [tb.architecture_decision, tb.component_contract, *technical_research],
        "ux_designer_agent": [tb.experience_brief, tb.ux_review_checklist, *light_research],
        "lead_engineer_agent": [tb.engineer_calculator, tb.implementation_plan, *technical_research, tb.codex_cli_task, write_scratch_text],
        "qa_officer_agent": [tb.test_plan, tb.quality_gate],
        "user_proxy_agent": [tb.user_feedback, tb.acceptance_recommendation],
    }

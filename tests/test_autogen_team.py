"""Tests for the Python-defined AutoGen team and runtime loader."""

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEAM_BUILDER_FILE = PROJECT_ROOT / "src" / "autogen" / "team_builder.py"


@pytest.fixture
def built_team():
    try:
        from src.autogen.team_builder import build_virtual_product_company_team
    except ImportError:
        pytest.skip("AutoGen team builder not importable")
    return build_virtual_product_company_team()


@pytest.fixture
def dumped_team_config(built_team):
    return built_team.dump_component().model_dump()


def _tools_by_agent(dumped_team_config):
    config = dumped_team_config.get("config") or dumped_team_config
    participants = config.get("participants", [])
    tools_by_agent = {}
    for participant in participants:
        participant_config = participant.get("config", {})
        workbench = participant_config.get("workbench") or []
        tools = []
        if workbench:
            tools = [
                tool.get("config", {}).get("name")
                for tool in workbench[0].get("config", {}).get("tools", [])
            ]
        tools_by_agent[participant_config.get("name")] = tools
    return tools_by_agent


def test_team_builder_file_exists():
    assert TEAM_BUILDER_FILE.exists(), "Expected the Python AutoGen team builder to exist"


def test_team_builder_returns_selector_group_chat(built_team):
    from autogen_agentchat.teams import SelectorGroupChat

    assert isinstance(built_team, SelectorGroupChat)
    participants = getattr(built_team, "_participants", None) or getattr(built_team, "participants", [])
    assert len(participants) == 9
    first_name = getattr(participants[0], "name", None) or getattr(participants[0], "_name", None)
    assert first_name == "ceo_agent"


def test_selector_is_configured_for_explicit_progression(dumped_team_config):
    config = dumped_team_config.get("config") or dumped_team_config
    assert config.get("allow_repeated_speaker") is False
    assert config.get("emit_team_events") is True
    selector_prompt = config.get("selector_prompt", "")
    assert "product_manager_agent" in selector_prompt
    assert "ceo_agent" in selector_prompt


def test_role_tool_coverage(dumped_team_config):
    tools_by_agent = _tools_by_agent(dumped_team_config)
    expected = {
        "ceo_agent": {"mission_brief", "rally_message", "webSearch", "scrapeWebsite", "runBrowserAgent", "runDeepResearch"},
        "product_manager_agent": {"requirement_record", "prioritize_opportunity", "webSearch", "scrapeWebsite", "runBrowserAgent", "runDeepResearch"},
        "cfo_agent": {"financial_projection", "business_case", "webSearch", "scrapeWebsite", "runBrowserAgent", "runDeepResearch"},
        "chief_marketer_agent": {"go_to_market_plan", "market_growth_frame", "webSearch", "scrapeWebsite", "runBrowserAgent", "runDeepResearch"},
        "architect_agent": {"architecture_decision", "component_contract", "webSearch", "scrapeWebsite", "runBrowserAgent", "runDeepResearch"},
        "ux_designer_agent": {"experience_brief", "ux_review_checklist", "webSearch", "scrapeWebsite", "runBrowserAgent", "runDeepResearch"},
        "lead_engineer_agent": {"engineer_calculator", "implementation_plan", "webSearch", "scrapeWebsite", "runBrowserAgent", "runDeepResearch", "codex_cli_task"},
        "qa_officer_agent": {"test_plan", "quality_gate", "webSearch", "scrapeWebsite", "runBrowserAgent", "runDeepResearch"},
        "user_proxy_agent": {"user_feedback", "acceptance_recommendation", "webSearch", "scrapeWebsite", "runBrowserAgent", "runDeepResearch"},
    }
    for agent_name, required_tools in expected.items():
        assert agent_name in tools_by_agent, f"Missing participant {agent_name}"
        assert required_tools.issubset(set(tools_by_agent[agent_name])), f"{agent_name} missing required tools"


def test_planning_roles_have_research_prompting_and_multi_step_tool_budget(dumped_team_config):
    config = dumped_team_config.get("config") or dumped_team_config
    participants = config.get("participants", [])
    by_name = {participant.get("config", {}).get("name"): participant.get("config", {}) for participant in participants}

    expected_agents = {
        "product_manager_agent": [
            "market sizing",
            "webSearch",
            "scrapeWebsite",
            "runBrowserAgent",
            "runDeepResearch",
        ],
        "cfo_agent": [
            "pricing benchmarks",
            "webSearch",
            "scrapeWebsite",
            "runBrowserAgent",
            "runDeepResearch",
        ],
        "chief_marketer_agent": [
            "TAM",
            "SOM",
            "webSearch",
            "scrapeWebsite",
            "runBrowserAgent",
            "runDeepResearch",
        ],
        "architect_agent": [
            "external technical documentation",
            "webSearch",
            "scrapeWebsite",
            "runBrowserAgent",
            "runDeepResearch",
        ],
    }

    for agent_name, required_fragments in expected_agents.items():
        agent_config = by_name.get(agent_name)
        assert agent_config, f"Missing participant {agent_name}"
        assert agent_config.get("max_tool_iterations") == 4
        system_message = agent_config.get("system_message", "")
        for fragment in required_fragments:
            assert fragment in system_message, f"{agent_name} system prompt missing {fragment!r}"


def test_tool_agents_disable_reflection_in_python_builder(dumped_team_config):
    config = dumped_team_config.get("config") or dumped_team_config
    participants = config.get("participants", [])
    for participant in participants:
        participant_config = participant.get("config", {})
        workbench = participant_config.get("workbench") or []
        if workbench:
            assert participant_config.get("reflect_on_tool_use") is False


def test_deterministic_selector_progression():
    from src.autogen.team_builder import select_company_speaker

    class FakeMessage:
        def __init__(self, source: str, content: str = "") -> None:
            self.source = source
            self.content = content

    assert select_company_speaker([FakeMessage("user", "Task")]) == "ceo_agent"
    assert select_company_speaker([FakeMessage("user"), FakeMessage("ceo_agent")]) == "product_manager_agent"
    assert select_company_speaker([FakeMessage("product_manager_agent")]) == "cfo_agent"
    assert select_company_speaker([FakeMessage("cfo_agent")]) == "chief_marketer_agent"
    assert select_company_speaker([FakeMessage("chief_marketer_agent")]) == "architect_agent"
    assert select_company_speaker([FakeMessage("architect_agent")]) == "ux_designer_agent"
    assert select_company_speaker([FakeMessage("ux_designer_agent")]) == "lead_engineer_agent"
    assert select_company_speaker([FakeMessage("lead_engineer_agent")]) == "qa_officer_agent"
    assert select_company_speaker([FakeMessage("qa_officer_agent")]) == "user_proxy_agent"
    assert select_company_speaker([FakeMessage("user_proxy_agent")]) == "ceo_agent"


def test_builder_can_export_team_config():
    from src.autogen.team_builder import export_virtual_product_company_team_config

    export_path = PROJECT_ROOT / "scratch" / "test_team_config_export.json"
    try:
        written_path = export_virtual_product_company_team_config(export_path)
        assert written_path == export_path
        assert export_path.exists()
        import json

        data = json.loads(export_path.read_text(encoding="utf-8"))
        assert data.get("provider") == "autogen_agentchat.teams.SelectorGroupChat"
        participants = (data.get("config") or {}).get("participants", [])
        assert participants[0].get("config", {}).get("name") == "ceo_agent"
    finally:
        export_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_start_stop_code_executors_no_raise():
    try:
        from src.servers.proxy_server import _start_code_executors, _stop_code_executors
    except ImportError:
        pytest.skip("proxy_server not importable")
    await _start_code_executors(None)
    await _stop_code_executors(None)


def test_runtime_loader_returns_python_defined_team():
    try:
        from src.servers.proxy_server import load_autogen_team_runtime
    except ImportError:
        pytest.skip("proxy_server not importable")

    team = load_autogen_team_runtime()
    assert team is not None
    participants = getattr(team, "_participants", None) or getattr(team, "participants", [])
    names = [getattr(p, "name", None) or getattr(p, "_name", None) for p in participants]
    assert names == [
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

    lead_engineer = next(
        participant
        for participant in participants
        if (getattr(participant, "name", None) or getattr(participant, "_name", None)) == "lead_engineer_agent"
    )
    workbench = getattr(lead_engineer, "workbench", getattr(lead_engineer, "_workbench", None)) or []
    wb_list = workbench if isinstance(workbench, list) else [workbench]
    tool_names = []
    for wb_item in wb_list:
        tools = getattr(wb_item, "tools", getattr(wb_item, "_tools", None)) or []
        tool_names.extend(getattr(tool, "name", "") for tool in tools)
    if tool_names:
        assert "CodeExecutor" in tool_names or "python_code_execution" in tool_names


def test_retryable_provider_error_detector():
    try:
        from src.servers.proxy_server import _is_retryable_autogen_provider_error
    except ImportError:
        pytest.skip("proxy_server not importable")

    assert _is_retryable_autogen_provider_error(TypeError("'NoneType' object is not subscriptable")) is True
    assert _is_retryable_autogen_provider_error(RuntimeError("different failure")) is False

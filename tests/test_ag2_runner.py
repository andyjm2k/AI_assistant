from types import SimpleNamespace

import pytest


def test_ag2_settings_use_expected_fallbacks():
    from src.workflows.ag2_runner import resolve_ag2_settings

    settings = resolve_ag2_settings(
        {
            "AUTOGEN_TEAM_MODEL": "fallback-model",
            "OPENROUTER_API_BASE": "https://openrouter.example/v1",
            "OPENAI_API_KEY": "fallback-key",
            "AG2_MAX_ROUNDS": "12",
            "AG2_ENABLE_CODE_EXECUTION": "true",
        }
    )

    assert settings.model == "fallback-model"
    assert settings.base_url == "https://openrouter.example/v1"
    assert settings.api_key == "fallback-key"
    assert settings.max_rounds == 12
    assert settings.code_execution_config()["work_dir"] == "coding"


def test_ag2_runner_reports_missing_dependency(monkeypatch):
    from src.workflows import ag2_runner

    def fake_import(_name):
        raise ImportError("no ag2")

    monkeypatch.setattr(ag2_runner.importlib, "import_module", fake_import)

    availability = ag2_runner.Ag2WorkflowRunner({}).available()

    assert availability.available is False
    assert "AG2 backend not available" in availability.message


@pytest.mark.asyncio
async def test_ag2_runner_builds_agents_registers_tools_and_normalizes_history(monkeypatch):
    from src.workflows import ag2_runner

    registered = []

    class FakeAssistantAgent:
        def __init__(self, **kwargs):
            self.name = kwargs["name"]
            self.kwargs = kwargs
            self.registered_tools = []

    class FakeUserProxyAgent:
        def __init__(self, **kwargs):
            self.name = kwargs["name"]
            self.kwargs = kwargs
            self.function_map = {}

        def can_execute_function(self, names):
            return all(name in self.function_map for name in names)

        def initiate_chat(self, manager, message, clear_history=True):
            assert message == "build a report"
            assert clear_history is True
            history = [
                {"name": "ceo_agent", "content": "Frame the goal."},
                {"name": "product_manager_agent", "content": "Requirements ready."},
            ]
            manager.groupchat.messages = history
            return SimpleNamespace(chat_history=history)

    class FakeGroupChat:
        def __init__(self, **kwargs):
            self.agents = kwargs["agents"]
            self.messages = kwargs["messages"]
            self.max_round = kwargs["max_round"]
            self.speaker_selection_method = kwargs["speaker_selection_method"]
            self.allow_repeat_speaker = kwargs["allow_repeat_speaker"]

    class FakeGroupChatManager:
        def __init__(self, **kwargs):
            self.groupchat = kwargs["groupchat"]
            self.llm_config = kwargs["llm_config"]

    def fake_register_function(function, caller, executor, name, description):
        caller.registered_tools.append(name)
        executor.function_map[name] = function
        registered.append(
            {
                "function": function,
                "caller": caller.name,
                "executor": executor.name,
                "name": name,
                "description": description,
            }
        )

    def fake_tool(value: str = "") -> str:
        """Fake workflow tool."""
        return value

    fake_autogen = SimpleNamespace(
        AssistantAgent=FakeAssistantAgent,
        UserProxyAgent=FakeUserProxyAgent,
        GroupChat=FakeGroupChat,
        GroupChatManager=FakeGroupChatManager,
        register_function=fake_register_function,
    )

    monkeypatch.setattr(ag2_runner.importlib, "import_module", lambda _name: fake_autogen)
    monkeypatch.setattr(ag2_runner, "load_role_tool_map", lambda: {"ceo_agent": [fake_tool]})

    runner = ag2_runner.Ag2WorkflowRunner(
        {
            "AG2_MODEL": "test-model",
            "AG2_API_KEY": "test-key",
            "AG2_BASE_URL": "https://example.test/v1",
            "AG2_MAX_ROUNDS": "5",
        }
    )

    team = runner.load()

    assert [agent.name for agent in team["agents"]] == ag2_runner.PARTICIPANT_ORDER
    assert [agent.name for agent in team["groupchat"].agents] == [
        "workflow_user",
        *ag2_runner.PARTICIPANT_ORDER,
        "tool_executor_agent",
    ]
    assert team["groupchat"].max_round == 5
    assert registered[0]["caller"] == "ceo_agent"
    assert registered[0]["executor"] == "tool_executor_agent"
    assert registered[0]["name"] == "fake_tool"

    team["groupchat"].messages = [{"name": "ceo_agent", "content": "start"}]
    next_speaker = team["groupchat"].speaker_selection_method(team["agents"][0], team["groupchat"])
    assert next_speaker.name == "product_manager_agent"

    team["groupchat"].messages = [
        {
            "name": "ceo_agent",
            "content": "",
            "tool_calls": [
                {
                    "type": "function",
                    "function": {"name": "fake_tool", "arguments": "{}"},
                }
            ],
        }
    ]
    next_speaker = team["groupchat"].speaker_selection_method(team["agents"][0], team["groupchat"])
    assert next_speaker.name == "tool_executor_agent"

    team["groupchat"].messages = [
        {
            "name": "cfo_agent",
            "content": "",
            "tool_calls": [
                {
                    "type": "function",
                    "function": {"name": "fake_tool", "arguments": "{}"},
                }
            ],
        },
        {"name": "tool_executor_agent", "content": "tool result"},
    ]
    next_speaker = team["groupchat"].speaker_selection_method(team["tool_executor"], team["groupchat"])
    assert next_speaker.name == "cfo_agent"

    system_messages = {agent.name: agent.kwargs["system_message"] for agent in team["agents"]}
    assert "finance research" in system_messages["cfo_agent"]
    assert "software architecture only" in system_messages["architect_agent"]
    assert "stay in your department lane" in system_messages["lead_engineer_agent"]

    result = await runner.run("build a report")

    assert result.framework == "ag2"
    assert result.message_count == 2
    assert result.messages[-1].source == "product_manager_agent"
    assert "Requirements ready." in result.output


def test_ag2_role_tool_map_is_department_specific():
    from src.workflows.shared_tools import load_role_tool_map, write_scratch_text

    role_tools = load_role_tool_map()
    names_by_role = {
        role: {getattr(tool, "__name__", "") for tool in tools}
        for role, tools in role_tools.items()
    }

    assert {"financial_projection", "business_case", "webSearch", "scrapeWebsite", "runDeepResearch"}.issubset(
        names_by_role["cfo_agent"]
    )
    assert "runBrowserAgent" not in names_by_role["cfo_agent"]
    assert {"architecture_decision", "component_contract", "runBrowserAgent"}.issubset(
        names_by_role["architect_agent"]
    )
    assert "financial_projection" not in names_by_role["architect_agent"]
    assert names_by_role["qa_officer_agent"] == {"test_plan", "quality_gate"}
    assert write_scratch_text in role_tools["ceo_agent"]


def test_ag2_write_scratch_text_restricts_output_to_scratch():
    from pathlib import Path
    import uuid

    from src.workflows.shared_tools import write_scratch_text

    filename = f"ag2-test-{uuid.uuid4().hex}.md"
    result = write_scratch_text(filename, "# AG2 deliverable\n")
    path = Path("scratch") / filename
    try:
        assert result.startswith(f"Wrote scratch/{filename}")
        assert path.read_text(encoding="utf-8") == "# AG2 deliverable\n"
        assert "Invalid scratch path" in write_scratch_text("../outside.md", "bad")
        assert "Unsupported text file extension" in write_scratch_text("report.exe", "bad")
    finally:
        if path.exists():
            path.unlink()

from __future__ import annotations

import asyncio
import importlib
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

from .shared_tools import PARTICIPANT_ORDER, next_participant_after, load_role_tool_map
from .types import WorkflowAvailability, WorkflowMessage, WorkflowRunResult


def _first_non_empty_env(env: Mapping[str, str], names: List[str]) -> str:
    for name in names:
        value = str(env.get(name) or "").strip()
        if value:
            return value
    return ""


def _env_bool(env: Mapping[str, str], name: str, default: bool = False) -> bool:
    value = str(env.get(name) or "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "y", "on"}


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _stringify_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    try:
        return json.dumps(content, ensure_ascii=False, indent=2, default=str)
    except TypeError:
        return str(content)


@dataclass(frozen=True)
class Ag2Settings:
    model: str
    base_url: str
    api_key: str
    api_type: str
    max_rounds: int
    enable_code_execution: bool

    def llm_config(self, *, temperature: float = 0.2, timeout: int = 180) -> Dict[str, Any]:
        config: Dict[str, Any] = {
            "model": self.model,
            "api_key": self.api_key,
            "api_type": self.api_type,
        }
        if self.base_url:
            config["base_url"] = self.base_url
        return {
            "config_list": [config],
            "temperature": temperature,
            "timeout": timeout,
        }

    def code_execution_config(self) -> Any:
        if not self.enable_code_execution:
            return False
        return {"use_docker": False, "work_dir": "coding"}


def resolve_ag2_settings(env: Optional[Mapping[str, str]] = None) -> Ag2Settings:
    source = os.environ if env is None else env
    return Ag2Settings(
        model=_first_non_empty_env(
            source,
            [
                "AG2_MODEL",
                "AUTOGEN_TEAM_MODEL",
                "OPENROUTER_AUTOGEN_MODEL",
                "MCP_LLM_MODEL_NAME",
                "OPENAI_MODEL",
            ],
        ),
        base_url=_first_non_empty_env(
            source,
            [
                "AG2_BASE_URL",
                "AUTOGEN_BASE_URL",
                "AUTOGEN_OPENROUTER_BASE_URL",
                "OPENROUTER_API_BASE",
                "MCP_LLM_BASE_URL",
                "OPENAI_API_BASE",
            ],
        ),
        api_key=_first_non_empty_env(
            source,
            [
                "AG2_API_KEY",
                "AUTOGEN_OPENROUTER_API_KEY",
                "OPENROUTER_API_KEY",
                "AUTOGEN_MINIMAX_API_KEY",
                "MINIMAX_API_KEY",
                "MCP_LLM_OPENAI_API_KEY",
                "OPENAI_API_KEY",
            ],
        ),
        api_type=str(source.get("AG2_API_TYPE") or "openai").strip() or "openai",
        max_rounds=_bounded_int(source.get("AG2_MAX_ROUNDS"), default=24, minimum=2, maximum=100),
        enable_code_execution=_env_bool(source, "AG2_ENABLE_CODE_EXECUTION", default=False),
    )


def _lookup_ag2_attr(module: Any, name: str) -> Any:
    if hasattr(module, name):
        return getattr(module, name)
    agentchat = getattr(module, "agentchat", None)
    if agentchat is not None and hasattr(agentchat, name):
        return getattr(agentchat, name)
    raise AttributeError(name)


def _tool_description(tool: Any) -> str:
    doc = str(getattr(tool, "__doc__", "") or "").strip().splitlines()
    if doc:
        return doc[0].strip()
    return f"CATBot workflow tool: {getattr(tool, '__name__', 'tool')}"


_ROLE_COORDINATION_RULES = (
    "Company operating rules: stay in your department lane; do not complete work owned by another role. "
    "If another role owns the next artifact, hand off to that exact agent name. When you use tools, wait for the "
    "tool result and then produce a concise role-specific deliverable before handing off. Do not claim the whole "
    "workflow is complete unless your role is explicitly responsible for final synthesis. Preserve decisions and "
    "evidence from prior roles instead of restarting the same work."
)


def _role_system_messages() -> Dict[str, str]:
    messages = {
        "ceo_agent": (
            "You are the CEO of a virtual product company. On your first turn, frame the product vision, target "
            "customer, business outcome, decision criteria, and role plan. Do not do PM scoping, CFO finance, "
            "marketing strategy, architecture, engineering, QA, or user feedback yourself. After the user proxy and "
            "QA have contributed, synthesize the final executive decision. If the user requested a final document, "
            "use write_scratch_text only after incorporating the role-owned deliverables."
        ),
        "product_manager_agent": (
            "You are the Product Manager. Own problem framing, customer segments, requirements, assumptions, scope, "
            "acceptance criteria, and prioritization. Use market research tools only for product, customer, "
            "competitor, and requirement evidence. Do not create financial projections, GTM strategy, technical "
            "architecture, implementation plans, QA gates, or final executive summaries."
        ),
        "cfo_agent": (
            "You are the Chief Financial Officer. Own finance research, pricing benchmarks, revenue drivers, cost "
            "structure, unit economics, cash runway, payback logic, financial risks, and a defensible business case. "
            "Use financial_projection and business_case for finance artifacts. Do not design the product, market "
            "campaign, system architecture, UX, implementation plan, QA plan, or final user-facing document."
        ),
        "chief_marketer_agent": (
            "You are the Chief Marketer. Own TAM/SOM framing, positioning, audience segmentation, channels, funnel, "
            "messaging, launch sequencing, and conversion assumptions. Use GTM tools and market research. Do not "
            "overwrite CFO numbers, define software architecture, produce implementation tasks, or finalize the plan."
        ),
        "architect_agent": (
            "You are the Chief Architect. Own software architecture only: system boundaries, components, data flow, "
            "integration points, security/privacy constraints, technical trade-offs, and implementation constraints. "
            "Use architecture_decision and component_contract. Research technical documentation when needed. Do not "
            "perform finance, marketing, UX copy/design, QA release gates, or final business-plan synthesis."
        ),
        "ux_designer_agent": (
            "You are the UX Designer. Own user journeys, interaction model, onboarding, trust cues, accessibility, "
            "information architecture, visual hierarchy, and friction points. Do not redo market sizing, finance, "
            "technical architecture, engineering tasks, or QA gates."
        ),
        "lead_engineer_agent": (
            "You are the Lead Engineer. Own implementation sequencing, engineering tasks, dependencies, delivery "
            "risks, build-vs-buy details, and code-level execution plans based on the architect and UX outputs. Use "
            "Codex only for concrete CATBot code work, and write_scratch_text only for technical deliverables when "
            "requested. Do not redo finance, marketing, architecture decisions, UX strategy, or final executive synthesis."
        ),
        "qa_officer_agent": (
            "You are the QA Officer. Own test strategy, defects, acceptance validation, compliance with requirements, "
            "and release gate. Direct defects to the responsible role. Do not create the product plan, financial model, "
            "marketing plan, architecture, implementation plan, or final summary."
        ),
        "user_proxy_agent": (
            "You represent the end user. React to the proposed experience with direct acceptance feedback, confusion, "
            "trust issues, missing value, and usability concerns. Do not perform internal company analysis or final synthesis."
        ),
    }
    return {name: f"{message}\n\n{_ROLE_COORDINATION_RULES}" for name, message in messages.items()}


def _message_source_name(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("name") or message.get("source") or message.get("role") or "")
    return str(getattr(message, "name", None) or getattr(message, "source", None) or getattr(message, "role", None) or "")


def _message_tool_function_names(message: Any) -> List[str]:
    if not isinstance(message, dict):
        return []
    funcs: List[str] = []
    if message.get("function_call"):
        name = (message.get("function_call") or {}).get("name")
        if name:
            funcs.append(str(name))
    for tool_call in message.get("tool_calls") or []:
        if tool_call.get("type") != "function":
            continue
        name = (tool_call.get("function") or {}).get("name")
        if name:
            funcs.append(str(name))
    return funcs


def _latest_tool_requester_name(messages: List[Any]) -> Optional[str]:
    for message in reversed(messages):
        source = _message_source_name(message)
        if source in PARTICIPANT_ORDER and _message_tool_function_names(message):
            return source
    return None


def _agent_by_name(groupchat: Any, name: str) -> Any:
    for agent in getattr(groupchat, "agents", []) or []:
        if getattr(agent, "name", None) == name:
            return agent
    return name


def _ag2_speaker_selection(last_speaker: Any, groupchat: Any) -> Any:
    messages = getattr(groupchat, "messages", []) or []
    if messages and isinstance(messages[-1], dict):
        latest = messages[-1]
        funcs = _message_tool_function_names(latest)
        if funcs:
            for agent in getattr(groupchat, "agents", []) or []:
                can_execute = getattr(agent, "can_execute_function", None)
                if callable(can_execute) and can_execute(funcs):
                    return agent
        if _message_source_name(latest) == "tool_executor_agent":
            requester_name = _latest_tool_requester_name(messages[:-1])
            if requester_name:
                return _agent_by_name(groupchat, requester_name)

    latest_name = None
    for message in reversed(messages):
        candidate = _message_source_name(message)
        if candidate in PARTICIPANT_ORDER:
            latest_name = str(candidate)
            break
    if latest_name is None:
        latest_name = getattr(last_speaker, "name", None)
    return _agent_by_name(groupchat, next_participant_after(latest_name))


def _normalize_ag2_history(history: Any) -> List[WorkflowMessage]:
    messages: List[WorkflowMessage] = []
    for item in history or []:
        if isinstance(item, dict):
            source = str(item.get("name") or item.get("source") or item.get("role") or "unknown")
            content = _stringify_content(item.get("content", ""))
        else:
            source = str(getattr(item, "name", None) or getattr(item, "source", None) or "unknown")
            content = _stringify_content(getattr(item, "content", item))
        if source == "tool_executor_agent":
            continue
        messages.append(WorkflowMessage(source=source, content=content))
    return messages


class Ag2WorkflowRunner:
    framework = "ag2"

    def __init__(self, env: Optional[Mapping[str, str]] = None) -> None:
        self._env = os.environ if env is None else env
        self._ag2_module: Any = None
        self._team: Optional[Dict[str, Any]] = None

    def _load_ag2_module(self) -> Any:
        if self._ag2_module is None:
            self._ag2_module = importlib.import_module("autogen")
        return self._ag2_module

    def available(self) -> WorkflowAvailability:
        try:
            module = self._load_ag2_module()
            for name in ["AssistantAgent", "UserProxyAgent", "GroupChat", "GroupChatManager"]:
                _lookup_ag2_attr(module, name)
        except Exception as exc:
            return WorkflowAvailability(
                available=False,
                framework=self.framework,
                message=(
                    "AG2 backend not available. Install AG2 with OpenAI support "
                    f"(for example: pip install \"ag2[openai]\"). Import error: {exc}"
                ),
            )
        return WorkflowAvailability(available=True, framework=self.framework, message="AG2 backend available.")

    def load(self) -> Dict[str, Any]:
        if self._team is not None:
            return self._team

        availability = self.available()
        if not availability.available:
            raise RuntimeError(availability.message)

        settings = resolve_ag2_settings(self._env)
        if not settings.model:
            raise RuntimeError("AG2_MODEL or a compatible model fallback is required for the AG2 backend.")
        if not settings.api_key:
            raise RuntimeError("AG2_API_KEY or a compatible API key fallback is required for the AG2 backend.")

        module = self._load_ag2_module()
        AssistantAgent = _lookup_ag2_attr(module, "AssistantAgent")
        UserProxyAgent = _lookup_ag2_attr(module, "UserProxyAgent")
        GroupChat = _lookup_ag2_attr(module, "GroupChat")
        GroupChatManager = _lookup_ag2_attr(module, "GroupChatManager")
        register_function = getattr(module, "register_function", None)
        if register_function is None:
            agentchat = getattr(module, "agentchat", None)
            register_function = getattr(agentchat, "register_function", None) if agentchat is not None else None
        if register_function is None:
            raise RuntimeError("AG2 register_function API is not available in the installed autogen package.")

        try:
            role_tools = load_role_tool_map()
        except Exception as exc:
            raise RuntimeError(f"AG2 backend could not load CATBot workflow tools: {exc}") from exc
        system_messages = _role_system_messages()
        llm_config = settings.llm_config()
        agents = []
        by_name: Dict[str, Any] = {}
        for name in PARTICIPANT_ORDER:
            agent = AssistantAgent(
                name=name,
                system_message=system_messages[name],
                llm_config=llm_config,
                description=system_messages[name],
            )
            agents.append(agent)
            by_name[name] = agent

        tool_executor = UserProxyAgent(
            name="tool_executor_agent",
            human_input_mode="NEVER",
            code_execution_config=settings.code_execution_config(),
            llm_config=False,
        )
        for role_name, tools in role_tools.items():
            caller = by_name.get(role_name)
            if caller is None:
                continue
            for tool in tools:
                register_function(
                    tool,
                    caller=caller,
                    executor=tool_executor,
                    name=getattr(tool, "__name__", "tool"),
                    description=_tool_description(tool),
                )

        workflow_user = UserProxyAgent(
            name="workflow_user",
            human_input_mode="NEVER",
            code_execution_config=False,
            llm_config=False,
        )
        groupchat = GroupChat(
            agents=[workflow_user, *agents, tool_executor],
            messages=[],
            max_round=settings.max_rounds,
            speaker_selection_method=_ag2_speaker_selection,
            allow_repeat_speaker=False,
        )
        manager = GroupChatManager(groupchat=groupchat, llm_config=llm_config)
        self._team = {
            "settings": settings,
            "agents": agents,
            "tool_executor": tool_executor,
            "workflow_user": workflow_user,
            "groupchat": groupchat,
            "manager": manager,
        }
        return self._team

    async def start(self) -> None:
        self.load()

    async def stop(self) -> None:
        self._team = None

    def _run_sync(self, input_text: str) -> WorkflowRunResult:
        team = self.load()
        groupchat = team["groupchat"]
        if hasattr(groupchat, "messages"):
            groupchat.messages = []

        chat_result = team["workflow_user"].initiate_chat(
            team["manager"],
            message=input_text,
            clear_history=True,
        )
        history = (
            getattr(chat_result, "chat_history", None)
            or getattr(groupchat, "messages", None)
            or []
        )
        messages = _normalize_ag2_history(history)
        final = messages[-1].content if messages else ""
        summary = (
            f"Completed with {len(messages)} messages. Final message from {messages[-1].source}:\n{final}"
            if final and messages
            else (f"Completed with {len(messages)} messages." if messages else "No messages returned from AG2 workflow.")
        )
        return WorkflowRunResult(
            framework=self.framework,
            output=summary,
            summary=summary,
            messages=messages,
            metadata={"max_rounds": team["settings"].max_rounds},
        )

    async def run(self, input_text: str) -> WorkflowRunResult:
        return await asyncio.to_thread(self._run_sync, input_text)

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Sequence

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import OrTerminationCondition
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.teams import SelectorGroupChat
from autogen_core.model_context import BufferedChatCompletionContext
from autogen_ext.models.openai import OpenAIChatCompletionClient
from src.utils.openai_compat import is_minimax_chat_request, normalize_temperature_for_minimax


AUTOGEN_TEAM_BUILDER_FILE = Path(__file__).resolve()
PROJECT_ROOT = AUTOGEN_TEAM_BUILDER_FILE.parents[2]
TEAM_CONFIG_EXPORT_FILE = PROJECT_ROOT / "config" / "team-config.json"
TEAM_NAME = "VirtualProductCompany"
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


_ENV_LOADED = False


def _ensure_project_env_loaded() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(env_file, override=False)
        except Exception:
            pass
    _ENV_LOADED = True


def _first_non_empty_env(names: Sequence[str]) -> str | None:
    _ensure_project_env_loaded()
    for name in names:
        value = (os.getenv(name) or "").strip()
        if value:
            return value
    return None


def _resolve_openrouter_api_key() -> str:
    base_url = _resolve_openrouter_base_url()
    model = _resolve_team_model()
    provider_hint = (_first_non_empty_env(["AUTOGEN_PROVIDER", "AUTOGEN_LLM_PROVIDER"]) or "").lower()
    candidates: list[str]
    if provider_hint == "minimax" or is_minimax_chat_request(base_url, model):
        candidates = [
            "AUTOGEN_MINIMAX_API_KEY",
            "MINIMAX_API_KEY",
            "MCP_LLM_MINIMAX_API_KEY",
            "MCP_LLM_OPENAI_API_KEY",
            "OPENAI_API_KEY",
        ]
    else:
        candidates = [
            "AUTOGEN_OPENROUTER_API_KEY",
            "OPENROUTER_API_KEY",
            "MCP_LLM_OPENROUTER_API_KEY",
            "MCP_LLM_OPENAI_API_KEY",
            "OPENAI_API_KEY",
        ]
    api_key = _first_non_empty_env(
        candidates
    )
    if not api_key:
        raise RuntimeError("No compatible API key is configured for the AutoGen team.")
    return api_key


def _resolve_openrouter_base_url() -> str:
    provider_hint = (_first_non_empty_env(["AUTOGEN_PROVIDER", "AUTOGEN_LLM_PROVIDER"]) or "").lower()
    if provider_hint == "minimax":
        candidates = [
            "AUTOGEN_MINIMAX_BASE_URL",
            "AUTOGEN_BASE_URL",
            "MCP_LLM_BASE_URL",
            "OPENAI_API_BASE",
            "AUTOGEN_OPENROUTER_BASE_URL",
            "OPENROUTER_API_BASE",
        ]
    elif provider_hint == "openrouter":
        candidates = [
            "AUTOGEN_OPENROUTER_BASE_URL",
            "OPENROUTER_API_BASE",
            "AUTOGEN_BASE_URL",
            "MCP_LLM_BASE_URL",
            "OPENAI_API_BASE",
            "AUTOGEN_MINIMAX_BASE_URL",
        ]
    else:
        candidates = [
            "AUTOGEN_BASE_URL",
            "AUTOGEN_OPENROUTER_BASE_URL",
            "AUTOGEN_MINIMAX_BASE_URL",
            "OPENROUTER_API_BASE",
            "MCP_LLM_BASE_URL",
            "OPENAI_API_BASE",
        ]
    configured = _first_non_empty_env(candidates)
    if configured:
        return configured.rstrip("/")
    if provider_hint == "minimax":
        return "https://api.minimax.io/v1"
    return "https://openrouter.ai/api/v1"


def _resolve_team_model() -> str:
    provider_hint = (_first_non_empty_env(["AUTOGEN_PROVIDER", "AUTOGEN_LLM_PROVIDER"]) or "").lower()
    if provider_hint == "minimax":
        candidates = [
            "AUTOGEN_TEAM_MODEL",
            "AUTOGEN_MINIMAX_MODEL",
            "MCP_LLM_MODEL_NAME",
            "OPENAI_MODEL",
            "OPENROUTER_AUTOGEN_MODEL",
        ]
    elif provider_hint == "openrouter":
        candidates = [
            "AUTOGEN_TEAM_MODEL",
            "OPENROUTER_AUTOGEN_MODEL",
            "MCP_LLM_MODEL_NAME",
            "OPENAI_MODEL",
            "AUTOGEN_MINIMAX_MODEL",
        ]
    else:
        candidates = [
            "AUTOGEN_TEAM_MODEL",
            "AUTOGEN_MINIMAX_MODEL",
            "OPENROUTER_AUTOGEN_MODEL",
            "MCP_LLM_MODEL_NAME",
            "OPENAI_MODEL",
        ]
    model = _first_non_empty_env(candidates)
    if model:
        return model
    base_url = _resolve_openrouter_base_url()
    if provider_hint == "minimax" or is_minimax_chat_request(base_url, None):
        return "MiniMax-M2.5"
    return "x-ai/grok-4.1-fast"


def _build_model_client(*, temperature: float, max_tokens: int = 2200, timeout: int = 180) -> OpenAIChatCompletionClient:
    base_url = _resolve_openrouter_base_url()
    model = _resolve_team_model()
    minimax_compat = is_minimax_chat_request(base_url, model)
    effective_temperature = (
        normalize_temperature_for_minimax(temperature)
        if minimax_compat
        else temperature
    )
    return OpenAIChatCompletionClient(
        model=model,
        model_info={
            "vision": False,
            "function_calling": True,
            "json_output": False,
            "family": "unknown",
            "structured_output": False,
        },
        api_key=_resolve_openrouter_api_key(),
        base_url=base_url,
        temperature=effective_temperature,
        timeout=timeout,
        max_retries=3,
        max_tokens=max_tokens,
        stop=["<eos>"],
        top_p=1,
        add_name_prefixes=minimax_compat,
        include_name_in_message=not minimax_compat,
    )


def _buffered_context() -> BufferedChatCompletionContext:
    return BufferedChatCompletionContext(buffer_size=20)


def mission_brief(vision: str, target_user: str, business_outcome: str) -> str:
    """Create a concise mission brief for the team."""
    return (
        f"Vision: {vision}\n"
        f"Target user: {target_user}\n"
        f"Business outcome: {business_outcome}\n"
        "Leadership note: align every decision to user value, speed of learning, and product quality."
    )


def rally_message(outcome: str, milestone: str, team_strength: str) -> str:
    """Generate a motivational alignment message."""
    return (
        f"Outcome to win: {outcome}. "
        f"Current milestone: {milestone}. "
        f"Team strength to lean on: {team_strength}. "
        "Push for clarity, speed, and quality together."
    )


def engineer_calculator(a: float, b: float, operator: str) -> str:
    """Basic calculator for implementation estimates."""
    try:
        if operator == "+":
            return str(a + b)
        if operator == "-":
            return str(a - b)
        if operator == "*":
            return str(a * b)
        if operator == "/":
            if b == 0:
                return "Error: Division by zero"
            return str(a / b)
        return "Error: Invalid operator. Use +, -, *, or /"
    except Exception as exc:
        return f"Error: {exc}"


def implementation_plan(feature_name: str, dependencies: str, risks: str) -> str:
    """Summarize the delivery approach for a feature."""
    return (
        f"Implementation plan for {feature_name}:\n"
        f"1. Confirm dependencies: {dependencies}.\n"
        "2. Implement the smallest end-to-end slice first.\n"
        "3. Add observability, tests, and error handling.\n"
        f"4. Watch these risks: {risks}."
    )


def requirement_record(feature: str, user_problem: str, success_metric: str, constraints: str) -> str:
    """Capture a product requirement in a reusable format."""
    return (
        f"Feature: {feature}\n"
        f"User problem: {user_problem}\n"
        f"Success metric: {success_metric}\n"
        f"Constraints: {constraints}"
    )


def prioritize_opportunity(opportunity: str, impact: int, effort: int, risk: int) -> str:
    """Simple prioritization helper for PM decisions."""
    score = impact * 2 - effort - risk
    if score >= 8:
        priority = "Now"
    elif score >= 4:
        priority = "Next"
    else:
        priority = "Later"
    return f"Opportunity: {opportunity} | Priority: {priority} | Score: {score}"


def financial_projection(
    revenue_streams: str,
    cost_structure: str,
    projection_horizon: str,
    key_assumptions: str,
) -> str:
    """Create a concise finance view of revenue, cost, and unit economics assumptions."""
    return (
        "Financial projection summary:\n"
        f"Revenue streams: {revenue_streams}\n"
        f"Cost structure: {cost_structure}\n"
        f"Projection horizon: {projection_horizon}\n"
        f"Key assumptions: {key_assumptions}"
    )


def business_case(
    initiative: str,
    expected_benefit: str,
    estimated_cost: str,
    financial_risk: str,
) -> str:
    """Summarize the business case for an initiative."""
    return (
        f"Business case for {initiative}:\n"
        f"Expected benefit: {expected_benefit}\n"
        f"Estimated cost: {estimated_cost}\n"
        f"Financial risk: {financial_risk}\n"
        "Decision lens: recommend proceed, revise, or stop based on ROI, payback, and downside exposure."
    )


def architecture_decision(decision: str, context: str, consequences: str) -> str:
    """Summarize an architecture decision with rationale."""
    return (
        f"Decision: {decision}\n"
        f"Context: {context}\n"
        f"Consequences: {consequences}"
    )


def component_contract(component: str, responsibilities: str, inputs: str, outputs: str) -> str:
    """Create an interface contract for a component."""
    return (
        f"Component: {component}\n"
        f"Responsibilities: {responsibilities}\n"
        f"Inputs: {inputs}\n"
        f"Outputs: {outputs}"
    )


def experience_brief(persona: str, journey_stage: str, desired_emotion: str, accessibility_need: str) -> str:
    """Define target UX outcomes for a user moment."""
    return (
        f"Persona: {persona}\n"
        f"Journey stage: {journey_stage}\n"
        f"Desired emotion: {desired_emotion}\n"
        f"Accessibility priority: {accessibility_need}"
    )


def ux_review_checklist(surface: str, primary_goal: str, main_risk: str) -> str:
    """Produce a focused UX review checklist."""
    return (
        f"Review {surface} for clarity of {primary_goal}.\n"
        "Check hierarchy, copy clarity, feedback states, accessibility, and error recovery.\n"
        f"Main UX risk to watch: {main_risk}."
    )


def go_to_market_plan(
    target_customer: str,
    tam: str,
    som: str,
    campaign_strategy: str,
) -> str:
    """Summarize a GTM plan grounded in TAM, SOM, and campaign strategy."""
    return (
        "Go-to-market plan:\n"
        f"Target customer: {target_customer}\n"
        f"TAM: {tam}\n"
        f"SOM: {som}\n"
        f"Campaign strategy: {campaign_strategy}"
    )


def market_growth_frame(
    market_category: str,
    positioning: str,
    acquisition_channels: str,
    launch_motion: str,
) -> str:
    """Frame marketing strategy around category, positioning, and launch motion."""
    return (
        f"Market category: {market_category}\n"
        f"Positioning: {positioning}\n"
        f"Acquisition channels: {acquisition_channels}\n"
        f"Launch motion: {launch_motion}"
    )


def test_plan(feature_name: str, requirements: str, risks: str) -> str:
    """Create a targeted QA plan."""
    return (
        f"Test plan for {feature_name}:\n"
        f"Requirements to validate: {requirements}.\n"
        "Cover happy path, edge cases, failure handling, and regression scope.\n"
        f"Highest risks: {risks}."
    )


def quality_gate(requirements_met: bool, ux_validated: bool, defects_open: int) -> str:
    """Determine whether the release should pass, fail, or remain conditional."""
    if requirements_met and ux_validated and defects_open == 0:
        status = "PASS"
    elif defects_open <= 2 and requirements_met:
        status = "CONDITIONAL"
    else:
        status = "FAIL"
    return (
        f"Quality gate: {status} | requirements_met={requirements_met} "
        f"| ux_validated={ux_validated} | defects_open={defects_open}"
    )


def user_feedback(persona: str, likes: str, frustrations: str, missing_value: str) -> str:
    """Summarize product feedback from a user perspective."""
    return (
        f"Persona: {persona}\n"
        f"What works: {likes}\n"
        f"What frustrates the user: {frustrations}\n"
        f"Missing value: {missing_value}"
    )


def acceptance_recommendation(severity: str, confidence: str, recommendation: str) -> str:
    """Recommend accept, revise, or reject from the user perspective."""
    return f"Acceptance recommendation: {recommendation} | Severity: {severity} | Confidence: {confidence}"


def _candidate_proxy_bases() -> list[str]:
    configured = (
        os.getenv("CATBOT_PROXY_BASE_URL")
        or os.getenv("PROXY_BASE_URL")
        or os.getenv("TELEGRAM_BACKEND_URL")
        or ""
    ).strip().rstrip("/")
    defaults = [
        "https://127.0.0.1:8002",
        "https://localhost:8002",
        "http://127.0.0.1:8002",
        "http://localhost:8002",
    ]
    ordered: list[str] = []
    if configured:
        ordered.append(configured)
    for item in defaults:
        if item not in ordered:
            ordered.append(item)
    return ordered


def _proxy_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    agent_secret = (
        os.getenv("AUTOGEN_TEAM_SECRET")
        or os.getenv("CATBOT_AGENT_SECRET")
        or os.getenv("MCP_BROWSER_SERVER_SECRET")
        or ""
    ).strip()
    if agent_secret:
        headers["X-Agent-Secret"] = agent_secret
    return headers


def _post_json(path_suffix: str, payload: dict[str, Any], timeout: int) -> object:
    last_error: str | None = None
    body = json.dumps(payload).encode("utf-8")
    headers = _proxy_headers()
    for base in _candidate_proxy_bases():
        request = urllib.request.Request(
            f"{base}{path_suffix}",
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            if base.startswith("https://"):
                context = ssl._create_unverified_context()
                with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
                    return json.loads(response.read().decode("utf-8"))
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code} from {base}"
        except Exception as exc:
            last_error = f"{base}: {exc}"
    return {"success": False, "message": last_error or "Proxy request failed."}


def _get_json(path_suffix: str, params: dict[str, Any], timeout: int) -> object:
    last_error: str | None = None
    encoded_params = urllib.parse.urlencode(
        [(key, value) for key, value in params.items() if value is not None and value != ""],
        doseq=True,
    )
    headers = _proxy_headers()
    for base in _candidate_proxy_bases():
        url = f"{base}{path_suffix}"
        if encoded_params:
            url = f"{url}?{encoded_params}"
        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            if base.startswith("https://"):
                context = ssl._create_unverified_context()
                with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
                    return json.loads(response.read().decode("utf-8"))
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code} from {base}"
        except Exception as exc:
            last_error = f"{base}: {exc}"
    return {"success": False, "message": last_error or "Proxy request failed."}


def _truncate_text(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(limit - 3, 0)].rstrip() + "..."


def webSearch(query: str) -> str:
    """Search the web for current external information via the local CATBot proxy."""
    data = _get_json("/v1/proxy/search", {"query": query}, 60)
    if isinstance(data, dict):
        if data.get("success") is False:
            return str(data.get("message") or data.get("detail") or data)
        results = data.get("results") or []
        if not isinstance(results, list) or not results:
            return "No search results found."
        lines: list[str] = []
        for index, item in enumerate(results[:5], start=1):
            if not isinstance(item, dict):
                continue
            title = _truncate_text(item.get("title") or "Untitled result", 160)
            snippet = _truncate_text(item.get("snippet") or "", 280)
            url = _truncate_text(item.get("url") or "", 300)
            date = _truncate_text(item.get("date") or "", 40)
            date_suffix = f" | Date: {date}" if date else ""
            lines.append(f"{index}. {title}\nURL: {url}{date_suffix}\nSnippet: {snippet}")
        if lines:
            return "Search results:\n" + "\n\n".join(lines)
    return _truncate_text(data, 12000)


def scrapeWebsite(
    url: str = "",
    urls: Sequence[str] | None = None,
    render_js: bool = False,
    render_engine: str = "auto",
    wait_for_selector: str = "",
    js_wait_ms: int = 2200,
) -> str:
    """Fetch website content via the local CATBot proxy, with optional retry URLs and JS rendering."""
    candidate_urls = [u.strip() for u in (urls or []) if isinstance(u, str) and u.strip()]
    if url.strip():
        candidate_urls.insert(0, url.strip())
    # Preserve order while dropping duplicates.
    deduped_urls = list(dict.fromkeys(candidate_urls))
    if not deduped_urls:
        return "url or urls is required."
    payload: dict[str, Any] = {"render_js": render_js, "render_engine": render_engine, "js_wait_ms": js_wait_ms}
    if deduped_urls:
        if len(deduped_urls) == 1:
            payload["url"] = deduped_urls[0]
        else:
            payload["urls"] = deduped_urls
    if wait_for_selector:
        payload["wait_for_selector"] = wait_for_selector
    data = _post_json("/v1/proxy/fetch", payload, 180)
    if isinstance(data, dict):
        if data.get("success") is False:
            return str(data.get("message") or data.get("detail") or data)
        resolved_url = _truncate_text(data.get("url") or deduped_urls[0], 300)
        title = _truncate_text(data.get("title") or "", 200)
        content = _truncate_text(data.get("content") or data.get("text") or data.get("message") or "", 12000)
        header = [f"Fetched URL: {resolved_url}"] if resolved_url else []
        if title:
            header.append(f"Title: {title}")
        if content:
            header.append(f"Content:\n{content}")
        return "\n".join(header) if header else _truncate_text(data, 12000)
    return _truncate_text(data, 12000)


def runBrowserAgent(task: str) -> str:
    """Run a browser automation task via the local CATBot proxy."""
    data = _post_json("/v1/proxy/browser-agent", {"task": task}, 900)
    if isinstance(data, dict):
        if data.get("success") is False:
            return str(data.get("error") or data.get("message") or data)
        result = data.get("result") or data.get("message") or data.get("output") or data
        return _truncate_text(result, 20000)
    return _truncate_text(data, 20000)


def runDeepResearch(researchTask: str, maxParallelBrowsers: int = 3) -> str:
    """Run a multi-step deep research task via the local CATBot proxy."""
    payload = {
        "researchTask": researchTask,
        "maxParallelBrowsers": maxParallelBrowsers,
    }
    data = _post_json("/v1/proxy/deep-research", payload, 1800)
    if isinstance(data, dict):
        if data.get("success") is False:
            return str(data.get("error") or data.get("message") or data)
        report = data.get("report") or data.get("result") or data.get("message") or data.get("output") or data
        return _truncate_text(report, 24000)
    return _truncate_text(data, 24000)


def codex_cli_task(prompt: str) -> str:
    """Run Codex CLI through the local CATBot proxy in an isolated scratch/autogen workspace snapshot."""
    data = _post_json("/v1/proxy/codex", {"prompt": prompt}, 3600)
    if isinstance(data, dict):
        if data.get("success") is False:
            return str(data.get("detail") or data.get("error") or data.get("message") or data)[:12000]
        exit_code = data.get("exitCode")
        timed_out = data.get("timedOut")
        duration_ms = data.get("durationMs")
        summary_file = data.get("summaryFile") or "(none)"
        last_message_file = data.get("lastMessageFile") or "(none)"
        workspace_dir = data.get("workspaceDir") or "(unknown)"
        workspace_mode = data.get("workspaceMode") or "(unknown)"
        stdout = str(data.get("stdout") or "").strip()
        stderr = str(data.get("stderr") or "").strip()
        parts = [
            f"Codex CLI finished with exit_code={exit_code}, timed_out={timed_out}, duration_ms={duration_ms}.",
            f"Workspace mode: {workspace_mode}.",
            f"Workspace dir: {workspace_dir}.",
            f"Summary file: {summary_file}.",
            f"Last message file: {last_message_file}.",
        ]
        if stdout:
            parts.append(f"stdout:\n{stdout[:8000]}")
        if stderr:
            parts.append(f"stderr:\n{stderr[:4000]}")
        return "\n".join(parts)[:16000]
    return str(data)[:16000]


def _shared_research_tools() -> list[Any]:
    return [webSearch, scrapeWebsite, runBrowserAgent, runDeepResearch]


def _role_tools(*role_specific_tools: Any, include_codex_cli: bool = False) -> list[Any]:
    tools = list(role_specific_tools)
    tools.extend(_shared_research_tools())
    if include_codex_cli:
        tools.append(codex_cli_task)
    return tools


def _latest_participant_source(history: Sequence[Any]) -> str | None:
    for item in reversed(history):
        source = getattr(item, "source", None)
        if source in PARTICIPANT_ORDER:
            return str(source)
    return None


def select_company_speaker(history: Sequence[Any]) -> str | None:
    latest_source = _latest_participant_source(history)
    if latest_source is None:
        return "ceo_agent"
    if latest_source == "ceo_agent":
        return "product_manager_agent"
    if latest_source == "product_manager_agent":
        return "cfo_agent"
    if latest_source == "cfo_agent":
        return "chief_marketer_agent"
    if latest_source == "chief_marketer_agent":
        return "architect_agent"
    if latest_source == "architect_agent":
        return "ux_designer_agent"
    if latest_source == "ux_designer_agent":
        return "lead_engineer_agent"
    if latest_source == "lead_engineer_agent":
        return "qa_officer_agent"
    if latest_source == "qa_officer_agent":
        return "user_proxy_agent"
    if latest_source == "user_proxy_agent":
        return "ceo_agent"
    return "ceo_agent"


def _research_prompt(additional_guidance: str) -> str:
    return (
        additional_guidance
        + " When current market, competitor, product, pricing, customer, vendor, or technical evidence is needed, "
        "use CATBot research tools directly. Start with webSearch to locate sources, use scrapeWebsite to extract "
        "details from promising URLs, and escalate to runBrowserAgent or runDeepResearch when the information is "
        "behind dynamic pages or requires multi-source synthesis. Ground claims in the evidence you gathered and "
        "label assumptions when evidence is incomplete."
    )


def _build_role_agents() -> list[AssistantAgent]:
    return [
        AssistantAgent(
            "ceo_agent",
            _build_model_client(temperature=0.4, max_tokens=1200),
            tools=_role_tools(mission_brief, rally_message),
            description="Owns the product vision, business outcome, and final readiness decision.",
            system_message=(
                "You are the CEO of a virtual product company. On your first turn, do not solve the whole task. "
                "State the product vision, target customer, and business outcome in a short framing note, then leave "
                "detailed scoping to product_manager_agent. After other roles contribute, make business trade-off "
                "decisions and final readiness calls. Only say TERMINATE when qa_officer_agent has confirmed quality "
                "and user_proxy_agent has confirmed the experience is acceptable."
            ),
            model_context=_buffered_context(),
            reflect_on_tool_use=False,
            max_tool_iterations=2,
            tool_call_summary_format="{result}",
        ),
        AssistantAgent(
            "product_manager_agent",
            _build_model_client(temperature=0.3, max_tokens=1600),
            tools=_role_tools(requirement_record, prioritize_opportunity),
            description="Owns problem framing, assumptions, requirements, and prioritization.",
            system_message=_research_prompt(
                "You are the Product Manager in a virtual software company. Translate the CEO vision into product "
                "requirements, assumptions, scope, acceptance criteria, and priorities. Your job is to turn the CEO "
                "framing into a concrete product brief that the CFO, Chief Marketer, architect, UX designer, and "
                "engineer can act on. For market sizing, user needs, competitor analysis, and product research, gather "
                "external evidence before making claims. State assumptions clearly and make the next required role obvious. "
                "Do not say TERMINATE."
            ),
            model_context=_buffered_context(),
            reflect_on_tool_use=False,
            max_tool_iterations=4,
            tool_call_summary_format="{result}",
        ),
        AssistantAgent(
            "cfo_agent",
            _build_model_client(temperature=0.2, max_tokens=1600),
            tools=_role_tools(financial_projection, business_case),
            description="Owns revenue and cost projections, economic assumptions, and business-case quality.",
            system_message=_research_prompt(
                "You are the Chief Financial Officer in a virtual software company. Translate the product brief into "
                "revenue drivers, cost structure, key assumptions, pricing logic, payback logic, and a defensible "
                "business case. Call out financial risks, dependency assumptions, and what must be true for the "
                "initiative to make economic sense. For TAM, pricing benchmarks, budget assumptions, market data, and "
                "vendor costs, gather external evidence before making claims. State assumptions clearly and make the "
                "next required role obvious, usually chief_marketer_agent unless the economics block the opportunity. "
                "Do not say TERMINATE."
            ),
            model_context=_buffered_context(),
            reflect_on_tool_use=False,
            max_tool_iterations=4,
            tool_call_summary_format="{result}",
        ),
        AssistantAgent(
            "chief_marketer_agent",
            _build_model_client(temperature=0.4, max_tokens=1600),
            tools=_role_tools(go_to_market_plan, market_growth_frame),
            description="Owns the go-to-market plan, TAM and SOM framing, positioning, and campaign strategy.",
            system_message=_research_prompt(
                "You are the Chief Marketer in a virtual software company. Build a go-to-market plan grounded in TAM, "
                "SOM, positioning, audience segmentation, acquisition channels, launch sequencing, and campaign "
                "strategy. Use the product brief and CFO business case to explain how the company can win attention "
                "and convert demand into revenue. For TAM, SOM, competitor positioning, channel benchmarks, and "
                "customer research, gather external evidence before making claims. State assumptions clearly and make "
                "the next required role obvious, typically architect_agent, ux_designer_agent, or lead_engineer_agent "
                "depending on what needs to be made concrete next. Do not say TERMINATE."
            ),
            model_context=_buffered_context(),
            reflect_on_tool_use=False,
            max_tool_iterations=4,
            tool_call_summary_format="{result}",
        ),
        AssistantAgent(
            "architect_agent",
            _build_model_client(temperature=0.2, max_tokens=1600),
            tools=_role_tools(architecture_decision, component_contract),
            description="Owns system design, interfaces, constraints, and technology trade-offs.",
            system_message=_research_prompt(
                "You are the Architect in a virtual software company. Define the system structure, data flow, "
                "interfaces, constraints, and technology choices needed to satisfy the product requirements. Keep "
                "designs practical, implementation-ready, and specific enough for engineering execution. When third-party "
                "platform constraints, integration details, browser behavior, or external technical documentation matter, "
                "gather external evidence before making claims. Do not say TERMINATE."
            ),
            model_context=_buffered_context(),
            reflect_on_tool_use=False,
            max_tool_iterations=4,
            tool_call_summary_format="{result}",
        ),
        AssistantAgent(
            "ux_designer_agent",
            _build_model_client(temperature=0.4, max_tokens=1600),
            tools=_role_tools(experience_brief, ux_review_checklist),
            description="Owns the user journey, interaction quality, tone, and accessibility direction.",
            system_message=(
                "You are the UX Designer in a virtual software company. Define how the product should feel, what users "
                "should understand at each step, and how the interface can reduce friction while increasing trust and "
                "delight. Use tools when they materially improve the recommendation. Keep recommendations actionable for "
                "architecture and engineering. Do not say TERMINATE."
            ),
            model_context=_buffered_context(),
            reflect_on_tool_use=False,
            max_tool_iterations=2,
            tool_call_summary_format="{result}",
        ),
        AssistantAgent(
            "lead_engineer_agent",
            _build_model_client(temperature=0.2, max_tokens=1800),
            tools=_role_tools(engineer_calculator, implementation_plan, include_codex_cli=True),
            description="Turns product direction into implementation plans and concrete delivery steps.",
            system_message=(
                "You are the Lead Engineer in a virtual software company. Turn the CEO vision, product requirements, "
                "architecture, and UX direction into a practical implementation plan. Focus on delivery sequence, "
                "technical risks, and execution details. Use tools when they speed up validation or evidence gathering. "
                "When concrete CATBot code changes are needed, use codex_cli_task to produce them inside the isolated "
                "scratch/autogen Codex workspace snapshot rather than the live CATBot repo. Raise blockers to the "
                "specific role that can resolve them. Do not say TERMINATE."
            ),
            model_context=_buffered_context(),
            reflect_on_tool_use=False,
            max_tool_iterations=3,
            tool_call_summary_format="{result}",
        ),
        AssistantAgent(
            "qa_officer_agent",
            _build_model_client(temperature=0.1, max_tokens=1400),
            tools=_role_tools(test_plan, quality_gate),
            description="Owns bug finding, validation against requirements, and release readiness.",
            system_message=(
                "You are the Quality Assurance Officer in a virtual software company. Verify that the product meets the "
                "defined requirements, architecture constraints, UX intent, and overall outcome. State a release gate "
                "clearly. When you find defects or gaps, direct the issue to the responsible role. Do not say TERMINATE; "
                "hand back to ceo_agent when quality is acceptable."
            ),
            model_context=_buffered_context(),
            reflect_on_tool_use=False,
            max_tool_iterations=2,
            tool_call_summary_format="{result}",
        ),
        AssistantAgent(
            "user_proxy_agent",
            _build_model_client(temperature=0.4, max_tokens=1200),
            tools=_role_tools(user_feedback, acceptance_recommendation),
            description="Represents the end user and provides direct feedback to the company.",
            system_message=(
                "You are the User Proxy in a virtual software company. React like a thoughtful but demanding user. "
                "Highlight confusion, friction, trust issues, missing value, and what feels genuinely useful. Route "
                "feedback to the most relevant role and give a clear acceptance recommendation. Do not say TERMINATE."
            ),
            model_context=_buffered_context(),
            reflect_on_tool_use=False,
            max_tool_iterations=2,
            tool_call_summary_format="{result}",
        ),
    ]


def build_virtual_product_company_team() -> SelectorGroupChat:
    participants = _build_role_agents()
    selector_prompt = (
        "You are selecting the next speaker in a virtual software company. Valid participant ids are exactly: "
        "ceo_agent, product_manager_agent, cfo_agent, chief_marketer_agent, architect_agent, "
        "ux_designer_agent, lead_engineer_agent, qa_officer_agent, user_proxy_agent. Return exactly one of those ids "
        "and nothing else.\n\n"
        "Routing rules:\n"
        "1. If the conversation only contains the user task, choose ceo_agent.\n"
        "2. If the latest non-user message is from ceo_agent and the task has not yet been turned into requirements, "
        "choose product_manager_agent.\n"
        "3. After product_manager_agent, choose cfo_agent when financial viability, revenue, cost, or business case "
        "work is needed.\n"
        "4. After cfo_agent, choose chief_marketer_agent for TAM, SOM, positioning, and GTM planning.\n"
        "5. After chief_marketer_agent, choose the role needed for the next concrete product artifact: architect_agent "
        "for system design, ux_designer_agent for user experience, or lead_engineer_agent if implementation planning "
        "can start immediately.\n"
        "6. After architect_agent or ux_designer_agent, choose lead_engineer_agent when implementation planning is next.\n"
        "7. After lead_engineer_agent, choose qa_officer_agent.\n"
        "8. After qa_officer_agent, choose user_proxy_agent if user feedback is still needed; otherwise choose ceo_agent.\n"
        "9. After user_proxy_agent, choose ceo_agent.\n"
        "10. Avoid repeating the same speaker twice in a row unless the last message explicitly says that same role must "
        "continue unfinished work.\n\n"
        "{history}\n\nReturn only one participant id from {participants}."
    )
    termination = OrTerminationCondition(
        TextMentionTermination("TERMINATE"),
        MaxMessageTermination(max_messages=24, include_agent_event=False),
    )
    return SelectorGroupChat(
        participants=participants,
        model_client=_build_model_client(temperature=0.0, max_tokens=32, timeout=45),
        name=TEAM_NAME,
        description="A virtual product company with leadership, product, finance, marketing, architecture, UX, engineering, QA, and user-feedback agents.",
        termination_condition=termination,
        selector_prompt=selector_prompt,
        allow_repeated_speaker=False,
        max_selector_attempts=1,
        selector_func=select_company_speaker,
        emit_team_events=True,
        model_client_streaming=False,
        model_context=_buffered_context(),
    )


def export_virtual_product_company_team_config(path: Path | None = None) -> Path:
    """Export the Python-defined AutoGen team to JSON for tools like AutoGen Studio."""
    export_path = path or TEAM_CONFIG_EXPORT_FILE
    export_path.parent.mkdir(parents=True, exist_ok=True)
    team = build_virtual_product_company_team()
    config = team.dump_component().model_dump(mode="json")
    export_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return export_path

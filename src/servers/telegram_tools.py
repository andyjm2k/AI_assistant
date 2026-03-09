"""
Telegram tool parsing and execution for parity with the HTML client.
Used only by the proxy Telegram chat endpoint; does not modify the web client.
Todo list uses persistent todo_store when context provides todo_user_key.
"""

import ast
import asyncio
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Optional persistent todo store (used when todo_user_key is in context)
try:
    from src.servers import todo_store as _todo_store_module
except ImportError:
    _todo_store_module = None

# Maximum length for calculate expression to avoid abuse
CALC_EXPR_MAX_LEN = 200
# Allowed characters for safe calculate (numbers, spaces, + - * / ( ) .)
CALC_ALLOWED_RE = re.compile(r"^[\d\s+\-*/().]+$")
_TOOL_CALL_BLOCK_RE = (
    r"<(?:tool|tool_call)>[\s\S]*?</(?:tool|tool_call)>\s*"
    r"<parameters>[\s\S]*?</parameters>"
)
_TOOL_CALL_BLOCK_PATTERN = re.compile(_TOOL_CALL_BLOCK_RE, re.IGNORECASE)
_STANDALONE_TOOL_CALL_PATTERN = re.compile(rf"^\s*(?:{_TOOL_CALL_BLOCK_RE})\s*$", re.IGNORECASE)

_TELEGRAM_TOOL_NAME_ALIASES = {
    "read_file": "readFile",
    "write_file": "writeFile",
    "list_files": "listFiles",
    "save_to_file": "writeFile",
    "saveToFile": "writeFile",
    "health_check": "healthCheck",
    "run_health_check": "healthCheck",
}


def _canonicalize_telegram_tool_name(name: Any) -> str:
    raw = str(name or "").strip()
    if not raw:
        return ""
    return _TELEGRAM_TOOL_NAME_ALIASES.get(raw, raw)


def _get_list_files_tool_max_entries() -> int:
    """Return max entries rendered in list-files replies."""
    raw = (os.getenv("LIST_FILES_TOOL_MAX_ENTRIES", "60") or "60").strip()
    try:
        parsed = int(raw)
    except ValueError:
        parsed = 60
    return max(1, parsed)


def _format_list_files_message(files: List[Dict[str, Any]]) -> str:
    """Render a bounded file list to reduce token pressure in chat loops."""
    if not files:
        return "No files."
    limit = _get_list_files_tool_max_entries()
    shown = files[:limit]
    lines = []
    for item in shown:
        name = str(item.get("name", ""))
        is_dir = str(item.get("type", "")).lower() == "directory"
        if is_dir:
            lines.append(f"- {name}/ [dir]")
        else:
            lines.append(f"- {name}")
    remaining = max(0, len(files) - len(shown))
    if remaining > 0:
        lines.append(f"- ... and {remaining} more files.")
    return "Files:\n" + "\n".join(lines)


def _log_tool_invocation(name: str, arguments: Dict[str, Any], conversation_id: str) -> None:
    """Print a consistent tool invocation log line from Telegram tool execution."""
    try:
        args_text = json.dumps(arguments if isinstance(arguments, dict) else {}, ensure_ascii=False, default=str)
    except Exception:
        args_text = str(arguments)
    print(f"[TOOL][telegram:{conversation_id}] name={name} args={args_text}", flush=True)


def parse_telegram_tool_response(content: str) -> Optional[Dict[str, Any]]:
    """
    Parse assistant content for a single tool call in the same format as the web client.
    Looks for <tool>name</tool><parameters>{...}</parameters> or <tool_call>name</tool_call> variations.
    Strips fenced code blocks before matching so example snippets are not executed.
    More lenient than before - extracts tool calls even if there's surrounding text (handles cases
    where LLM outputs tool calls as text after task execution starts).
    Optionally supports JSON-style and contentPrompt fallbacks.
    Returns a dict with keys 'name' and 'arguments' (JSON string), or None if no valid tool call.
    """
    if not content or not isinstance(content, str):
        return None
    # Strip fenced code blocks to avoid executing examples
    content_without_code = re.sub(r"```[\s\S]*?```", "", content)
    # XML format: support both <tool> and <tool_call> tags (handle malformed XML where opening/closing tags differ)
    # Try <tool> first (preferred format)
    tool_match = re.search(r"<tool>(.*?)</tool>", content_without_code)
    if not tool_match:
        # Fallback to <tool_call> if <tool> not found
        tool_match = re.search(r"<tool_call>(.*?)</tool_call>", content_without_code)
    if not tool_match:
        # Also try mixed format: <tool_call>...</tool> (handle malformed XML)
        tool_match = re.search(r"<tool_call>(.*?)</tool>", content_without_code)
    if not tool_match:
        # Or <tool>...</tool_call>
        tool_match = re.search(r"<tool>(.*?)</tool_call>", content_without_code)
    
    params_match = re.search(r"<parameters>([\s\S]*?)</parameters>", content_without_code)
    if tool_match and params_match:
        try:
            # Extract tool call even if there's some surrounding text
            # This handles cases where LLM outputs tool calls as text after task execution
            tool_name = tool_match.group(1).strip()
            params_str = params_match.group(1).strip()
            # Validate that we have a valid tool name and parameters
            if not tool_name:
                return None
            params = json.loads(params_str)
            # Return the parsed tool call regardless of surrounding text
            # The strict leading/trailing check was too restrictive and prevented
            # tool calls from being executed when LLM outputs them as text
            return {"name": tool_name, "arguments": json.dumps(params) if isinstance(params, dict) else params_str}
        except (json.JSONDecodeError, ValueError) as e:
            # Log parsing errors for debugging
            print(f"[TELEGRAM_TOOLS] Error parsing tool call: {e}")
            pass
    # JSON-style: content is JSON object
    trimmed = content.strip()
    if trimmed.startswith("{") or trimmed.startswith("["):
        try:
            obj = json.loads(trimmed)
            if isinstance(obj, dict):
                if obj.get("action") and obj.get("contentPrompt") is not None:
                    return {
                        "name": obj.get("action", "runWorkflow"),
                        "arguments": json.dumps({"contentPrompt": obj["contentPrompt"]}),
                    }
                if obj.get("name") and "arguments" in obj:
                    args = obj["arguments"]
                    return {
                        "name": obj["name"],
                        "arguments": args if isinstance(args, str) else json.dumps(args),
                    }
        except json.JSONDecodeError:
            pass
    if "contentPrompt" in trimmed and trimmed.strip():
        return {"name": "runWorkflow", "arguments": trimmed}
    return None


def reply_looks_like_tool_call(content: str) -> bool:
    """
    Return True if content looks like raw tool-call XML and should not be shown to the user.
    Used to fall back to tool result when the LLM returns only a tool call and no final text.
    """
    if not content or not isinstance(content, str):
        return False
    # Only treat standalone tool XML as a raw tool call. Mixed natural-language replies
    # that merely include tool markup should be delivered to the user.
    return bool(_STANDALONE_TOOL_CALL_PATTERN.match(content.strip()))


def strip_tool_call_markup(content: str) -> str:
    """
    Remove embedded tool-call XML blocks from a mixed assistant reply.
    Returns cleaned text; empty string if no user-facing text remains.
    """
    if not content or not isinstance(content, str):
        return ""
    cleaned = _TOOL_CALL_BLOCK_PATTERN.sub(" ", content)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def tool_result_looks_like_error(message: str) -> bool:
    """
    Return True if a tool result message looks like an error and should not be shown raw to the user.
    Used to show a friendly fallback in Telegram when a tool failed (e.g. 404, 500, fetch failed).
    """
    if not message or not isinstance(message, str):
        return False
    lower = message.strip().lower()
    if "500:" in message or "404" in message or "403" in message:
        return True
    if "failed to fetch" in lower or "client error" in lower or "not found" in lower:
        return True
    if "http status" in lower or "connection error" in lower or "timeout" in lower:
        return True
    return False


def _safe_calculate(expression: str) -> Optional[float]:
    """
    Evaluate a simple math expression safely. Only allows numbers and + - * / ( ).
    Returns None on invalid or unsafe input.
    """
    if not expression or len(expression) > CALC_EXPR_MAX_LEN:
        return None
    expr = expression.strip()
    if not CALC_ALLOWED_RE.match(expr):
        return None
    try:
        tree = ast.parse(expr, mode="eval")
        if not isinstance(tree.body, (ast.BinOp, ast.UnaryOp, ast.Constant)):
            return None
        # Only allow Constant (numbers) and BinOp/UnaryOp
        def allowed(node):
            if isinstance(node, ast.Constant):
                return isinstance(node.value, (int, float))
            if isinstance(node, ast.BinOp):
                return isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)) and allowed(node.left) and allowed(node.right)
            if isinstance(node, ast.UnaryOp):
                return isinstance(node.op, (ast.UAdd, ast.USub)) and allowed(node.operand)
            return False
        if not allowed(tree.body):
            return None
        return eval(compile(tree, "<calc>", "eval"))
    except Exception:
        return None


async def execute_telegram_tool(
    name: str,
    arguments: Dict[str, Any],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute a single tool by name with the given arguments.
    context must include: conversation_id, and optionally:
    - todo_user_key: str (required for manageTodoList; uses persistent store only)
    - memory_cache_store: Dict[str, list]
    - do_search, do_fetch, do_news, do_weather, do_autogen, do_browser_agent, do_deep_research (async callables)
    - do_restart_proxy (async callable that schedules proxy restart)
    - read_file_internal, write_file_internal, list_files_internal (callables)
    - send_telegram_file_internal (async callable to send scratch files to current Telegram chat)
    - upload_drive_internal (callable), memory_manager (object with store/search/list/delete)
    Returns a dict with success (bool), message (str), and optional data.
    """
    cid = context.get("conversation_id") or "default"
    name = _canonicalize_telegram_tool_name(name)
    _log_tool_invocation(name, arguments, cid)
    memory_cache_store = context.get("memory_cache_store") or {}
    todo_user_key = context.get("todo_user_key")

    def mem_cache() -> List[str]:
        return memory_cache_store.setdefault(cid, [])

    # --- manageTodoList --- (persistent store only; in-memory fallback disabled)
    if name == "manageTodoList":
        action = (arguments.get("action") or "").strip().lower()
        task_id = arguments.get("taskId")
        task_description = (arguments.get("taskDescription") or "").strip()
        scheduled_for = (arguments.get("scheduledFor") or arguments.get("scheduled_for") or "").strip() or None
        clear_schedule = bool(arguments.get("clearSchedule") or arguments.get("clear_schedule"))
        clear_recurrence = bool(arguments.get("clearRecurrence") or arguments.get("clear_recurrence"))

        recurrence: Optional[Dict[str, Any]] = None
        recurrence_arg = arguments.get("recurrence")
        if isinstance(recurrence_arg, dict):
            freq = str(recurrence_arg.get("frequency", "")).strip().lower()
            interval = recurrence_arg.get("interval", 1)
            if freq:
                try:
                    recurrence = {"frequency": freq, "interval": int(interval)}
                except (TypeError, ValueError):
                    return {"success": False, "message": "recurrence.interval must be a number."}
        else:
            repeat_frequency = str(arguments.get("repeatFrequency") or arguments.get("repeat_frequency") or "").strip().lower()
            repeat_interval = arguments.get("repeatInterval", arguments.get("repeat_interval", 1))
            if repeat_frequency:
                try:
                    recurrence = {"frequency": repeat_frequency, "interval": int(repeat_interval)}
                except (TypeError, ValueError):
                    return {"success": False, "message": "repeatInterval must be a number."}

        use_persistent = todo_user_key and _todo_store_module is not None
        if not use_persistent:
            return {
                "success": False,
                "message": "Todo list is not available (persistent store not configured). Please use the web app with sign-in or ensure the server has todo storage enabled.",
            }

        def _parse_task_id(value: Any) -> Optional[int]:
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                return None
            return parsed

        def _load_meta() -> Dict[str, Any]:
            meta_loader = getattr(_todo_store_module, "load_tasks_with_meta", None)
            if callable(meta_loader):
                loaded = meta_loader(todo_user_key)
                if isinstance(loaded, dict):
                    tasks_out = loaded.get("tasks")
                    task_items_out = loaded.get("task_items")
                    if not isinstance(tasks_out, list):
                        tasks_out = []
                    if not isinstance(task_items_out, list):
                        task_items_out = []
                    return {"tasks": tasks_out, "task_items": task_items_out}
            fallback = _todo_store_module.load_tasks(todo_user_key)
            fallback = fallback if isinstance(fallback, list) else []
            return {"tasks": [str(t) for t in fallback], "task_items": []}

        meta = _load_meta()
        tasks = meta["tasks"]
        task_items = meta["task_items"]

        if action in {"list", "due", "list_due", "listdue"}:
            due_only = action in {"due", "list_due", "listdue"}
            items_for_render = task_items
            tasks_for_render = tasks
            now_utc = datetime.now(timezone.utc)

            if due_only:
                due_loader = getattr(_todo_store_module, "list_due_task_items", None)
                if callable(due_loader):
                    due_items = due_loader(todo_user_key)
                    if isinstance(due_items, list):
                        items_for_render = [item for item in due_items if isinstance(item, dict)]
                else:
                    filtered: List[Dict[str, Any]] = []
                    for item in task_items:
                        if not isinstance(item, dict):
                            continue
                        next_run = item.get("next_run_at")
                        if not next_run:
                            continue
                        try:
                            next_run_text = str(next_run)
                            if next_run_text.endswith("Z"):
                                next_run_text = next_run_text[:-1] + "+00:00"
                            parsed_next = datetime.fromisoformat(next_run_text)
                            if parsed_next.tzinfo is None:
                                parsed_next = parsed_next.replace(tzinfo=timezone.utc)
                            if parsed_next.astimezone(timezone.utc) <= now_utc:
                                filtered.append(item)
                        except ValueError:
                            continue
                    items_for_render = filtered
                tasks_for_render = [
                    str(item.get("description") or "").strip()
                    for item in items_for_render
                    if isinstance(item, dict) and str(item.get("description") or "").strip()
                ]

            if not tasks_for_render and not items_for_render:
                if due_only:
                    return {"success": True, "message": "You have no due scheduled tasks right now.", "data": {"tasks": [], "task_items": []}}
                return {"success": True, "message": "Your todo list is empty."}
            if not items_for_render:
                items_for_render = [{"description": t} for t in tasks_for_render]

            lines = []
            for i, item in enumerate(items_for_render):
                description = str(item.get("description") or (tasks_for_render[i] if i < len(tasks_for_render) else "")).strip()
                line_number = _parse_task_id(item.get("task_id")) or (i + 1)
                next_run = item.get("next_run_at")
                recurrence_item = item.get("recurrence")
                suffix_parts = []
                if next_run:
                    due_marker = ""
                    try:
                        next_run_text = str(next_run)
                        if next_run_text.endswith("Z"):
                            next_run_text = next_run_text[:-1] + "+00:00"
                        parsed_next = datetime.fromisoformat(next_run_text)
                        if parsed_next.tzinfo is None:
                            parsed_next = parsed_next.replace(tzinfo=timezone.utc)
                        if parsed_next.astimezone(timezone.utc) <= now_utc:
                            due_marker = ", due now"
                    except ValueError:
                        pass
                    suffix_parts.append(f"next: {next_run}{due_marker}")
                if isinstance(recurrence_item, dict):
                    freq = str(recurrence_item.get("frequency", "")).strip().lower()
                    interval = recurrence_item.get("interval", 1)
                    if freq:
                        try:
                            interval_value = int(interval)
                        except (TypeError, ValueError):
                            interval_value = 1
                        unit = freq if interval_value == 1 else f"{freq}s"
                        suffix_parts.append(f"repeats every {interval_value} {unit}")
                suffix = f" ({'; '.join(suffix_parts)})" if suffix_parts else ""
                lines.append(f"{line_number}. {description}{suffix}")
            intro = "Here are your due tasks:\n" if due_only else "Here are your current tasks:\n"
            return {
                "success": True,
                "message": intro + "\n".join(lines),
                "data": {"tasks": tasks_for_render, "task_items": items_for_render},
            }

        if action == "add":
            if not task_description:
                return {"success": False, "message": "Task description is required."}
            try:
                _todo_store_module.add_task(
                    todo_user_key,
                    task_description,
                    scheduled_for=scheduled_for,
                    recurrence=recurrence,
                )
            except ValueError as e:
                return {"success": False, "message": str(e)}
            return {"success": True, "message": f"Added task: {task_description}"}

        if action == "update":
            idx = _parse_task_id(task_id)
            if idx is None or idx < 1:
                return {"success": False, "message": "Invalid task ID."}
            description_for_update = task_description if task_description else None
            if (
                description_for_update is None
                and scheduled_for is None
                and recurrence is None
                and not clear_schedule
                and not clear_recurrence
            ):
                return {
                    "success": False,
                    "message": "Provide at least one update field (taskDescription, scheduledFor, recurrence, clearSchedule, clearRecurrence).",
                }
            try:
                _todo_store_module.update_task(
                    todo_user_key,
                    idx,
                    description_for_update,
                    scheduled_for=scheduled_for,
                    recurrence=recurrence,
                    clear_schedule=clear_schedule,
                    clear_recurrence=clear_recurrence,
                )
            except ValueError:
                return {"success": False, "message": "Invalid task ID."}
            return {"success": True, "message": f"Updated task {idx}."}

        if action == "delete":
            if task_id is None:
                return {"success": False, "message": "Task ID is required."}
            idx = _parse_task_id(task_id)
            if idx is None or idx < 1:
                return {"success": False, "message": "Invalid task ID."}
            try:
                _todo_store_module.delete_task(todo_user_key, idx)
            except ValueError:
                return {"success": False, "message": "Invalid task ID."}
            return {"success": True, "message": f"Deleted task {idx}."}

        if action == "complete":
            if task_id is None:
                return {"success": False, "message": "Task ID is required."}
            idx = _parse_task_id(task_id)
            if idx is None or idx < 1:
                return {"success": False, "message": "Invalid task ID."}
            try:
                complete_fn = getattr(_todo_store_module, "complete_task", None)
                if callable(complete_fn):
                    result = complete_fn(todo_user_key, idx)
                    if isinstance(result, dict) and result.get("rescheduled"):
                        next_run_at = result.get("next_run_at") or "the next scheduled run"
                        return {
                            "success": True,
                            "message": f"Completed task {idx}. This repeating task was rescheduled for {next_run_at}.",
                        }
                else:
                    _todo_store_module.delete_task(todo_user_key, idx)
            except ValueError:
                return {"success": False, "message": "Invalid task ID."}
            return {"success": True, "message": f"Completed task {idx}."}

        if action == "clear":
            _todo_store_module.clear_tasks(todo_user_key)
            return {"success": True, "message": "Todo list has been cleared."}
        return {"success": False, "message": "Invalid action."}

    # --- executeTodoTask --- (start task execution; human must confirm to complete)
    if name == "executeTodoTask":
        task_id = arguments.get("taskId") or arguments.get("task_id")
        prompt_override = arguments.get("promptOverride") or arguments.get("prompt_override") or ""
        if task_id is None:
            return {"success": False, "message": "Task ID is required."}
        try:
            tid = int(task_id) if isinstance(task_id, (int, float)) else int(str(task_id))
        except (TypeError, ValueError):
            return {"success": False, "message": "Invalid task ID."}
        start_fn = context.get("task_execute_start")
        if not start_fn:
            return {"success": False, "message": "Task execution is not available."}
        user_key = context.get("todo_user_key") or cid
        try:
            status, message = await start_fn(user_key, tid, (prompt_override or "").strip() or None)
            register_target_fn = context.get("task_execution_register_telegram_target")
            chat_id = context.get("user_id") or context.get("conversation_id")
            if callable(register_target_fn):
                try:
                    register_target_fn(user_key, chat_id, tid)
                except TypeError:
                    try:
                        register_target_fn(user_key, chat_id)
                    except Exception:
                        pass
                except Exception:
                    pass
            return {"success": True, "message": message, "status": status}
        except Exception as e:
            msg = str(e)
            if "409" in msg or "already active" in msg.lower() or "already executing" in msg.lower():
                return {"success": False, "message": msg or f"Task {tid} is already executing."}
            if "400" in msg or "Invalid" in msg:
                return {"success": False, "message": msg or "Invalid request."}
            return {"success": False, "message": msg or "Task execution failed."}

    # --- cancelTodoExecution --- (request soft cancel for current execution)
    if name == "cancelTodoExecution":
        cancel_fn = context.get("task_execute_cancel")
        if not cancel_fn:
            return {"success": False, "message": "Task execution cancel is not available."}
        user_key = context.get("todo_user_key") or cid
        task_id = arguments.get("taskId") or arguments.get("task_id")
        parsed_task_id: Optional[int] = None
        if task_id is not None:
            try:
                parsed_task_id = int(task_id)
            except (TypeError, ValueError):
                return {"success": False, "message": "Invalid task ID."}
        try:
            ok, msg, cancelled_task_id = cancel_fn(user_key, parsed_task_id)
        except TypeError:
            ok, msg = cancel_fn(user_key)
            cancelled_task_id = parsed_task_id
        result: Dict[str, Any] = {"success": ok, "message": msg}
        if cancelled_task_id is not None:
            result["taskId"] = cancelled_task_id
        return result

    # --- getTodoExecutionStatus --- (return current execution status for user)
    if name == "getTodoExecutionStatus":
        status_fn = context.get("task_execution_status")
        if not status_fn:
            return {"success": True, "message": "No execution status available.", "data": None}
        user_key = context.get("todo_user_key") or cid
        task_id = arguments.get("taskId") or arguments.get("task_id")
        parsed_task_id: Optional[int] = None
        if task_id is not None:
            try:
                parsed_task_id = int(task_id)
            except (TypeError, ValueError):
                return {"success": False, "message": "Invalid task ID."}
        try:
            state = status_fn(user_key, parsed_task_id)
        except TypeError:
            state = status_fn(user_key)
        if not state:
            return {"success": True, "message": "No task is currently running or paused.", "data": None}
        return {
            "success": True,
            "message": state.get("message") or f"Status: {state.get('status', 'unknown')}.",
            "data": state,
        }

    # --- manageMemoryCache ---
    if name == "manageMemoryCache":
        action = (arguments.get("action") or "").strip().lower()
        mem_id = arguments.get("memId")
        mem_description = (arguments.get("memDescription") or "").strip()
        items = mem_cache()
        if action == "list":
            if not items:
                return {"success": True, "message": "Memory cache is empty."}
            lines = [f"{i + 1}. {m}" for i, m in enumerate(items)]
            return {"success": True, "message": "Memory cache:\n" + "\n".join(lines)}
        if action == "add":
            if not mem_description:
                return {"success": False, "message": "Memory description is required."}
            items.append(mem_description)
            return {"success": True, "message": f"Added to memory cache: {mem_description}"}
        if action == "update":
            if mem_id is None or not mem_description:
                return {"success": False, "message": "Both memId and memDescription are required."}
            idx = int(mem_id) if isinstance(mem_id, (int, float)) else None
            if idx is None or idx < 1 or idx > len(items):
                return {"success": False, "message": "Invalid memId."}
            items[idx - 1] = mem_description
            return {"success": True, "message": "Updated memory cache entry."}
        if action == "delete":
            if mem_id is None:
                return {"success": False, "message": "memId is required."}
            idx = int(mem_id) if isinstance(mem_id, (int, float)) else None
            if idx is None or idx < 1 or idx > len(items):
                return {"success": False, "message": "Invalid memId."}
            items.pop(idx - 1)
            return {"success": True, "message": "Deleted from memory cache."}
        if action == "clear":
            items.clear()
            return {"success": True, "message": "Memory cache has been cleared."}
        return {"success": False, "message": "Invalid action."}

    # --- navigateToUrl / openChatToUser ---
    if name in ("navigateToUrl", "openChatToUser"):
        url = (arguments.get("url") or "").strip()
        if not url:
            return {"success": False, "message": "URL is required."}
        return {
            "success": True,
            "message": f"Here's the link: {url}. In Telegram I can't open it; open it in your browser.",
        }

    # --- calculate ---
    if name == "calculate":
        expr = (arguments.get("expression") or "").strip()
        result = _safe_calculate(expr)
        if result is None:
            return {"success": False, "message": "Invalid or unsafe expression."}
        return {"success": True, "message": str(result), "data": {"result": result}}

    # --- runWorkflow ---
    if name == "runWorkflow":
        do_autogen = context.get("do_autogen")
        if not do_autogen:
            return {"success": False, "message": "Workflow (AutoGen) is not available."}
        prompt = (arguments.get("contentPrompt") or "").strip()
        if not prompt:
            return {"success": False, "message": "contentPrompt is required."}
        result = await do_autogen(prompt)
        msg = result.get("output") or result.get("response") or result.get("detail", str(result))
        return {"success": True, "message": msg, "data": result}

    # --- runCodexCli ---
    if name == "runCodexCli":
        do_codex = context.get("do_codex")
        if not do_codex:
            return {"success": False, "message": "Codex CLI is not available."}
        prompt = (arguments.get("prompt") or "").strip()
        if not prompt:
            return {"success": False, "message": "prompt is required."}
        result = await do_codex(prompt=prompt)
        summary_file = result.get("summaryFile")
        events_file = result.get("eventsFile")
        last_message_file = result.get("lastMessageFile")
        exit_code = result.get("exitCode")
        timed_out = result.get("timedOut")
        message = (
            f"Codex CLI finished (exit_code={exit_code}, timed_out={timed_out}). "
            f"Summary file: {summary_file}. Events file: {events_file}. Last message file: {last_message_file}"
        )
        return {"success": True, "message": message, "data": result}

    # --- restartProxyServer ---
    if name == "restartProxyServer":
        do_restart_proxy = context.get("do_restart_proxy")
        if not do_restart_proxy:
            return {"success": False, "message": "Proxy restart is not available."}
        confirm = arguments.get("confirm")
        if str(confirm).strip().lower() not in {"true", "1", "yes", "y"}:
            return {"success": False, "message": "Set confirm=true to restart the proxy server."}
        reason = (arguments.get("reason") or "").strip()
        result = await do_restart_proxy(reason)
        ok = bool(result.get("success", False))
        return {"success": ok, "message": result.get("message", "Proxy restart requested."), "data": result}

    # --- scrapeWebsite ---
    if name == "scrapeWebsite":
        do_fetch = context.get("do_fetch")
        if not do_fetch:
            return {"success": False, "message": "Web fetch is not available."}

        def _coerce_bool(value: Any, default: bool = False) -> bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            if isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in {"1", "true", "yes", "y", "on"}:
                    return True
                if lowered in {"0", "false", "no", "n", "off"}:
                    return False
            return default

        # Accept single url or list urls; try each until one succeeds (scrape-with-retry)
        url = (arguments.get("url") or "").strip()
        urls_arg = arguments.get("urls")
        if isinstance(urls_arg, list):
            url_list = [u.strip() for u in urls_arg if u and isinstance(u, str) and u.strip()]
        else:
            url_list = [url] if url else []
        if not url_list:
            return {"success": False, "message": "URL or urls is required."}

        render_js = _coerce_bool(arguments.get("render_js", False))
        render_engine = str(arguments.get("render_engine") or "auto").strip().lower()
        wait_for_selector = str(arguments.get("wait_for_selector") or "").strip() or None
        try:
            js_wait_ms = int(arguments.get("js_wait_ms", 2200))
        except (TypeError, ValueError):
            js_wait_ms = 2200

        fetch_kwargs: Dict[str, Any] = {
            "render_js": render_js,
            "render_engine": render_engine,
            "wait_for_selector": wait_for_selector,
            "js_wait_ms": js_wait_ms,
        }

        last_error: Optional[str] = None
        for one_url in url_list:
            try:
                try:
                    out = await do_fetch(one_url, **fetch_kwargs)
                except TypeError:
                    # Backward compatibility for older callback signatures used in tests/integrations.
                    out = await do_fetch(one_url)
                content = (out.get("content") or "")[:4000]
                return {"success": True, "message": f"Fetched content (snippet):\n{content}", "data": out}
            except Exception as e:
                last_error = str(e)
                continue
        return {"success": False, "message": last_error or "Failed to fetch any URL."}

    # --- webSearch ---
    if name == "webSearch":
        do_search = context.get("do_search")
        if not do_search:
            return {"success": False, "message": "Web search is not available."}
        query = (arguments.get("query") or "").strip()
        if not query:
            return {"success": False, "message": "Query is required."}
        data = await do_search(query)
        results = data.get("results") or []
        # Include URL in each line so the model can pass them to scrapeWebsite (e.g. urls array for retry)
        lines = [
            f"- {r.get('title', '')}: {r.get('snippet', '')} | URL: {r.get('url', '')}"
            for r in results[:5]
        ]
        return {"success": True, "message": "Search results:\n" + "\n".join(lines) if lines else "No results.", "data": data}


    # --- weatherInfo ---
    if name == "weatherInfo":
        do_weather = context.get("do_weather")
        if not do_weather:
            return {"success": False, "message": "Weather service is not available."}
        location_value = arguments.get("location")
        location = location_value.strip() if isinstance(location_value, str) else (str(location_value).strip() if location_value else "")
        detail_value = arguments.get("requestType") or arguments.get("detail") or "summary"
        detail = detail_value.strip().lower() if isinstance(detail_value, str) else str(detail_value).strip().lower()
        if detail not in {"summary", "current", "forecast"}:
            detail = "summary"
        user_id = context.get("user_id")
        try:
            data = await do_weather(location=location or None, detail=detail, user_id=user_id, memory_manager=context.get("memory_manager"))
            return {"success": True, "message": data.get("summary", "Weather data retrieved."), "data": data}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # --- fetchNews ---
    if name == "fetchNews":
        do_news = context.get("do_news")
        write_internal = context.get("write_file_internal")
        if not do_news or not write_internal:
            return {"success": False, "message": "News or file write is not available."}
        search_term = (arguments.get("searchTerm") or arguments.get("query") or "").strip()
        filename = (arguments.get("filename") or "news.csv").strip() or "news.csv"
        if not search_term:
            return {"success": False, "message": "searchTerm is required."}
        data = await do_news(search_term)
        articles = data.get("articles") or []
        if not articles:
            return {"success": True, "message": f"No articles found for \"{search_term}\"."}
        csv_lines = ["Title,URL"]
        for a in articles:
            title = (a.get("title") or "").replace(",", " ")
            url = a.get("url") or ""
            csv_lines.append(f'"{title}","{url}"')
        csv_content = "\n".join(csv_lines)
        wr = await write_internal(filename, csv_content, "txt")
        if isinstance(wr, dict) and not wr.get("success"):
            return {"success": False, "message": wr.get("message", "Failed to write file.")}
        return {"success": True, "message": f"Saved {len(articles)} news articles to {filename}."}

    # --- readFile ---
    if name == "readFile":
        read_internal = context.get("read_file_internal")
        if not read_internal:
            return {"success": False, "message": "File read is not available."}
        filename = (arguments.get("filename") or "").strip()
        if not filename:
            return {"success": False, "message": "filename is required."}
        out = await read_internal(filename)
        if isinstance(out, dict) and not out.get("success"):
            return {"success": False, "message": out.get("message", "Read failed.")}
        data = out.get("data") or {}
        content = data.get("content", "")
        return {"success": True, "message": out.get("message", "Read OK"), "data": {"content": content}}

    # --- writeFile ---
    if name == "writeFile":
        write_internal = context.get("write_file_internal")
        if not write_internal:
            return {"success": False, "message": "File write is not available."}
        filename = (arguments.get("filename") or "").strip()
        content = arguments.get("content", "")
        fmt = (arguments.get("format") or "txt").strip().lower() or "txt"
        if not filename:
            return {"success": False, "message": "filename is required."}
        out = await write_internal(filename, str(content), fmt)
        if isinstance(out, dict) and not out.get("success"):
            return {"success": False, "message": out.get("message", "Write failed.")}
        return {"success": True, "message": out.get("message", "Write OK.")}

    # --- listFiles ---
    if name == "listFiles":
        list_internal = context.get("list_files_internal")
        if not list_internal:
            return {"success": False, "message": "File list is not available."}
        path_value = (
            arguments.get("path")
            or arguments.get("subdir")
            or arguments.get("directory")
            or ""
        )
        path = str(path_value).strip() if path_value is not None else ""
        recursive_raw = arguments.get("recursive", False)
        if isinstance(recursive_raw, bool):
            recursive = recursive_raw
        elif isinstance(recursive_raw, (int, float)):
            recursive = bool(recursive_raw)
        else:
            recursive = str(recursive_raw).strip().lower() in {"1", "true", "yes", "y", "on"}

        try:
            out = await list_internal(path=path, recursive=recursive)
        except TypeError:
            # Backward compatibility for older callback signatures in tests/custom integrations.
            if path or recursive:
                try:
                    out = await list_internal(path, recursive)
                except TypeError:
                    return {
                        "success": False,
                        "message": "File list backend does not support path or recursive arguments.",
                    }
            else:
                out = await list_internal()
        if isinstance(out, dict) and not out.get("success"):
            return {"success": False, "message": out.get("message", "List failed.")}
        if not isinstance(out, dict):
            return {"success": False, "message": "File list backend returned an invalid response."}
        files = out.get("files")
        if not isinstance(files, list):
            files = []
        message = _format_list_files_message(files)
        skipped_count_raw = out.get("skipped_count", 0)
        try:
            skipped_count = int(skipped_count_raw or 0)
        except (TypeError, ValueError):
            skipped_count = 0
        if skipped_count > 0:
            message += f"\n- ... skipped {skipped_count} inaccessible or unsafe entries."
        return {"success": True, "message": message, "data": out}

    # --- sendTelegramFile ---
    if name == "sendTelegramFile":
        send_file_internal = context.get("send_telegram_file_internal")
        if not send_file_internal:
            return {"success": False, "message": "Telegram file sending is not available."}
        filename = (arguments.get("filename") or arguments.get("filePath") or "").strip()
        if not filename:
            return {"success": False, "message": "filename is required."}
        caption_raw = arguments.get("caption")
        caption = str(caption_raw).strip() if caption_raw is not None else None
        out = await send_file_internal(filename, caption=caption or None)
        if isinstance(out, dict) and not out.get("success", False):
            return {"success": False, "message": out.get("message", "Failed to send file.")}
        return {
            "success": True,
            "message": (out or {}).get("message", f"Sent {filename} to Telegram."),
            "data": out or {},
        }

    # --- storeMemory ---
    if name == "storeMemory":
        mm = context.get("memory_manager")
        if not mm:
            return {"success": False, "message": "Memory system is not available."}
        text = (arguments.get("text") or arguments.get("content") or "").strip()
        category = (arguments.get("category") or "").strip() or None
        if not text:
            return {"success": False, "message": "text is required."}
        guard_fn = getattr(mm, "should_store_as_conversational_memory", None)
        if callable(guard_fn):
            allow_store = guard_fn(
                text=text,
                category=category,
                source="telegram",
                metadata=None,
            )
            if isinstance(allow_store, bool) and not allow_store:
                return {
                    "success": False,
                    "message": "Refused to store transient task/list/status state as memory.",
                }
        mid = await mm.store_memory(text=text, category=category, source="telegram")
        return {"success": True, "message": "Memory stored.", "data": {"memory_id": mid}}

    # --- searchMemories ---
    if name == "searchMemories":
        mm = context.get("memory_manager")
        if not mm:
            return {"success": False, "message": "Memory system is not available."}
        query = (arguments.get("query") or "").strip()
        if not query:
            return {"success": False, "message": "query is required."}
        results = await mm.search_memories(query=query, limit=arguments.get("limit", 5))
        items = results or []
        lines = [f"- {m.get('text', '')}" for m in items]
        return {"success": True, "message": "Memories:\n" + "\n".join(lines) if lines else "No matches.", "data": {"memories": items}}

    # --- listMemories ---
    if name == "listMemories":
        mm = context.get("memory_manager")
        if not mm:
            return {"success": False, "message": "Memory system is not available."}
        try:
            mems = mm.list_memories(limit=arguments.get("limit", 20))
        except Exception:
            mems = []
        lines = [f"- {m.get('text', '')}" for m in (mems or [])]
        return {"success": True, "message": "Memories:\n" + "\n".join(lines) if lines else "No memories.", "data": {"memories": mems}}

    # --- deleteMemory ---
    if name == "deleteMemory":
        mm = context.get("memory_manager")
        if not mm:
            return {"success": False, "message": "Memory system is not available."}
        mid = (arguments.get("memory_id") or arguments.get("id") or "").strip()
        if not mid:
            return {"success": False, "message": "memory_id is required."}
        if asyncio.iscoroutinefunction(getattr(mm, "delete_memory", None)):
            await mm.delete_memory(mid)
        else:
            mm.delete_memory(mid)
        return {"success": True, "message": "Memory deleted."}

    # --- runBrowserAgent ---
    if name == "runBrowserAgent":
        do_browser = context.get("do_browser_agent")
        if not do_browser:
            return {"success": False, "message": "Browser agent is not available."}
        out = await do_browser(arguments)
        msg = out.get("message") or out.get("output") or str(out)[:500]
        return {"success": True, "message": msg, "data": out}

    # --- runDeepResearch ---
    if name == "runDeepResearch":
        do_research = context.get("do_deep_research")
        if not do_research:
            return {"success": False, "message": "Deep research is not available."}
        out = await do_research(arguments)
        msg = out.get("message") or out.get("output") or str(out)[:500]
        return {"success": True, "message": msg, "data": out}

    # --- healthCheck ---
    if name == "healthCheck":
        do_health = context.get("do_browser_health_check")
        if not do_health:
            return {"success": False, "message": "Browser health check is not available."}
        out = await do_health(arguments if isinstance(arguments, dict) else {})
        success = bool(out.get("success", True)) if isinstance(out, dict) else True
        message = ""
        if isinstance(out, dict):
            message = str(out.get("message") or "").strip()
            if not message:
                result_val = out.get("result")
                if isinstance(result_val, (dict, list)):
                    try:
                        message = json.dumps(result_val, ensure_ascii=False, indent=2, default=str)
                    except Exception:
                        message = str(result_val)
                elif result_val is not None:
                    message = str(result_val)
        if not message:
            message = str(out)[:1000]
        return {"success": success, "message": message, "data": out if isinstance(out, dict) else {"raw": out}}

    # --- pdfToPowerPoint ---
    if name == "pdfToPowerPoint":
        return {"success": True, "message": "PDF to PowerPoint is only available in the CATBot web interface. Please use the web app for this feature."}

    # --- uploadToGoogleDrive ---
    if name == "uploadToGoogleDrive":
        upload_internal = context.get("upload_drive_internal")
        if not upload_internal:
            return {"success": False, "message": "Google Drive upload is not available."}
        file_path = (arguments.get("filePath") or arguments.get("filename") or "").strip()
        file_name = (arguments.get("fileName") or "").strip() or None
        if not file_path:
            return {"success": False, "message": "filePath is required."}
        out = await upload_internal(file_path, file_name)
        if isinstance(out, dict) and not out.get("success", True):
            return {"success": False, "message": out.get("message", "Upload failed.")}
        return {"success": True, "message": out.get("message", "Uploaded to Google Drive.")}

    # --- llmQuery ---
    if name == "llmQuery":
        llm_internal = context.get("llm_query_internal")
        if not llm_internal:
            return {"success": True, "message": "Custom LLM queries are available in the CATBot web interface."}
        prompt = (arguments.get("contentPrompt") or arguments.get("query") or arguments.get("message") or "").strip()
        if not prompt:
            return {"success": False, "message": "query or contentPrompt is required."}
        out = await llm_internal(prompt)
        return {"success": True, "message": out.get("content", str(out)), "data": out}

    # --- dynamic skill framework tools ---
    skill_executor = context.get("execute_skill_tool")
    if callable(skill_executor):
        try:
            skill_result = await skill_executor(name, arguments)
        except TypeError:
            # Backward compatibility for callbacks that still expect context
            skill_result = await skill_executor(name, arguments, context)
        except Exception as e:
            return {"success": False, "message": f"Skill tool execution failed: {e}"}

        if isinstance(skill_result, dict):
            # Allow unknown tools to fall through to the canonical unknown-tool response.
            if str(skill_result.get("error_code") or "").strip().lower() == "tool_not_found":
                pass
            else:
                success = bool(skill_result.get("success", True))
                message = skill_result.get("message")
                if not message:
                    data_val = skill_result.get("data")
                    message = str(data_val) if data_val is not None else f"Executed skill tool: {name}"
                response = {
                    "success": success,
                    "message": str(message),
                }
                if "data" in skill_result:
                    response["data"] = skill_result.get("data")
                if skill_result.get("error_code"):
                    response["error_code"] = skill_result.get("error_code")
                if skill_result.get("tool_name"):
                    response["tool_name"] = skill_result.get("tool_name")
                return response
        elif isinstance(skill_result, str):
            return {"success": True, "message": skill_result}

    return {"success": False, "message": f"Unknown tool: {name}"}

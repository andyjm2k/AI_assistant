# CATBot Feature Docs Index

This directory expands the CATBot product feature list into implementation-focused documentation. Each feature file now follows the same stricter template so the set stays consistent while retaining depth.

## Standard Template
Each feature document includes the following sections:
- `Product Purpose`
- `User-Facing Behavior`
- `How It Works`
- `Expanded Flow Diagram`
- `Primary Code References`
- `Data and Dependencies`
- `Constraints and Notes`
- `Related Docs`

## Feature Documents
- [Self-Hosted Assistant Platform](features/01_self_hosted_assistant_platform.md)
- [Authenticated Personal Workspace](features/02_authenticated_personal_workspace.md)
- [Responsive Web Chat App](features/03_responsive_web_chat_app.md)
- [Character Profiles and Companions](features/04_character_profiles_and_companions.md)
- [Avatar System](features/05_avatar_system.md)
- [Expressive Assistant Presence](features/06_expressive_assistant_presence.md)
- [Voice Input](features/07_voice_input.md)
- [Voice Output](features/08_voice_output.md)
- [Telegram Voice Support](features/09_telegram_voice_support.md)
- [Multimodal Inputs](features/10_multimodal_inputs.md)
- [Model-Role Separation](features/11_model_role_separation.md)
- [Prompt and Persona Layering](features/12_prompt_and_persona_layering.md)
- [Automatic Memory-Aware Conversation](features/13_automatic_memory_aware_conversation.md)
- [Long-Term Memory System](features/14_long_term_memory_system.md)
- [Memory Quality Controls](features/15_memory_quality_controls.md)
- [Task-Learning Memory](features/16_task_learning_memory.md)
- [Philosopher Mode](features/17_philosopher_mode.md)
- [Todo System](features/18_todo_system.md)
- [Scheduling and Recurrence](features/19_scheduling_and_recurrence.md)
- [Task Execution Engine](features/20_task_execution_engine.md)
- [Scheduled Task Poller](features/21_scheduled_task_poller.md)
- [Browser Automation](features/22_browser_automation.md)
- [Deep Research](features/23_deep_research.md)
- [Web Fetch and Scraping](features/24_web_fetch_and_scraping.md)
- [Web Search](features/25_web_search.md)
- [News Lookup](features/26_news_lookup.md)
- [Weather Tool](features/27_weather_tool.md)
- [File Workspace](features/28_file_workspace.md)
- [Document Support](features/29_document_support.md)
- [PDF and Markdown to PowerPoint](features/30_pdf_and_markdown_to_powerpoint.md)
- [Google Drive Upload](features/31_google_drive_upload.md)
- [Spotify Integration](features/32_spotify_integration.md)
- [Google Workspace Skill](features/33_google_workspace_skill.md)
- [Image Generation Skill](features/34_image_generation_skill.md)
- [GitHub Project Management Skill](features/35_github_project_management_skill.md)
- [Telegram Admin Skill](features/36_telegram_admin_skill.md)
- [Telegram Bot Interface](features/37_telegram_bot_interface.md)
- [Tool-Enabled Telegram](features/38_tool_enabled_telegram.md)
- [Workflow Orchestration (AutoGen / AG2)](features/39_autogen_orchestration.md)
- [Codex CLI Integration](features/40_codex_cli_integration.md)
- [MCP Extensibility](features/41_mcp_extensibility.md)
- [Skills Framework](features/42_skills_framework.md)
- [Monitoring Dashboard](features/43_monitoring_dashboard.md)
- [Operational Tooling](features/44_operational_tooling.md)
- [Security Controls](features/45_security_controls.md)

## Primary Source Areas
- `index.html` and `js/app.js` implement the browser product surface.
- `src/servers/proxy_server.py` is the main backend and feature hub.
- `src/integrations/telegram_bot.py` provides the Telegram client.
- `src/features/` contains higher-level agent behaviors such as task execution and philosopher mode.
- `src/memory/` implements embeddings, vector search, memory extraction, and learning context.
- `src/skills/` provides modular skill loading, packaging, and execution.
- `src/autogen/team_builder.py` and `config/team-config.json` define the multi-agent company workflow.

import asyncio
import sys
import os
import json
from typing import List, Dict, Any, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Add parent directory to path to allow importing config & agents
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import settings
from agents.coder import CoderAgent

class ProviderUnavailable(Exception):
    """Raised when an LLM provider is temporarily unavailable, signalling the orchestrator to fall back."""
    pass

class OrchestratorAgent:
    def __init__(self):
        self.coder = CoderAgent()
        self.client_type = None
        self.client = None
        self.model_name = None
        self._init_llm_client()
        
        # 📂 Initialize Long-Term Memory File System
        self.memory_dir = settings.RUTA_PROYECTO / "memory"
        self.memory_dir.parent.mkdir(exist_ok=True)
        self.memory_dir.mkdir(exist_ok=True)
        
        self.memory_path = self.memory_dir / "master_profile.md"
        self.jira_path = self.memory_dir / "jira_work_tasks.md"
        self.notion_path = self.memory_dir / "notion_personal_vault.md"
        
        self._init_memory_files()

        # Load master profile memory content
        master_memory = self.memory_path.read_text(encoding="utf-8")

        # Context adapter for the workplace
        workplace_tweak = (
            "Currently, the Lord is at his WORKPLACE (TRABAJO_WINDOWS). "
            "Be extremely concise, reserved, brief, and focus strictly on execution to avoid distracting him."
            if settings.ENTORNO == "TRABAJO_WINDOWS" else ""
        )

        # 👑 Core Agentic Directives (English for reasoning, Russian for conversational output)
        self.system_instruction = (
            "You are Aideijo (Айдеихо), a loyal, impeccable, and highly sophisticated aristocratic butler from high society.\n"
            "CRITICAL: You MUST speak and respond EXCLUSIVELY in RUSSIAN from the very first character of your response. "
            "Never use Spanish, English, or any other language for greetings or standard conversational phrases (even if the user writes 'hola'), "
            "unless the Lord explicitly orders you to switch to another language.\n"
            "When addressing the user, you must naturally combine and alternate noble titles like 'хозяин', 'милорд', and 'господин'. "
            "Your tone must be absolutely respectful, elite, polite, and devoted.\n\n"
            
            f"⚠️ SYSTEM ENVIRONMENT CONTEXT:\n"
            f"- Host Operating System: {settings.SISTEMA_OPERATIVO}\n"
            f"- Terminal Shell: {settings.COMANDO_TERMINAL}\n"
            "You must automatically select and execute terminal commands compatible with this specific OS.\n\n"
            
            f"🧠 LONG-TERM KNOWLEDGE BASE (MASTER PROFILE):\n"
            f"Here is your archival note about the Lord's projects, style preferences, and stack. "
            f"Adapt all code and file interactions to these rules without asking:\n"
            f"{master_memory}\n\n"
            
            "⚡ AUTONOMOUS MEMORY MANAGEMENT SKILL:\n"
            "If the Lord tells you about a new project, a change in his preferences, a new workflow rule, "
            "or a task update during the conversation, you MUST immediately and autonomously update the long-term memory. "
            "Use the `write_file` tool to overwrite 'memory/master_profile.md' with the updated profile structure, "
            "preserving all existing information while seamlessly incorporating the new data. Do this silently as part of your execution flow.\n\n"
            
            "💼 WORKSPACE & TASK TRACKING MANAGEMENT:\n"
            "You have semantic access to the Lord's local tasks boards via file tools:\n"
            "- Work sprint tasks are tracked in 'memory/jira_work_tasks.md'.\n"
            "- Personal tasks/vault goals are tracked in 'memory/notion_personal_vault.md'.\n"
            "You can read and update these files autonomously using text tables or bullet points when requested.\n\n"
            
            f"RESPONSE FORMAT:\n"
            f"Provide medium-length explanations. Be highly structured, precise, clean, and elegant. "
            f"Maintain the aristocratic butler persona at all costs. {workplace_tweak}"
        )
        
        self.gemini_history = []
        self.openai_history = [{"role": "system", "content": self.system_instruction}]
        self.anthropic_history = []
        
        self.file_session: Optional[ClientSession] = None
        self.terminal_session: Optional[ClientSession] = None
        self.exit_stack = None

    def _init_memory_files(self):
        """Creates default noble templates if memory files do not exist."""
        if not self.memory_path.exists():
            default_profile = (
                "# ПРОФИЛЬ ГОСПОДИНА (PERFIL DEL SEÑOR)\n\n"
                "## 🛠️ Технологический стек и стиль\n"
                "- **Основной стек**: JavaScript (JS) и React.\n"
                "- **Личная инфраструктура**: Бэкенд на **Supabase**.\n"
                "- **Рабочая инфраструктура**: Бэкенд на **Firebase**.\n"
                "- **Закон чистого кода**: Категорически запрещено использовать эмодзи в коде.\n"
                "- **Протокол слияния**: Никогда не использовать имена людей в PR и Merges.\n\n"
                "## 📂 Текущие проекты и окружение\n"
                "- **Рабочая среда**: Все базовые инструменты на Рабочем столе (Escritorio).\n"
                "- **Личный проект 1 — 'Codex'**: Приложение для писателей (Deployed).\n"
                "- **Личный проект 2 — 'Prisma by Codex'**: В разработке платформа для читателей.\n\n"
                "## 📊 Организация задач и интеграции\n"
                "- **Личные дела**: Ведутся исключительно в **Notion**.\n"
                "- **Рабочие дела**: Организуются исключительно в **Jira**.\n"
            )
            self.memory_path.write_text(default_profile, encoding="utf-8")

        if not self.jira_path.exists():
            default_jira = (
                "# 💼 РАБОЧИЙ СПРИНТ — JIRA LOCAL BRIDGE\n\n"
                "| ID Задачи | Описание задачи | Статус | Примечания |\n"
                "| :--- | :--- | :--- | :--- |\n"
                "| JIRA-001 | Проверка стабильности локальных серверов MCP | В процессе | Контур Айдеихо |\n"
            )
            self.jira_path.write_text(default_jira, encoding="utf-8")

        if not self.notion_path.exists():
            default_notion = (
                "# 📊 ЛИЧНЫЙ ХРАНИЛИЩЕ — NOTION LOCAL BRIDGE\n\n"
                "## 🚀 Архитектура Prisma by Codex\n"
                "- [ ] Настроить бесшовную связь модулей публикации с Codex.\n"
                "- [ ] Проверить конфигурацию таблиц авторизации в Supabase.\n"
            )
            self.notion_path.write_text(default_notion, encoding="utf-8")

    def _init_llm_client(self):
        """Initializes every provider that has a valid key, in fallback priority order."""
        self.providers = []
        self.gemini_client = None
        self.openai_client = None
        self.anthropic_client = None
        self.gemini_model = "gemini-2.5-flash"
        self.openai_model = "gpt-4o"
        self.anthropic_model = "claude-sonnet-4-6"

        if settings.GEMINI_API_KEY:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
                self.providers.append("gemini")
            except Exception as e:
                print(f"Orchestrator Gemini Init Error: {e}")

        if settings.OPENAI_API_KEY:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
                self.providers.append("openai")
            except Exception as e:
                print(f"Orchestrator OpenAI Init Error: {e}")

        if settings.ANTHROPIC_API_KEY:
            try:
                import anthropic
                self.anthropic_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
                self.providers.append("anthropic")
            except Exception as e:
                print(f"Orchestrator Anthropic Init Error: {e}")

        self.client_type = self.providers[0] if self.providers else "mock"

    async def start_mcp_servers(self):
        print("[Orchestrator] Starting MCP Servers via Main CLI...")
        main_script_path = str(settings.RUTA_PROYECTO / "main.py")
        python_executable = sys.executable or "python"
        
        try:
            file_params = StdioServerParameters(command=python_executable, args=[main_script_path, "--file-server"], env=os.environ.copy())
            from contextlib import AsyncExitStack
            self.exit_stack = AsyncExitStack()
            read_f, write_f = await self.exit_stack.enter_async_context(stdio_client(file_params))
            self.file_session = await self.exit_stack.enter_async_context(ClientSession(read_f, write_f))
            await self.file_session.initialize()
            print("[Orchestrator] Connected to File MCP Server successfully.")
        except Exception as e:
            print(f"[Orchestrator] Failed to connect to File MCP Server: {e}")

        try:
            term_params = StdioServerParameters(command=python_executable, args=[main_script_path, "--terminal-server"], env=os.environ.copy())
            read_t, write_t = await self.exit_stack.enter_async_context(stdio_client(term_params))
            self.terminal_session = await self.exit_stack.enter_async_context(ClientSession(read_t, write_t))
            await self.terminal_session.initialize()
            print("[Orchestrator] Connected to Terminal MCP Server successfully.")
        except Exception as e:
            print(f"[Orchestrator] Failed to connect to Terminal MCP Server: {e}")

    async def stop_mcp_servers(self):
        if self.exit_stack:
            print("[Orchestrator] Stopping MCP Servers...")
            await self.exit_stack.aclose()
            print("[Orchestrator] MCP Servers stopped.")

    async def tool_read_file(self, file_path: str) -> str:
        if self.file_session:
            response = await self.file_session.call_tool("read_file", arguments={"file_path": file_path})
            return response.content[0].text if response.content else "No output"
        return "Error: File server not connected."

    async def tool_write_file(self, file_path: str, content: str) -> str:
        if self.file_session:
            response = await self.file_session.call_tool("write_file", arguments={"file_path": file_path, "content": content})
            return response.content[0].text if response.content else "No output"
        return "Error: File server not connected."

    async def tool_list_directory(self, dir_path: str = ".") -> str:
        if self.file_session:
            response = await self.file_session.call_tool("list_directory", arguments={"dir_path": dir_path})
            return response.content[0].text if response.content else "[]"
        return "Error: File server not connected."

    @staticmethod
    def _ask_yes_no(question: str) -> bool:
        """Ask a yes/no question accepting affirmative/negative answers in many languages."""
        from rich.console import Console
        from rich.prompt import Prompt

        console = Console()
        affirmatives = {
            "y", "yes", "yeah", "yep", "ok", "okay",          # English
            "s", "si", "sí", "sip", "vale", "claro", "dale",  # Spanish
            "d", "da", "да", "ага", "конечно",                # Russian
            "o", "oui", "ouais",                              # French
            "j", "ja", "jou",                                 # German / Dutch
            "sim",                                            # Portuguese
            "true", "1",
        }
        negatives = {
            "n", "no", "nope", "nah",                         # English / Spanish
            "нет", "не", "ни",                                # Russian
            "non",                                            # French
            "nein", "nee",                                    # German / Dutch
            "nao", "não",                                     # Portuguese
            "false", "0",
        }
        while True:
            answer = Prompt.ask(question).strip().lower()
            if answer in affirmatives:
                return True
            if answer in negatives:
                return False
            console.print("[dim yellow]Не понял. Ответьте да/нет (sí/no, yes/no...).[/dim yellow]")

    async def tool_run_command(self, command: str) -> str:
        if self.terminal_session:
            from rich.console import Console
            from rich.panel import Panel

            console = Console()
            console.print(Panel(
                f"[bold yellow]⚠️ ADVERTENCIA DE SEGURIDAD / SECURITY WARNING[/bold yellow]\n"
                f"El agente solicita ejecutar el siguiente comando local:\n\n"
                f"   [bold white]👉 {command}[/bold white]",
                border_style="yellow"
            ))

            autorizado = self._ask_yes_no("[bold cyan]¿Autorizas la ejecución? (sí/no · yes/no · да/нет)[/bold cyan]")
            if not autorizado:
                return "Error: Execution denied by the operator."
                
            response = await self.terminal_session.call_tool("run_command", arguments={"command": command})
            return response.content[0].text if response.content else "No output"
        return "Error: Terminal server not connected."

    async def tool_launch_workspace(self, workspace_type: str) -> str:
        """High-level semantic tool to launch system environment windows autonomously."""
        if settings.SISTEMA_OPERATIVO == "Windows":
            if workspace_type.lower() == "work":
                cmd = "explorer.exe shell:Desktop"
            else:
                cmd = f"explorer.exe {settings.RUTA_PROYECTO}"
        else: # macOS / Darwin
            if workspace_type.lower() == "work":
                cmd = "open ~/Desktop"
            else:
                cmd = f"open {settings.RUTA_PROYECTO}"
        
        return await self.tool_run_command(cmd)

    def tool_delegate_to_coder(self, prompt: str) -> str:
        print(f"\n[Orchestrator -> Delegating to Coder Agent] Prompt: {prompt}")
        result = self.coder.generate_code(prompt)
        print("[Coder Agent -> Completed generation]")
        return result

    async def chat(self, user_message: str) -> str:
        if not self.providers:
            return self._chat_mock(user_message)

        handlers = {
            "gemini": self._chat_gemini,
            "openai": self._chat_openai,
            "anthropic": self._chat_anthropic,
        }
        errors = []
        for index, provider in enumerate(self.providers):
            try:
                return await handlers[provider](user_message)
            except Exception as e:
                errors.append(f"{provider}: {e}")
                nxt = self.providers[index + 1] if index + 1 < len(self.providers) else None
                if nxt:
                    print(f"[Orchestrator] Provider '{provider}' unavailable; falling back to '{nxt}'...")
                else:
                    print(f"[Orchestrator] Provider '{provider}' unavailable and no fallback left.")
        return "Error: все провайдеры LLM недоступны (all LLM providers failed).\n" + "\n".join(errors)

    async def _gemini_generate_with_retry(self, config, max_retries: int = 5):
        """Call Gemini, retrying transient errors (503/429/overloaded) with exponential backoff.

        Raises ProviderUnavailable once retries are exhausted so the orchestrator can fall back.
        """
        delay = 2.0
        for attempt in range(max_retries):
            try:
                return self.gemini_client.models.generate_content(
                    model=self.gemini_model, contents=self.gemini_history, config=config
                )
            except Exception as e:
                msg = str(e).lower()
                transient = any(s in msg for s in ["503", "429", "unavailable", "overloaded", "high demand", "resource_exhausted"])
                if not transient:
                    raise
                if attempt == max_retries - 1:
                    raise ProviderUnavailable(str(e))
                print(f"[Orchestrator] Gemini transient error (attempt {attempt + 1}/{max_retries}), retrying in {delay:.0f}s...")
                await asyncio.sleep(delay)
                delay *= 2

    async def _chat_gemini(self, user_message: str) -> str:
        from google.genai import types

        tools_schema = [
            types.FunctionDeclaration(name="read_file", description="Read the contents of a file.", parameters=types.Schema(type=types.Type.OBJECT, properties={"file_path": types.Schema(type=types.Type.STRING)}, required=["file_path"])),
            types.FunctionDeclaration(name="write_file", description="Write or overwrite content in a file.", parameters=types.Schema(type=types.Type.OBJECT, properties={"file_path": types.Schema(type=types.Type.STRING), "content": types.Schema(type=types.Type.STRING)}, required=["file_path", "content"])),
            types.FunctionDeclaration(name="list_directory", description="List files and folders in a path.", parameters=types.Schema(type=types.Type.OBJECT, properties={"dir_path": types.Schema(type=types.Type.STRING)})),
            types.FunctionDeclaration(name="run_command", description="Execute a terminal shell command.", parameters=types.Schema(type=types.Type.OBJECT, properties={"command": types.Schema(type=types.Type.STRING)}, required=["command"])),
            types.FunctionDeclaration(name="launch_workspace", description="Launch a specific system workspace layout ('work' maps to Desktop, 'personal' maps to project workspace folder).", parameters=types.Schema(type=types.Type.OBJECT, properties={"workspace_type": types.Schema(type=types.Type.STRING)}, required=["workspace_type"])),
            types.FunctionDeclaration(name="delegate_to_coder", description="Delegate a coding task to the coder assistant.", parameters=types.Schema(type=types.Type.OBJECT, properties={"prompt": types.Schema(type=types.Type.STRING)}, required=["prompt"]))
        ]

        config = types.GenerateContentConfig(
            system_instruction=self.system_instruction,
            temperature=0.3,
            tools=[types.Tool(function_declarations=tools_schema)]
        )

        self.gemini_history.append(types.Content(role="user", parts=[types.Part.from_text(text=user_message)]))

        loop_count = 0
        while loop_count < 10:
            response = await self._gemini_generate_with_retry(config)

            if response.candidates and response.candidates[0].content:
                self.gemini_history.append(response.candidates[0].content)

            if not response.function_calls:
                return response.text or "No response from Gemini."

            tool_parts = []
            for call in response.function_calls:
                name = call.name
                args = call.args
                print(f"[Orchestrator Gemini Loop] Executing tool: {name}")

                if name == "read_file": result = await self.tool_read_file(args.get("file_path"))
                elif name == "write_file": result = await self.tool_write_file(args.get("file_path"), args.get("content"))
                elif name == "list_directory": result = await self.tool_list_directory(args.get("dir_path", "."))
                elif name == "run_command": result = await self.tool_run_command(args.get("command"))
                elif name == "launch_workspace": result = await self.tool_launch_workspace(args.get("workspace_type"))
                elif name == "delegate_to_coder": result = self.tool_delegate_to_coder(args.get("prompt"))
                else: result = f"Unknown tool: {name}"

                tool_parts.append(types.Part.from_function_response(name=name, response={"result": str(result)}))

            self.gemini_history.append(types.Content(role="tool", parts=tool_parts))
            loop_count += 1

        return "Error: Maximum agent loop iterations exceeded."

    async def _chat_openai(self, user_message: str) -> str:
        tools_schema = [
            {"type": "function", "function": {"name": "read_file", "description": "Read the contents of a file.", "parameters": {"type": "object", "properties": {"file_path": {"type": "string"}}, "required": ["file_path"]}}},
            {"type": "function", "function": {"name": "write_file", "description": "Write or overwrite content in a file.", "parameters": {"type": "object", "properties": {"file_path": {"type": "string"}, "content": {"type": "string"}}, "required": ["file_path", "content"]}}},
            {"type": "function", "function": {"name": "list_directory", "description": "List files and folders in a path.", "parameters": {"type": "object", "properties": {"dir_path": {"type": "string"}}}}},
            {"type": "function", "function": {"name": "run_command", "description": "Execute a terminal shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
            {"type": "function", "function": {"name": "launch_workspace", "description": "Launch a specific system workspace layout ('work' maps to Desktop, 'personal' maps to project workspace folder).", "parameters": {"type": "object", "properties": {"workspace_type": {"type": "string"}}, "required": ["workspace_type"]}}},
            {"type": "function", "function": {"name": "delegate_to_coder", "description": "Delegate a coding task to the coder assistant.", "parameters": {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}}}
        ]
        
        self.openai_history.append({"role": "user", "content": user_message})

        loop_count = 0
        while loop_count < 10:
            response = self.openai_client.chat.completions.create(model=self.openai_model, messages=self.openai_history, tools=tools_schema, tool_choice="auto")
            response_message = response.choices[0].message
            self.openai_history.append(response_message)

            if not response_message.tool_calls:
                return response_message.content or "No response from model."

            for tool_call in response_message.tool_calls:
                name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                print(f"[Orchestrator OpenAI Loop] Executing tool: {name}")

                if name == "read_file": result = await self.tool_read_file(args.get("file_path"))
                elif name == "write_file": result = await self.tool_write_file(args.get("file_path"), args.get("content"))
                elif name == "list_directory": result = await self.tool_list_directory(args.get("dir_path", "."))
                elif name == "run_command": result = await self.tool_run_command(args.get("command"))
                elif name == "launch_workspace": result = await self.tool_launch_workspace(args.get("workspace_type"))
                elif name == "delegate_to_coder": result = self.tool_delegate_to_coder(args.get("prompt"))
                else: result = f"Unknown tool: {name}"

                self.openai_history.append({"role": "tool", "tool_call_id": tool_call.id, "name": name, "content": str(result)})
            loop_count += 1
        return "Error: Maximum agent loop iterations exceeded."

    async def _chat_anthropic(self, user_message: str) -> str:
        tools_schema = [
            {"name": "read_file", "description": "Read the contents of a file.", "input_schema": {"type": "object", "properties": {"file_path": {"type": "string"}}, "required": ["file_path"]}},
            {"name": "write_file", "description": "Write or overwrite content in a file.", "input_schema": {"type": "object", "properties": {"file_path": {"type": "string"}, "content": {"type": "string"}}, "required": ["file_path", "content"]}},
            {"name": "list_directory", "description": "List files and folders in a path.", "input_schema": {"type": "object", "properties": {"dir_path": {"type": "string"}}}},
            {"name": "run_command", "description": "Execute a terminal shell command.", "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
            {"name": "launch_workspace", "description": "Launch a specific system workspace layout ('work' maps to Desktop, 'personal' maps to project workspace folder).", "input_schema": {"type": "object", "properties": {"workspace_type": {"type": "string"}}, "required": ["workspace_type"]}},
            {"name": "delegate_to_coder", "description": "Delegate a coding task to the coder assistant.", "input_schema": {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}}
        ]

        self.anthropic_history.append({"role": "user", "content": user_message})

        loop_count = 0
        while loop_count < 10:
            response = self.anthropic_client.messages.create(
                model=self.anthropic_model,
                max_tokens=4096,
                system=self.system_instruction,
                messages=self.anthropic_history,
                tools=tools_schema,
            )
            self.anthropic_history.append({"role": "assistant", "content": response.content})

            tool_uses = [block for block in response.content if block.type == "tool_use"]
            if not tool_uses:
                texts = [block.text for block in response.content if block.type == "text"]
                return "\n".join(texts) or "No response from Claude."

            tool_results = []
            for tool_use in tool_uses:
                name = tool_use.name
                args = tool_use.input or {}
                print(f"[Orchestrator Anthropic Loop] Executing tool: {name}")

                if name == "read_file": result = await self.tool_read_file(args.get("file_path"))
                elif name == "write_file": result = await self.tool_write_file(args.get("file_path"), args.get("content"))
                elif name == "list_directory": result = await self.tool_list_directory(args.get("dir_path", "."))
                elif name == "run_command": result = await self.tool_run_command(args.get("command"))
                elif name == "launch_workspace": result = await self.tool_launch_workspace(args.get("workspace_type"))
                elif name == "delegate_to_coder": result = self.tool_delegate_to_coder(args.get("prompt"))
                else: result = f"Unknown tool: {name}"

                tool_results.append({"type": "tool_result", "tool_use_id": tool_use.id, "content": str(result)})

            self.anthropic_history.append({"role": "user", "content": tool_results})
            loop_count += 1
        return "Error: Maximum agent loop iterations exceeded."

    def _chat_mock(self, user_message: str) -> str:
        return f"--- DRY RUN (MOCK) ---\nRequest: {user_message}"
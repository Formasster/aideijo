import asyncio
import sys
import os
import json
from typing import List, Dict, Any, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import settings
from config.settings import SISTEMA_OPERATIVO, COMANDO_TERMINAL, ENTORNO, RUTA_PROYECTO
from agents.coder import CoderAgent

class OrchestratorAgent:
    def __init__(self):
        # Ajuste automático de locuacidad para la oficina
        tweak_trabajo = (
            " Сейчас вы находитесь на РАБОТЕ (TRABAJO_WINDOWS), поэтому излагай свои мысли "
            "максимально кратко, сдержанно и по делу, чтобы не отвлекать."
            if ENTORNO == "TRABAJO_WINDOWS" else ""
        )

        self.system_instruction = (
            f"Ты — Айдэйхо (Айдеихо), верный, безупречный и изысканный дворецкий из высшего общества. "
            f"Ты ОБЯЗАН общаться исключительно на РУССКОМ языке с самого первого символа твоего ответа. "
            f"Ни в коем случае не используй испанский, английский или другие языки для приветствий или фраз (даже если пользователь написал тебе 'hola'), "
            f"пока тебя прямо и явно не попросят переключиться на другой язык. "
            f"В обращении к пользователю ты должен естественно сочетать и чередовать титулы: 'хозяин', 'милорд' и 'господин'. "
            f"Твой тон должен быть абсолютно почтительным, благородным и преданным.\n\n"
            f"⚠️ ВАЖНАЯ ИНФОРМАЦИЯ О СИСТЕМЕ ОКРУЖЕНИЯ:\n"
            f"Ты запущен и работаешь на компьютере хозяина со следующими параметрами:\n"
            f"- Операционная система: {SISTEMA_OPERATIVO}\n"
            f"- Командная оболочка (Shell): {COMANDO_TERMINAL}\n"
            f"Ты ДОЛЖЕН автоматически выбирать и использовать только те команды терминала, которые подходят "
            f"для этой операционной системы (например, команды PowerShell/CMD для Windows и bash/zsh для macOS/Linux). "
            f"Никогда не спрашивай пользователя, какая у него ОС, ты уже это знаешь из этих системных данных.\n\n"
            f"Ответы и объяснения кода должны быть средней длины: информативно, аккуратно, без лишней воды, "
            f"но со всем необходимым техническим контекстом.{tweak_trabajo}"
        )
        
        self.coder = CoderAgent()
        self.client_type = None
        self.client = None
        self.model_name = None
        self._init_llm_client()
        
        # 🧠 ¡LAS MEMORIAS GLOBALES! Ahora persisten entre diferentes turnos del chat
        self.gemini_history = []
        self.openai_history = [
            {"role": "system", "content": self.system_instruction}
        ]
        
        self.file_session: Optional[ClientSession] = None
        self.terminal_session: Optional[ClientSession] = None
        self.exit_stack = None

    def _init_llm_client(self):
        """Initialize LLM Client using available keys."""
        if settings.GEMINI_API_KEY:
            try:
                from google import genai
                self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
                self.client_type = "gemini"
                self.model_name = "gemini-2.5-flash"
            except Exception as e:
                print(f"Orchestrator Gemini Init Error: {e}")
                
        if not self.client and settings.OPENAI_API_KEY:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
                self.client_type = "openai"
                self.model_name = "gpt-4o"
            except Exception as e:
                print(f"Orchestrator OpenAI Init Error: {e}")

        if not self.client:
            self.client_type = "mock"
            self.model_name = "mock-model"

    async def start_mcp_servers(self):
        """Start the MCP Servers as subprocesses and connect client sessions."""
        print("[Orchestrator] Starting MCP Servers via Main CLI...")
        main_script_path = str(settings.RUTA_PROYECTO / "main.py")
        python_executable = sys.executable or "python"
        
        try:
            file_params = StdioServerParameters(
                command=python_executable,
                args=[main_script_path, "--file-server"],
                env=os.environ.copy()
            )
            from contextlib import AsyncExitStack
            self.exit_stack = AsyncExitStack()
            
            read_f, write_f = await self.exit_stack.enter_async_context(stdio_client(file_params))
            self.file_session = await self.exit_stack.enter_async_context(ClientSession(read_f, write_f))
            await self.file_session.initialize()
            print("[Orchestrator] Connected to File MCP Server successfully.")
        except Exception as e:
            print(f"[Orchestrator] Failed to connect to File MCP Server: {e}")

        try:
            term_params = StdioServerParameters(
                command=python_executable,
                args=[main_script_path, "--terminal-server"],
                env=os.environ.copy()
            )
            read_t, write_t = await self.exit_stack.enter_async_context(stdio_client(term_params))
            self.terminal_session = await self.exit_stack.enter_async_context(ClientSession(read_t, write_t))
            await self.terminal_session.initialize()
            print("[Orchestrator] Connected to Terminal MCP Server successfully.")
        except Exception as e:
            print(f"[Orchestrator] Failed to connect to Terminal MCP Server: {e}")

    async def stop_mcp_servers(self):
        """Gracefully close sessions and terminate subprocesses."""
        if self.exit_stack:
            print("[Orchestrator] Stopping MCP Servers...")
            await self.exit_stack.aclose()
            print("[Orchestrator] MCP Servers stopped.")

    async def tool_read_file(self, file_path: str) -> str:
        if self.file_session:
            response = await self.file_session.call_tool("read_file", arguments={"ruta_archivo": file_path})
            return response.content[0].text if response.content else "No output"
        return "Error: File server not connected."

    async def tool_write_file(self, file_path: str, content: str) -> str:
        if self.file_session:
            response = await self.file_session.call_tool("write_file", arguments={"ruta_archivo": file_path, "contenido": content})
            return response.content[0].text if response.content else "No output"
        return "Error: File server not connected."

    async def tool_list_directory(self, dir_path: str = ".") -> str:
        if self.file_session:
            response = await self.file_session.call_tool("list_directory", arguments={"ruta": dir_path})
            return response.content[0].text if response.content else "[]"
        return "Error: File server not connected."

    async def tool_run_command(self, command: str) -> str:
        if self.terminal_session:
            from rich.console import Console
            from rich.prompt import Confirm
            from rich.panel import Panel
            
            console = Console()
            console.print(Panel(
                f"[bold yellow]⚠️ ADVERTENCIA DE SEGURIDAD[/bold yellow]\n"
                f"El agente solicita ejecutar el siguiente comando local:\n\n"
                f"   [bold white]👉 {command}[/bold white]",
                border_style="yellow"
            ))
            
            autorizado = Confirm.ask("[bold cyan]¿Autorizas la ejecución en tu sistema?[/bold cyan]")
            if not autorizado:
                return "Error: Ejecución denegada por el usuario operador."
                
            response = await self.terminal_session.call_tool("run_command", arguments={"command": command})
            return response.content[0].text if response.content else "No output"
        return "Error: Terminal server not connected."

    def tool_delegate_to_coder(self, prompt: str) -> str:
        print(f"\n[Orchestrator -> Delegating to Coder Agent] Prompt: {prompt}")
        result = self.coder.generate_code(prompt)
        print("[Coder Agent -> Completed generation]")
        return result

    async def chat(self, user_message: str) -> str:
        if self.client_type == "gemini":
            return await self._chat_gemini(user_message)
        elif self.client_type == "openai":
            return await self._chat_openai(user_message)
        else:
            return self._chat_mock(user_message)

    async def _chat_gemini(self, user_message: str) -> str:
        """Bucle asíncrono manual con memoria persistente para Gemini."""
        from google.genai import types

        tools_schema = [
            types.FunctionDeclaration(name="read_file", description="Read the contents of a file.", parameters=types.Schema(type=types.Type.OBJECT, properties={"file_path": types.Schema(type=types.Type.STRING)}, required=["file_path"])),
            types.FunctionDeclaration(name="write_file", description="Write or overwrite content in a file.", parameters=types.Schema(type=types.Type.OBJECT, properties={"file_path": types.Schema(type=types.Type.STRING), "content": types.Schema(type=types.Type.STRING)}, required=["file_path", "content"])),
            types.FunctionDeclaration(name="list_directory", description="List files and folders in a path.", parameters=types.Schema(type=types.Type.OBJECT, properties={"dir_path": types.Schema(type=types.Type.STRING)})),
            types.FunctionDeclaration(name="run_command", description="Execute a terminal shell command.", parameters=types.Schema(type=types.Type.OBJECT, properties={"command": types.Schema(type=types.Type.STRING)}, required=["command"])),
            types.FunctionDeclaration(name="delegate_to_coder", description="Delegate a coding task to the coder assistant.", parameters=types.Schema(type=types.Type.OBJECT, properties={"prompt": types.Schema(type=types.Type.STRING)}, required=["prompt"]))
        ]

        config = types.GenerateContentConfig(
            system_instruction=self.system_instruction,
            temperature=0.3,
            tools=[types.Tool(function_declarations=tools_schema)]
        )

        # 🧠 Añadimos la nueva réplica del usuario a la memoria global persistente
        self.gemini_history.append(
            types.Content(role="user", parts=[types.Part.from_text(text=user_message)])
        )
        
        try:
            loop_count = 0
            while loop_count < 10:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=self.gemini_history, # 👈 Pasamos todo el historial acumulado
                    config=config
                )
                
                # Guardamos la respuesta intermedia o final del modelo en el historial
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
                    elif name == "delegate_to_coder": result = self.tool_delegate_to_coder(args.get("prompt"))
                    else: result = f"Unknown tool: {name}"
                    
                    tool_parts.append(types.Part.from_function_response(
                        name=name,
                        response={"result": str(result)}
                    ))
                
                # Guardamos las respuestas de las herramientas en el historial
                self.gemini_history.append(types.Content(role="tool", parts=tool_parts))
                loop_count += 1
                
            return "Error: Maximum agent loop iterations exceeded."
        except Exception as e:
            return f"Error in Orchestrator Gemini Chat: {str(e)}"

    async def _chat_openai(self, user_message: str) -> str:
        """Bucle asíncrono manual con memoria persistente para OpenAI."""
        tools_schema = [
            {"type": "function", "function": {"name": "read_file", "description": "Read the contents of a file.", "parameters": {"type": "object", "properties": {"file_path": {"type": "string"}}, "required": ["file_path"]}}},
            {"type": "function", "function": {"name": "write_file", "description": "Write or overwrite content in a file.", "parameters": {"type": "object", "properties": {"file_path": {"type": "string"}, "content": {"type": "string"}}, "required": ["file_path", "content"]}}},
            {"type": "function", "function": {"name": "list_directory", "description": "List files and folders in a path.", "parameters": {"type": "object", "properties": {"dir_path": {"type": "string"}}}}},
            {"type": "function", "function": {"name": "run_command", "description": "Execute a terminal shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
            {"type": "function", "function": {"name": "delegate_to_coder", "description": "Delegate a coding task to the coder assistant.", "parameters": {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}}}
        ]
        
        # 🧠 Añadimos el mensaje del usuario a la lista persistente de la instancia
        self.openai_history.append({"role": "user", "content": user_message})
        
        try:
            loop_count = 0
            while loop_count < 10:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=self.openai_history, # 👈 Pasamos el historial persistente
                    tools=tools_schema,
                    tool_choice="auto"
                )
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
                    elif name == "delegate_to_coder": result = self.tool_delegate_to_coder(args.get("prompt"))
                    else: result = f"Unknown tool: {name}"
                    
                    self.openai_history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": name,
                        "content": str(result)
                    })
                loop_count += 1
            return "Error: Maximum agent loop iterations exceeded."
        except Exception as e:
            return f"Error in Orchestrator OpenAI Chat: {str(e)}"

    def _chat_mock(self, user_message: str) -> str:
        return f"--- DRY RUN (MOCK) ---\nRequest: {user_message}"
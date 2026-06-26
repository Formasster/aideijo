import sys
import os
import argparse
import asyncio
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.text import Text

# Add current directory to path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from config import settings
from agents.orchestrator import OrchestratorAgent

console = Console()

async def run_interactive_chat():
    console.print(Panel(
        Text("Welcome to Aideijo (ADK) Orchestrator Interface\n", style="bold green") +
        Text(f"OS Detected: {settings.SISTEMA_OPERATIVO} | Shell: {settings.COMANDO_TERMINAL}\n", style="cyan") +
        Text("Type 'exit' or 'quit' to close the session.", style="italic yellow"),
        title="[bold white]Aideijo CLI[/bold white]",
        border_style="green"
    ))

    # Initialize agent
    agent = OrchestratorAgent()
    
    # Check if API Keys are missing
    if not settings.GEMINI_API_KEY and not settings.OPENAI_API_KEY:
        console.print("[yellow]Warning: No LLM API keys found in settings. Running in mock/dry-run mode.[/yellow]")
        console.print("[yellow]Please copy .env.example to .env and configure your keys.[/yellow]\n")

    # Start MCP subprocess servers
    await agent.start_mcp_servers()
    
    try:
        while True:
            try:
                user_input = Prompt.ask("\n[bold green]You[/bold green]")
                if user_input.strip().lower() in ["exit", "quit"]:
                    console.print("[bold red]Shutting down Aideijo...[/bold red]")
                    break
                if not user_input.strip():
                    continue

                console.print("[dim cyan]🤖 Айдеихо думает...[/dim cyan]")
                response = await agent.chat(user_input)

                console.print(Panel(response, title="[bold blue]Айдеихо[/bold blue]", border_style="blue"))
            except KeyboardInterrupt:
                console.print("\n[bold red]Interrupted. Shutting down...[/bold red]")
                break
            except Exception as e:
                console.print(f"[bold red]Error in chat loop: {e}[/bold red]")
    finally:
        await agent.stop_mcp_servers()

def run_file_server():
    console.print("[bold cyan]Starting File MCP Server...[/bold cyan]")
    from mcp_servers.file_server import mcp
    mcp.run()

def run_terminal_server():
    console.print("[bold cyan]Starting Terminal MCP Server...[/bold cyan]")
    from mcp_servers.terminal_server import mcp
    mcp.run()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Aideijo - Agentic Programming Assistant")
    parser.add_argument("--file-server", action="store_true", help="Run only the File MCP Server")
    parser.add_argument("--terminal-server", action="store_true", help="Run only the Terminal MCP Server")
    
    args = parser.parse_args()

    if args.file_server:
        run_file_server()
    elif args.terminal_server:
        run_terminal_server()
    else:
        # Default behavior: run interactive chat
        asyncio.run(run_interactive_chat())

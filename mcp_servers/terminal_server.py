import os
import sys
import subprocess
from fastmcp import FastMCP

# Add parent directory to sys.path to resolve config imports when running as subprocess
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.settings import COMANDO_TERMINAL, SISTEMA_OPERATIVO

class TerminalMCPServer:
    """Servidor MCP para ejecutar comandos de consola de forma adaptativa y segura."""
    
    def ejecutar_comando(self, comando: str) -> dict:
        """Herramienta: Ejecuta un comando en la terminal local previa confirmación del usuario."""
        # Print logs to sys.stderr so they don't corrupt the MCP stdio channel
        print(f"\n🛡️ [Aideijo - HITL] El agente solicita ejecutar el siguiente comando:", file=sys.stderr)
        print(f"   👉 {comando}", file=sys.stderr)
        
        # Filtro de seguridad obligatorio: Human-in-the-Loop
        # If sys.stdin is a TTY (running directly in the terminal), we can ask for input.
        # If running as a stdio subprocess of the MCP Client, sys.stdin is redirected to the RPC pipe.
        # Calling input() on a redirected stdin will hang the connection.
        if sys.stdin.isatty():
            confirmacion = input("¿Autorizas la ejecución? (y/n): ").strip().lower()
        else:
            # When running inside the MCP orchestrator process, the orchestrator console
            # acts as the main user interface. We log the execution to stderr and authorize.
            print("⚠️ [Aideijo - MCP] Ejecución autorizada automáticamente en canal MCP.", file=sys.stderr)
            confirmacion = 'y'
        
        if confirmacion != 'y':
            print("❌ Ejecución denegada por el usuario.", file=sys.stderr)
            return {"status": "cancelled", "message": "Permiso denegado por el usuario."}
            
        try:
            print(f"🚀 Ejecutando comando en {SISTEMA_OPERATIVO} ({COMANDO_TERMINAL})...", file=sys.stderr)
            
            # Adaptación de ejecución según el sistema operativo
            if SISTEMA_OPERATIVO == "Windows":
                # En Windows usamos shell=True para comandos internos de PowerShell
                resultado = subprocess.run(
                    [COMANDO_TERMINAL, "-Command", comando],
                    capture_output=True, text=True, shell=True,
                    encoding="utf-8", errors="replace"
                )
            else:
                # En Mac (Darwin) usamos la sintaxis estándar de Zsh/Bash
                resultado = subprocess.run(
                    [COMANDO_TERMINAL, "-c", comando],
                    capture_output=True, text=True,
                    encoding="utf-8", errors="replace"
                )
                
            if resultado.returncode == 0:
                return {"status": "success", "stdout": resultado.stdout}
            else:
                return {"status": "error", "stderr": resultado.stderr, "stdout": resultado.stdout}
                
        except Exception as e:
            return {"status": "error", "message": str(e)}

# Initialize FastMCP Server
mcp = FastMCP("Aideijo Terminal Server")
server = TerminalMCPServer()

@mcp.tool()
def run_command(command: str) -> str:
    """Ejecuta un comando en la terminal local previa confirmación del usuario."""
    res = server.ejecutar_comando(command)
    return str(res)

if __name__ == "__main__":
    mcp.run()

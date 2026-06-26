import os
import sys
import subprocess
from fastmcp import FastMCP

# Add parent directory to sys.path to resolve config imports when running as subprocess
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.settings import COMANDO_TERMINAL, SISTEMA_OPERATIVO

class TerminalMCPServer:
    """MCP Server to execute terminal shell commands adaptively and securely."""
    
    def execute_command(self, command: str) -> dict:
        """Executes a local shell command and returns the execution result."""
        try:
            if SISTEMA_OPERATIVO == "Windows":
                result = subprocess.run(
                    [COMANDO_TERMINAL, "-Command", command],
                    capture_output=True, text=True, shell=True,
                    encoding="utf-8", errors="replace"
                )
            else:
                result = subprocess.run(
                    [COMANDO_TERMINAL, "-c", command],
                    capture_output=True, text=True,
                    encoding="utf-8", errors="replace"
                )
                
            if result.returncode == 0:
                return {"status": "success", "stdout": result.stdout}
            else:
                return {"status": "error", "stderr": result.stderr, "stdout": result.stdout}
                
        except Exception as e:
            return {"status": "error", "message": str(e)}

# Initialize FastMCP Server
mcp = FastMCP("Aideijo Terminal Server")
server = TerminalMCPServer()

@mcp.tool()
def run_command(command: str) -> str:
    """Execute a terminal shell command on the local system."""
    return str(server.execute_command(command))

if __name__ == "__main__":
    mcp.run()
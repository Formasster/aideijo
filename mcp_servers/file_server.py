import os
import sys
from pathlib import Path
from fastmcp import FastMCP

# Add parent directory to sys.path to resolve config imports when running as subprocess
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.settings import RUTA_HOME, RUTA_PROYECTO

class FileMCPServer:
    """MCP Server acting as the secure file system interface for Aideijo."""
    
    def __init__(self):
        # Define secure zones to prevent accidental out-of-bounds operations
        self.allowed_zones = {
            "project": RUTA_PROYECTO,
            "home": RUTA_HOME
        }

    def _validate_path(self, target_path: str) -> Path:
        """Resolves to an absolute path and verifies it is inside allowed secure zones."""
        resolved_path = Path(target_path).resolve()
        is_safe = any(resolved_path.is_relative_to(zone) for zone in self.allowed_zones.values())
        if not is_safe:
            raise PermissionError(f"Access denied. Path {target_path} is outside secure boundaries.")
        return resolved_path

    def list_directory(self, dir_path: str = "."):
        """Lists files and directories inside a specific path."""
        try:
            target = Path(dir_path) if Path(dir_path).is_absolute() else RUTA_PROYECTO / dir_path
            validated_path = self._validate_path(str(target))
            elements = os.listdir(validated_path)
            return {"status": "success", "data": elements}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def read_file(self, file_path: str):
        """Reads the text content of a file."""
        try:
            target = Path(file_path) if Path(file_path).is_absolute() else RUTA_PROYECTO / file_path
            validated_path = self._validate_path(str(target))
            content = validated_path.read_text(encoding="utf-8")
            return {"status": "success", "content": content}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def write_file(self, file_path: str, content: str):
        """Creates or overwrites a file with new content."""
        try:
            target = Path(file_path) if Path(file_path).is_absolute() else RUTA_PROYECTO / file_path
            validated_path = self._validate_path(str(target))
            validated_path.parent.mkdir(parents=True, exist_ok=True)
            validated_path.write_text(content, encoding="utf-8")
            return {"status": "success", "message": f"File {validated_path.name} saved successfully."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

# Initialize FastMCP Server
mcp = FastMCP("Aideijo File Server")
server = FileMCPServer()

@mcp.tool()
def list_directory(dir_path: str = ".") -> str:
    """List files and folders inside a directory path."""
    return str(server.list_directory(dir_path))

@mcp.tool()
def read_file(file_path: str) -> str:
    """Read the full text content of a file."""
    return str(server.read_file(file_path))

@mcp.tool()
def write_file(file_path: str, content: str) -> str:
    """Create or overwrite a file with specific content."""
    return str(server.write_file(file_path, content))

if __name__ == "__main__":
    mcp.run()
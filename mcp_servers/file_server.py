import os
import sys
from pathlib import Path
from fastmcp import FastMCP

# Add parent directory to sys.path to resolve config imports when running as subprocess
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.settings import RUTA_HOME, RUTA_PROYECTO

class FileMCPServer:
    """Servidor MCP que actúa como los ojos y manos de Aideijo en el sistema de archivos."""
    
    def __init__(self):
        # Definimos zonas seguras para evitar que el agente borre archivos del sistema por error
        self.zonas_permitidas = {
            "proyecto": RUTA_PROYECTO,
            "home": RUTA_HOME
        }

    def _validar_ruta(self, ruta: str) -> Path:
        """Convierte a ruta absoluta y valida que sea segura."""
        ruta_p = Path(ruta).resolve()
        # Por seguridad, verificamos si está dentro de las zonas permitidas
        dentro_de_zona = any(ruta_p.is_relative_to(zona) for zona in self.zonas_permitidas.values())
        if not dentro_de_zona:
            raise PermissionError(f"❌ Acceso denegado. La ruta {ruta} está fuera del entorno seguro.")
        return ruta_p

    def list_directory(self, ruta: str = "."):
        """Herramienta: Lista los archivos y carpetas de un directorio."""
        try:
            # Si es una ruta relativa, la tomamos desde la raíz del proyecto
            ruta_objetivo = Path(ruta) if Path(ruta).is_absolute() else RUTA_PROYECTO / ruta
            ruta_validada = self._validar_ruta(str(ruta_objetivo))
            
            elementos = os.listdir(ruta_validada)
            print(f"📁 [Aideijo - MCP] Listando contenido de: {ruta_validada}")
            return {"status": "success", "data": elementos}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def read_file(self, ruta_archivo: str):
        """Herramienta: Lee el contenido de un archivo de texto (Código, Markdown, etc)."""
        try:
            ruta_objetivo = Path(ruta_archivo) if Path(ruta_archivo).is_absolute() else RUTA_PROYECTO / ruta_archivo
            ruta_validada = self._validar_ruta(str(ruta_objetivo))
            
            contenido = ruta_validada.read_text(encoding="utf-8")
            print(f"📖 [Aideijo - MCP] Leyendo archivo: {ruta_validada.name}")
            return {"status": "success", "content": contenido}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def write_file(self, ruta_archivo: str, contenido: str):
        """Herramienta: Crea o sobreescribe un archivo con nuevo contenido."""
        try:
            ruta_objetivo = Path(ruta_archivo) if Path(ruta_archivo).is_absolute() else RUTA_PROYECTO / ruta_archivo
            ruta_validada = self._validar_ruta(str(ruta_objetivo))
            
            # Asegurar que las carpetas intermedias existan
            ruta_validada.parent.mkdir(parents=True, exist_ok=True)
            ruta_validada.write_text(contenido, encoding="utf-8")
            print(f"💾 [Aideijo - MCP] Archivo guardado con éxito: {ruta_validada.name}")
            return {"status": "success", "message": f"Archivo {ruta_validada.name} guardado."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

# Initialize FastMCP Server
mcp = FastMCP("Aideijo File Server")
server = FileMCPServer()

@mcp.tool()
def list_directory(ruta: str = ".") -> str:
    """Lista los archivos y carpetas de un directorio."""
    res = server.list_directory(ruta)
    return str(res)

@mcp.tool()
def read_file(ruta_archivo: str) -> str:
    """Lee el contenido de un archivo de texto (Código, Markdown, etc)."""
    res = server.read_file(ruta_archivo)
    return str(res)

@mcp.tool()
def write_file(ruta_archivo: str, contenido: str) -> str:
    """Crea o sobreescribe un archivo con nuevo contenido."""
    res = server.write_file(ruta_archivo, contenido)
    return str(res)

if __name__ == "__main__":
    mcp.run()

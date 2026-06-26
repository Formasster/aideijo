import os
import sys
import platform
from pathlib import Path
from dotenv import load_dotenv

# Ensure terminal outputs UTF-8 to support emojis on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# 1. DETECCIÓN DEL SISTEMA OPERATIVO
# platform.system() devuelve 'Windows' en tu trabajo y 'Darwin' en tu Mac de casa
SISTEMA_OPERATIVO = platform.system()

# 2. GESTIÓN DE RUTAS DINÁMICAS (Multiplataforma)
# Path(__file__) asegura que las rutas se calculen solas sin importar el OS
RUTA_PROYECTO = Path(__file__).resolve().parent.parent
RUTA_HOME = Path.home()

# 3. CARGA INTELIGENTE DEL ENTORNO (.env)
ruta_env = RUTA_PROYECTO / ".env"
if ruta_env.exists():
    load_dotenv(ruta_env)
else:
    print("⚠️ [Aideijo] Alerta: No se encontró el archivo .env local.")

# 4. VARIABLES DE CONFIGURACIÓN
ENTORNO = os.getenv("ENTORNO", "DESCONOCIDO")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
USE_OLLAMA = os.getenv("USE_OLLAMA", "False").lower() in ("true", "1", "t")

# 5. CONFIGURACIÓN DE HERRAMIENTAS SEGÚN EL ENTORNO
if SISTEMA_OPERATIVO == "Windows":
    # Configuración para la oficina (Windows)
    COMANDO_TERMINAL = "powershell.exe"
    LOGS_DIR = RUTA_PROYECTO / "logs"
else:
    # Configuración para casa (Mac / Darwin)
    COMANDO_TERMINAL = "zsh"
    LOGS_DIR = RUTA_PROYECTO / "logs"

# Asegurar que la carpeta de logs exista localmente
LOGS_DIR.mkdir(exist_ok=True)

def info_sistema():
    """Función de diagnóstico para ver dónde está despertando Aideijo"""
    print(f"🤖 [Aideijo] Despertando en entorno: {ENTORNO}")
    # Usamos expresiones sencillas sin LaTeX para el reporte en texto plano
    print(f"💻 Sistema Operativo detectado: {SISTEMA_OPERATIVO}")
    print(f"📁 Ruta del proyecto: {RUTA_PROYECTO}")
    print(f"🏠 Tu directorio Home local: {RUTA_HOME}")
    print(f"⚙️  ¿Usa Ollama local?: {USE_OLLAMA}")
    print("-" * 50)

if __name__ == "__main__":
    # Si ejecutas este archivo directamente, probará la configuración
    info_sistema()

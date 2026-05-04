"""
Roda localmente para empacotar a sessão do WhatsApp.
Saída: string base64 para colar em WHATSAPP_SESSION_B64 no Railway.
"""
import os
import base64
import zipfile
import io

SESSION_DIR = os.path.join(os.path.dirname(__file__), ".whatsapp_session")

buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(SESSION_DIR):
        # Pula cache de GPU / logs — não são necessários para a sessão
        dirs[:] = [d for d in dirs if d not in ("GPUCache", "GrShaderCache", "ShaderCache")]
        for file in files:
            filepath = os.path.join(root, file)
            arcname = os.path.relpath(filepath, os.path.dirname(SESSION_DIR))
            zf.write(filepath, arcname)

b64 = base64.b64encode(buf.getvalue()).decode()
print(f"Tamanho zip: {len(buf.getvalue()) // 1024} KB  |  base64: {len(b64)} chars")
print()
print("Cole no Railway (Settings → Variables):")
print(f"WHATSAPP_SESSION_B64={b64}")

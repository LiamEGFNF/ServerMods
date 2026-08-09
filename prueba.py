import os
import json
import time
import urllib.request
import ssl
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Variables de entorno configuradas en Render
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "")

# Caché global únicamente para metadatos (JSON ligero en RAM)
CACHE_MODS = []

def actualizar_cache_discord():
    global CACHE_MODS
    while True:
        if DISCORD_TOKEN and CHANNEL_ID:
            try:
                url = f"https://discord.com/api/v9/channels/{CHANNEL_ID}/messages?limit=50"
                headers = {
                    "Authorization": f"Bot {DISCORD_TOKEN}",
                    "User-Agent": "Mozilla/5.0"
                }
                req = urllib.request.Request(url, headers=headers)
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE

                with urllib.request.urlopen(req, context=ctx, timeout=10) as res:
                    data = json.loads(res.read().decode('utf-8'))
                    
                    nuevos_mods = []
                    for msg in data:
                        content = msg.get("content", "")
                        attachments = msg.get("attachments", [])
                        if not attachments:
                            continue
                        
                        # Obtener la URL firmada fresca del adjunto
                        img_url = attachments[0].get("url", "")
                        
                        nombre = "Sin título"
                        autor = msg.get("author", {}).get("username", "Anon")
                        descripcion = content

                        lines = content.split("\n")
                        for line in lines:
                            if line.lower().startswith("nombre:"):
                                nombre = line.split(":", 1)[1].strip()
                            elif line.lower().startswith("autor:"):
                                autor = line.split(":", 1)[1].strip()
                            elif line.lower().startswith("descripcion:"):
                                descripcion = line.split(":", 1)[1].strip()

                        nuevos_mods.append({
                            "nombre": nombre,
                            "autor": autor,
                            "descripcion": descripcion,
                            "imagen_url": img_url
                        })

                    CACHE_MODS = nuevos_mods
            except Exception as e:
                print(f">>> [ERROR DISCORD CACHE] {e}")
        else:
            print(">>> [WARN] DISCORD_TOKEN o CHANNEL_ID no estan configurados en las Variables de Entorno.")

        time.sleep(30)

class ProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. Endpoint para entregar el JSON con la lista de mods
        if self.path == "/mods":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            response = json.dumps(CACHE_MODS)
            self.wfile.write(response.encode('utf-8'))

        # 2. Endpoint Proxy para imágenes (Descarga al vuelo, CERO consumo residual de RAM)
        elif self.path.startswith("/image?url="):
            img_url = self.path.split("/image?url=", 1)[1]
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                req = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0"})
                
                with urllib.request.urlopen(req, context=ctx, timeout=10) as res:
                    img_bytes = res.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(img_bytes)
            except Exception as e:
                print(f">>> [ERROR PROXY IMAGEN] {e}")
                self.send_response(500)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        return  # Desactivar logs basura en la consola de Render

def run():
    port = int(os.environ.get("PORT", 10000))
    
    # Hilo secundario para refrescar el caché de Discord sin bloquear las peticiones
    t = threading.Thread(target=actualizar_cache_discord, daemon=True)
    t.start()

    print(f"==> Servidor activo en puerto {port}")
    server = HTTPServer(("0.0.0.0", port), ProxyHandler)
    server.serve_forever()

if __name__ == "__main__":
    run()

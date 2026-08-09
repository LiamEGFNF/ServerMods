import os
import json
import time
import urllib.request
import urllib.error
import ssl
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Variables de entorno en Render
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "").strip()
CHANNEL_ID = os.environ.get("CHANNEL_ID", "").strip()

# User-Agent oficial para que Cloudflare deje de bloquear la petición
USER_AGENT = "DiscordBot (https://github.com, 1.0)"

# Caché en RAM para metadatos
CACHE_MODS = []

def actualizar_cache_discord():
    global CACHE_MODS
    while True:
        if DISCORD_TOKEN and CHANNEL_ID:
            try:
                # API v10 de Discord
                url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages?limit=50"
                
                # Sanitizamos el token por si le metieron la palabra 'Bot ' o espacios de más
                clean_token = DISCORD_TOKEN.replace("Bot ", "").strip()
                headers = {
                    "Authorization": f"Bot {clean_token}",
                    "User-Agent": USER_AGENT
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
                    print(f">>> [DISCORD OK] Mods cargados con éxito: {len(CACHE_MODS)}", flush=True)

            except urllib.error.HTTPError as e:
                try:
                    error_body = e.read().decode('utf-8')
                except Exception:
                    error_body = "No se pudo leer la respuesta"
                print(f">>> [ERROR DISCORD API] Código HTTP: {e.code} | Respuesta de Discord: {error_body}", flush=True)

            except Exception as e:
                print(f">>> [ERROR DISCORD CACHE] Excepción inesperada: {e}", flush=True)
        else:
            print(">>> [WARN] DISCORD_TOKEN o CHANNEL_ID no están configurados en las Variables de Entorno.", flush=True)

        time.sleep(30)

class ProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Endpoint para entregar metadatos JSON a Godot
        if self.path == "/mods":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            response = json.dumps(CACHE_MODS)
            self.wfile.write(response.encode('utf-8'))

        # Proxy directo de imágenes
        elif self.path.startswith("/image?url="):
            img_url = self.path.split("/image?url=", 1)[1]
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                req = urllib.request.Request(img_url, headers={"User-Agent": USER_AGENT})
                
                with urllib.request.urlopen(req, context=ctx, timeout=10) as res:
                    img_bytes = res.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(img_bytes)
            except Exception as e:
                print(f">>> [ERROR PROXY IMAGEN] {e}", flush=True)
                self.send_response(500)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        return

def run():
    port = int(os.environ.get("PORT", 10000))
    t = threading.Thread(target=actualizar_cache_discord, daemon=True)
    t.start()

    print(f"==> Servidor activo en puerto {port}", flush=True)
    server = HTTPServer(("0.0.0.0", port), ProxyHandler)
    server.serve_forever()

if __name__ == "__main__":
    run()

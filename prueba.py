import socket
import urllib.request
import ssl
import threading
import time
import json
import re

DISCORD_TOKEN = "MTUzNTQxNDkyMTc4ODEzMzQyNw.GBrsAE.ecp1wtm9e5jVWuDAXPD7ZecrGrVxyrMiM_eI40"
CHANNEL_ID = "1527189285491572767"

CACHE_MODS = []
CACHE_IMAGENES = {}

def procesar_mensajes_discord(raw_json):
    mods = []
    try:
        mensajes = json.loads(raw_json)
        if not isinstance(mensajes, list):
            return []

        for msg in mensajes:
            content = msg.get("content", "")
            attachments = msg.get("attachments", [])

            # Buscar imagen adjunta OBLIGATORIA (.png, .jpg, etc.)
            img_url = ""
            for att in attachments:
                url = att.get("url", "")
                ext = url.split("?")[0].split(".")[-1].lower()
                if ext in ["png", "jpg", "jpeg", "webp"]:
                    img_url = url
                    break

            # SI NO TIENE IMAGEN PNG, SE IGNORA COMPLETAMENTE EL MOD
            if not img_url:
                continue

            if "nombre:" not in content.lower():
                continue

            bloques = re.split(r'(?i)(?=Nombre:)', content)

            for bloque in bloques:
                if not bloque.strip() or "nombre:" not in bloque.lower():
                    continue

                nom_match = re.search(r"Nombre:\s*(.+)", bloque, re.IGNORECASE)
                aut_match = re.search(r"Autor:\s*(.+)", bloque, re.IGNORECASE)
                desc_match = re.search(r"Descripcion:\s*(.+)", bloque, re.IGNORECASE)

                nombre = nom_match.group(1).split("\n")[0].strip() if nom_match else ""
                autor = aut_match.group(1).split("\n")[0].strip() if aut_match else msg.get("author", {}).get("username", "Desconocido")
                descripcion = desc_match.group(1).split("\n")[0].strip() if desc_match else ""

                # Limpieza de paréntesis o formato sobrante
                nombre = re.sub(r'^\((.*)\)$', r'\1', nombre)
                autor = re.sub(r'^\((.*)\)$', r'\1', autor)
                descripcion = re.sub(r'^\((.*)\)$', r'\1', descripcion)

                if nombre:
                    mods.append({
                        "nombre": nombre[:20],
                        "autor": autor[:15],
                        "descripcion": descripcion[:70],
                        "zip_url": img_url,
                        "imagen_url": img_url
                    })
    except Exception as e:
        print(f">>> [PARSER ERROR] {e}")

    return mods

def actualizar_cache_discord():
    global CACHE_MODS
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages?limit=50"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bot {DISCORD_TOKEN}",
        "User-Agent": "DiscordBot (https://godotengine.org, v1.0)"
    })
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    while True:
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
                raw_data = response.read().decode('utf-8')
                CACHE_MODS = procesar_mensajes_discord(raw_data)
                print(f">>> [CACHÉ] ¡{len(CACHE_MODS)} mods con PNG válido cargados!")
        except Exception as e:
            print(f">>> [CACHÉ ERROR] {e}")
        time.sleep(30)

threading.Thread(target=actualizar_cache_discord, daemon=True).start()

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

try:
    server_socket.bind(('127.0.0.1', 8000))
    server_socket.listen(10)
except Exception as e:
    print(f">>> [ERROR PUERTO] {e}")
    exit()

print("==================================================")
print(">>> PUENTE LISTO EN http://127.0.0.1:8000")
print("==================================================")

def descargar_imagen_discord(img_url):
    if not img_url: return b""
    if img_url in CACHE_IMAGENES: return CACHE_IMAGENES[img_url]

    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, context=ctx, timeout=8) as res:
            data = res.read()
            CACHE_IMAGENES[img_url] = data
            return data
    except Exception as e:
        print(f">>> [ERROR IMAGEN] {e}")
        return b""

while True:
    try:
        client, addr = server_socket.accept()
        request_data = client.recv(2048).decode('utf-8', errors='ignore')
        if not request_data:
            client.close()
            continue

        primera_linea = request_data.split('\r\n')[0]
        path = primera_linea.split(' ')[1] if len(primera_linea.split(' ')) > 1 else "/"

        if path == "/" or path.startswith("/mods"):
            payload = json.dumps(CACHE_MODS).encode('utf-8')
            headers = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(payload)}\r\nConnection: close\r\n\r\n"
            client.sendall(headers.encode('utf-8') + payload)

        elif path.startswith("/image?url="):
            img_target_url = path.split("/image?url=")[1]
            img_bytes = descargar_imagen_discord(img_target_url)
            headers = f"HTTP/1.1 200 OK\r\nContent-Type: image/png\r\nContent-Length: {len(img_bytes)}\r\nConnection: close\r\n\r\n"
            client.sendall(headers.encode('utf-8') + img_bytes)

        client.close()
    except Exception:
        pass

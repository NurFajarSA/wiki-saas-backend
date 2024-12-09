# app/deploy.py
import docker
import os
from dotenv import load_dotenv

load_dotenv()

DOCKER_NETWORK = os.getenv("DOCKER_NETWORK", "wikinet")
WIKI_IMAGE = "requarks/wiki:2"  # Sesuaikan versi jika diperlukan
BASE_DOMAIN = os.getenv("BASE_DOMAIN")  # e.g., domain.com

client = docker.from_env()

def ensure_network():
    try:
        client.networks.get(DOCKER_NETWORK)
    except docker.errors.NotFound:
        client.networks.create(DOCKER_NETWORK, driver="bridge")

def get_available_port(start_port=8001, end_port=9000):
    import socket
    for port in range(start_port, end_port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', port)) != 0:
                return port
    raise Exception("No available ports")

def deploy_wikijs(slug: str) -> str:
    ensure_network()
    container_name = f"wiki_{slug}"
    port = get_available_port()
    domain = f"{slug}.{BASE_DOMAIN}"
    url = f"https://{domain}"

    # Periksa apakah container sudah ada
    try:
        container = client.containers.get(container_name)
        raise Exception("Container sudah ada")
    except docker.errors.NotFound:
        pass

    # Jalankan container
    env_vars = {
        "DB_TYPE": "postgres",
        "DB_HOST": os.getenv("DB_HOST", "localhost"),
        "DB_PORT": os.getenv("DB_PORT", "5432"),
        "DB_USER": os.getenv("DB_USER"),
        "DB_PASS": os.getenv("DB_PASS"),
        "DB_NAME": os.getenv("DB_NAME"),
        "WIKI_ADMIN_EMAIL": os.getenv("WIKI_ADMIN_EMAIL"),
        "WIKI_ADMIN_PASSWORD": os.getenv("WIKI_ADMIN_PASSWORD"),
    }

    container = client.containers.run(
        WIKI_IMAGE,
        name=container_name,
        environment=env_vars,
        networks=[DOCKER_NETWORK],
        ports={'3000/tcp': port},  # Wiki.js default port adalah 3000
        detach=True,
        restart_policy={"Name": "always"},
    )

    return domain, port

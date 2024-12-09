# app/deploy.py
import docker
import os
from dotenv import load_dotenv

load_dotenv()

DOCKER_NETWORK = os.getenv("DOCKER_NETWORK", "wikinet")
WIKI_IMAGE = "requarks/wiki:2"  # Sesuaikan versi jika diperlukan

client = docker.from_env()

# Pastikan jaringan Docker ada
def ensure_network():
    try:
        client.networks.get(DOCKER_NETWORK)
    except docker.errors.NotFound:
        client.networks.create(DOCKER_NETWORK, driver="bridge")

def deploy_wikijs(slug: str) -> str:
    ensure_network()
    container_name = f"wiki_{slug}"
    domain = f"{slug}.{os.getenv('BASE_DOMAIN')}"  # Misalnya slug.domain.com
    url = f"https://{domain}"

    # Periksa apakah container sudah ada
    try:
        container = client.containers.get(container_name)
        raise Exception("Container already exists")
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

    ports = {
        # Anda bisa menentukan port yang berbeda atau menggunakan NGINX sebagai reverse proxy
    }

    container = client.containers.run(
        WIKI_IMAGE,
        name=container_name,
        environment=env_vars,
        networks=[DOCKER_NETWORK],
        detach=True,
        restart_policy={"Name": "always"},
        # Map port jika diperlukan
    )

    return url

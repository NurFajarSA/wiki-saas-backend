# app/deploy.py

import docker  # Pastikan modul docker diimpor
import os
import re
import logging
from dotenv import load_dotenv
from typing import Tuple

load_dotenv()

# Konfigurasi logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DOCKER_NETWORK = os.getenv("DOCKER_NETWORK", "wikinet")
WIKI_IMAGE = "requarks/wiki:2"  # Sesuaikan versi jika diperlukan
BASE_DOMAIN = os.getenv("BASE_DOMAIN")  # e.g., nurfajar.tech

client = docker.from_env()

def ensure_network():
    """Memastikan jaringan Docker ada, jika tidak, buat jaringan baru."""
    try:
        client.networks.get(DOCKER_NETWORK)
        logger.info(f"Jaringan Docker '{DOCKER_NETWORK}' sudah ada.")
    except docker.errors.NotFound:
        client.networks.create(DOCKER_NETWORK, driver="bridge")
        logger.info(f"Jaringan Docker '{DOCKER_NETWORK}' telah dibuat.")

def get_available_port(start_port=8001, end_port=9000) -> int:
    """Mencari port yang tersedia dalam rentang yang ditentukan."""
    import socket
    for port in range(start_port, end_port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', port)) != 0:
                logger.info(f"Port {port} tersedia.")
                return port
    raise Exception("No available ports found in the specified range.")

def deploy_wikijs(slug) -> Tuple[str, int]:


    ensure_network()
    port = get_available_port()
    container_name = f"wiki_{port}"
    domain = f"{BASE_DOMAIN}"
    url = f"https://{domain}"  # Sesuaikan jika Anda menggunakan HTTPS
    
    logger.info(f"Deploying wiki.js dengan slug '{slug}' pada domain '{domain}' dan port '{port}'.")
    
    # Periksa apakah container sudah ada
    try:
        container = client.containers.get(container_name)
        logger.error(f"Container dengan nama '{container_name}' sudah ada.")
        raise Exception("Container sudah ada")
    except docker.errors.NotFound:
        logger.info(f"Container dengan nama '{container_name}' tidak ditemukan. Melanjutkan deployment.")
    
    # Tentukan volume untuk data persistent
    volume_path = os.path.join(os.getcwd(), 'data', slug)
    os.makedirs(volume_path, exist_ok=True)
    logger.info(f"Data akan disimpan di '{volume_path}'.")
    
    # Jalankan container dengan volume
    env_vars = {
        "DB_TYPE": "postgres",
        "DB_HOST": os.getenv("DB_HOST", "db"),
        "DB_PORT": os.getenv("DB_PORT", "5432"),
        "DB_USER": os.getenv("DB_USER"),
        "DB_PASS": os.getenv("DB_PASS"),
        "DB_NAME": os.getenv("DB_NAME"),
        "WIKI_ADMIN_EMAIL": os.getenv("WIKI_ADMIN_EMAIL"),
        "WIKI_ADMIN_PASSWORD": os.getenv("WIKI_ADMIN_PASSWORD"),
    }
    
    logger.info(f"Environment variables: {env_vars}")
    
    try:
        container = client.containers.run(
            WIKI_IMAGE,
            name=container_name,
            environment=env_vars,
            network=DOCKER_NETWORK,  # Menggunakan 'network' sebagai string
            ports={'3000/tcp': port},  # Wiki.js default port adalah 3000
            volumes={volume_path: {'bind': '/wiki/data', 'mode': 'rw'}},  # Bind mount untuk data
            detach=True,
            restart_policy={"Name": "always"},
        )
        logger.info(f"Container '{container_name}' berhasil dijalankan pada port {port}.")
    except docker.errors.ContainerError as e:
        logger.error(f"Error saat menjalankan container: {e}")
        raise Exception(f"Error saat menjalankan container: {e}")
    except docker.errors.ImageNotFound as e:
        logger.error(f"Image '{WIKI_IMAGE}' tidak ditemukan: {e}")
        raise Exception(f"Image '{WIKI_IMAGE}' tidak ditemukan: {e}")
    except docker.errors.APIError as e:
        logger.error(f"API error saat menjalankan container: {e}")
        raise Exception(f"API error saat menjalankan container: {e}")
    
    return domain, port

# app/deploy.py

import docker 
import os
import logging
from dotenv import load_dotenv
from typing import Tuple
import socket
import subprocess

load_dotenv()

# Konfigurasi logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DOCKER_NETWORK = os.getenv("DOCKER_NETWORK", "wikinet")
WIKI_IMAGE = "requarks/wiki:2"  
BASE_DOMAIN = os.getenv("BASE_DOMAIN")
BASE_URL = os.getenv("BASE_URL")

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
    for port in range(start_port, end_port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', port)) != 0:
                logger.info(f"Port {port} tersedia.")
                return port
    raise Exception("No available ports found in the specified range.")

def create_database(db_name: str):
    """Buat database PostgreSQL baru."""
    try:
        subprocess.run(
            ['sudo', '-u', 'postgres', 'psql', '-c', f"CREATE DATABASE {db_name};"],
            check=True
        )
        logger.info(f"Database '{db_name}' berhasil dibuat.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Gagal membuat database '{db_name}': {e}")
        raise Exception(f"Gagal membuat database '{db_name}': {e}")

def deploy_wikijs(name: str) -> Tuple[str, int]:
    ensure_network()
    port = get_available_port()
    container_name = f"wiki_{port}"
    domain = f"{BASE_DOMAIN}"
    db_name = f"wikisaas_db_{name}"
    db_name = db_name.lower().replace("-", "_")

    logger.info(f"Deploying wiki.js dengan name '{name}' pada domain '{domain}' dan port '{port}'.")

    # Buat database untuk instance ini
    create_database(db_name)

    # Tentukan volume untuk data persistent
    volume_path = os.path.join(os.getcwd(), 'data', name)
    os.makedirs(volume_path, exist_ok=True)
    os.chmod(volume_path, 0o777)
    logger.info(f"Data akan disimpan di '{volume_path}'.")

    # Definisikan variabel lingkungan untuk Wiki.js
    env_vars = {
        "DB_TYPE": "postgres",
        "DB_HOST": os.getenv("DB_HOST", "localhost"),
        "DB_PORT": os.getenv("DB_PORT", "5432"),
        "DB_USER": os.getenv("DB_USER"),
        "DB_PASS": os.getenv("DB_PASS"),
        "DB_NAME": db_name,
        "WIKI_ADMIN_EMAIL": os.getenv("WIKI_ADMIN_EMAIL"),
        "WIKI_ADMIN_PASSWORD": os.getenv("WIKI_ADMIN_PASSWORD"),
    }

    logger.info(f"Environment variables: {env_vars}")

    # Jalankan container dengan volume
    try:
        container = client.containers.run(
            WIKI_IMAGE,
            name=container_name,
            environment=env_vars,
            network=DOCKER_NETWORK,
            ports={'3000/tcp': port}, 
            volumes={volume_path: {'bind': '/wiki/data', 'mode': 'rw'}},
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

    return BASE_URL, port

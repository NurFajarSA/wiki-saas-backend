# app/deploy.py

import docker
import os
import logging
from .database import SessionLocal
from . import models, crud, schemas
from dotenv import load_dotenv
from typing import Tuple
import socket
import time
import subprocess

load_dotenv()

# Inisialisasi logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DOCKER_NETWORK = os.getenv("DOCKER_NETWORK", "wikinet")
WIKI_IMAGE = "requarks/wiki:2" 
BASE_DOMAIN = os.getenv("BASE_DOMAIN") 

# Inisialisasi Docker client
client = docker.from_env()

def ensure_network():
    """Pastikan jaringan Docker ada, jika tidak, buat jaringan baru."""
    try:
        network = client.networks.get(DOCKER_NETWORK)
        logger.info(f"Docker network '{DOCKER_NETWORK}' sudah ada.")
    except docker.errors.NotFound:
        client.networks.create(DOCKER_NETWORK, driver="bridge")
        logger.info(f"Docker network '{DOCKER_NETWORK}' telah dibuat.")

def get_available_port(start_port=8001, end_port=9000) -> int:
    """Cari port yang tersedia dalam rentang yang ditentukan."""
    for port in range(start_port, end_port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', port)) != 0:
                logger.info(f"Port {port} tersedia.")
                return port
    raise Exception("Tidak ada port yang tersedia dalam rentang yang ditentukan.")

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

def deploy_wikijs(instance_create: schemas.InstanceCreate) -> Tuple[str, int]:
    """
    Deploy instance Wiki.js baru.

    Args:
        instance_create (schemas.InstanceCreate): Data untuk instance yang akan di-deploy.

    Returns:
        Tuple[str, int]: Domain dan port yang digunakan oleh instance.

    Raises:
        Exception: Jika deployment gagal.
    """
    db = SessionLocal()
    try:
        # Pastikan jaringan Docker tersedia
        ensure_network()

        # Cari port yang tersedia
        port = get_available_port()

        # Definisikan variabel domain dan lainnya
        domain = BASE_DOMAIN  # Menggunakan satu domain
        container_name = f"wiki_{port}"
        db_name = f"wikisaas_db_{port}"

        # Buat database untuk instance ini
        create_database(db_name)

        # Definisikan variabel lingkungan untuk Wiki.js
        env_vars = {
            "DB_TYPE": "postgres",
            "DB_HOST": os.getenv("DB_HOST", "db"),
            "DB_PORT": os.getenv("DB_PORT", "5432"),
            "DB_USER": os.getenv("DB_USER"),
            "DB_PASS": os.getenv("DB_PASS"),
            "DB_NAME": db_name,
            "WIKI_ADMIN_EMAIL": os.getenv("WIKI_ADMIN_EMAIL"),
            "WIKI_ADMIN_PASSWORD": os.getenv("WIKI_ADMIN_PASSWORD"),
        }

        # Definisikan path volume
        volume_path = os.path.join(os.getcwd(), 'data', str(port))
        os.makedirs(volume_path, exist_ok=True)
        logger.info(f"Data akan disimpan di '{volume_path}'.")

        # Jalankan container Docker
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

        # Buat record instance di database
        db_instance = crud.create_instance(db, instance_create)
        db_instance.port = port
        db_instance.container_name = container_name
        db_instance.db_name = db_name
        db_instance.status = "deployed"
        db.commit()
        db.refresh(db_instance)

        return domain, port

    except Exception as e:
        logger.error(f"Deployment gagal: {e}")
        raise e
    finally:
        db.close()

def configure_nginx(domain: str, port: int):
    """Mengonfigurasi NGINX untuk domain yang sama dengan port berbeda."""
    nginx_conf = f"""
    server {{
        listen {port} ssl;
        server_name {domain};

        ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;
        include /etc/letsencrypt/options-ssl-nginx.conf;
        ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

        location / {{
            proxy_pass http://localhost:{port};
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }}
    }}
    """

    config_path = f"/etc/nginx/sites-available/{domain}_{port}"
    symlink_path = f"/etc/nginx/sites-enabled/{domain}_{port}"

    try:
        with open(config_path, 'w') as f:
            f.write(nginx_conf)
        subprocess.run(['sudo', 'ln', '-sf', config_path, symlink_path], check=True)
        subprocess.run(['sudo', 'nginx', '-t'], check=True)
        subprocess.run(['sudo', 'systemctl', 'reload', 'nginx'], check=True)
        logger.info(f"NGINX configuration successful for domain: {domain} on port: {port}")
    except subprocess.CalledProcessError as e:
        logger.error(f"NGINX configuration failed: {e}")
        raise Exception(f"NGINX configuration failed: {e}")
    except PermissionError as e:
        logger.error(f"Permission denied during NGINX configuration: {e}")
        raise Exception(f"Permission denied during NGINX configuration: {e}")
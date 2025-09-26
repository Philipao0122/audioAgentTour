#!/bin/bash

# Actualizar e instalar dependencias del sistema
yum update -y || apt-get update -y || true

# Instalar dependencias del sistema necesarias para soundfile y otras bibliotecas
yum install -y libsndfile libpq-dev python3-dev || \
apt-get install -y libsndfile1 libpq-dev python3-dev || true

# Instalar dependencias de Python
python -m pip install --upgrade pip
python -m pip install --upgrade setuptools wheel

# Instalar las dependencias de Python
python -m pip install -r requirements.txt

# Instalar dependencias específicas para Supabase
python -m pip install --no-cache-dir \
    'supabase>=1.0.0' \
    'postgrest>=0.10.0' \
    'gotrue>=0.7.0' \
    'realtime>=0.1.12' \
    'python-jose>=3.3.0'

# Limpiar la caché de pip para reducir el tamaño del paquete
python -m pip cache purge
rm -rf /root/.cache/pip

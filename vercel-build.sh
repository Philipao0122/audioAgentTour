#!/bin/bash

# Instalar dependencias del sistema necesarias para soundfile y otras bibliotecas de audio
apt-get update
apt-get install -y libsndfile1

# Instalar dependencias de Python
pip install -r requirements.txt

# Limpiar la caché de pip para reducir el tamaño del paquete
rm -rf /root/.cache/pip

# Verificar que todas las dependencias estén instaladas
pip freeze > installed_packages.txt

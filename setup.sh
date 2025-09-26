#!/bin/bash

# Instalar dependencias del sistema necesarias para soundfile y otras bibliotecas
apt-get update && apt-get install -y \
    libsndfile1 \
    libportaudio2 \
    libasound2-dev \
    libsndfile1-dev \
    portaudio19-dev \
    python3-dev \
    python3-pip

# Instalar dependencias de Python
pip install --upgrade pip
pip install --upgrade setuptools wheel
pip install -r requirements.txt

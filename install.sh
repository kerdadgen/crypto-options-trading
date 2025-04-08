#!/bin/bash

# Script d'installation pour la stratégie de trading d'options crypto
# Ce script installe toutes les dépendances nécessaires et configure l'environnement

echo "Installation de la stratégie de trading d'options crypto..."
echo "--------------------------------------------------------"

# Vérifier si Python est installé
if command -v python3 &>/dev/null; then
    echo "Python est déjà installé."
    python3 --version
else
    echo "Installation de Python..."
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip python3-venv
fi

# Créer un environnement virtuel
echo "Création de l'environnement virtuel..."
python3 -m venv crypto_options_env

# Activer l'environnement virtuel
echo "Activation de l'environnement virtuel..."
source crypto_options_env/bin/activate

# Installer les dépendances
echo "Installation des dépendances..."
pip install aiohttp==3.8.5 pandas==2.0.3 numpy==1.24.3 matplotlib==3.7.2

# Créer les répertoires de données
echo "Création des répertoires de données..."
mkdir -p implementation/data
mkdir -p tests/data

echo "--------------------------------------------------------"
echo "Installation terminée avec succès!"
echo ""
echo "Pour utiliser la stratégie:"
echo "1. Configurez vos clés API dans implementation/config.py"
echo "2. Activez l'environnement virtuel: source crypto_options_env/bin/activate"
echo "3. Testez en paper trading: python tests/paper_trading_test.py"
echo "4. Exécutez la stratégie: python implementation/main.py"
echo ""
echo "Consultez la documentation dans le répertoire 'documentation' pour plus d'informations."

"""
Configuration pour la stratégie de trading d'options crypto.
Ce fichier contient les paramètres de configuration pour l'API Deribit et la stratégie.
"""

# Configuration de l'API
API_KEY = "YOUR_API_KEY"  # À remplacer par votre clé API Deribit
API_SECRET = "YOUR_API_SECRET"  # À remplacer par votre secret API Deribit
TEST_MODE = True  # Utiliser le testnet de Deribit

# URLs de l'API
BASE_URL = "https://test.deribit.com" if TEST_MODE else "https://www.deribit.com"
API_URL = BASE_URL + "/api/v2/"

# Paramètres de la stratégie
CAPITAL_TOTAL = 300  # Capital total en USD
CAPITAL_ACTIF = CAPITAL_TOTAL * 0.5  # Capital de trading actif (50%)
RESERVE_SECURITE = CAPITAL_TOTAL * 0.5  # Réserve de sécurité (50%)
MAX_POSITION_SIZE = CAPITAL_ACTIF * 0.1  # Taille maximale par position (10% du capital actif)
MAX_POSITIONS = 5  # Nombre maximal de positions simultanées

# Paramètres d'analyse de volatilité
IV_HV_HIGH_THRESHOLD = 1.3  # Seuil pour considérer la volatilité implicite comme élevée
IV_HV_LOW_THRESHOLD = 0.7  # Seuil pour considérer la volatilité implicite comme basse
HV_WINDOW_SHORT = 7  # Fenêtre courte pour le calcul de la volatilité historique (jours)
HV_WINDOW_MEDIUM = 14  # Fenêtre moyenne pour le calcul de la volatilité historique (jours)
HV_WINDOW_LONG = 30  # Fenêtre longue pour le calcul de la volatilité historique (jours)
HV_WEIGHTS = [0.5, 0.3, 0.2]  # Poids pour la moyenne pondérée des volatilités (court, moyen, long)

# Paramètres de gestion des positions
PROFIT_TARGET_PCT = 0.5  # Objectif de profit (50% du profit maximal)
STOP_LOSS_PCT = 0.5  # Stop-loss (50% de la perte maximale)
MIN_DAYS_TO_EXPIRY = 7  # Nombre minimal de jours avant expiration
MAX_DAYS_TO_EXPIRY = 21  # Nombre maximal de jours avant expiration
STRIKE_SPREAD_PCT = 0.05  # Écart entre les strikes pour les spreads verticaux (5%)

# Paramètres de taille des contrats
BTC_CONTRACT_SIZE = 0.01  # Taille minimale pour les contrats BTC (0.01 BTC)
ETH_CONTRACT_SIZE = 0.1  # Taille minimale pour les contrats ETH (0.1 ETH)

# Paramètres de monitoring
CHECK_INTERVAL = 3600  # Intervalle entre les vérifications (secondes)
POSITION_CHECK_INTERVAL = 14400  # Intervalle entre les vérifications des positions (secondes)

# Paramètres de logging
LOG_LEVEL = "INFO"  # Niveau de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_FILE = "crypto_options_trading.log"  # Fichier de log

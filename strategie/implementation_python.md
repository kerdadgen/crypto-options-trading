# Implémentation d'une stratégie de volatilité pour options crypto

Cette stratégie se concentre sur l'arbitrage de volatilité implicite et l'exploitation des skews de volatilité sur le marché des options crypto, spécifiquement adaptée pour un débutant avec un capital limité de 300$.

## Exemples concrets de trades

### Exemple 1: Arbitrage de volatilité implicite avec spreads verticaux

```python
# Exemple de position: Bear Call Spread sur BTC
# Lorsque la volatilité implicite est anormalement élevée (IV/HV > 1.3)

# Vendre un call ATM (à la monnaie)
# Prix BTC actuel: 65,000$
# Vendre Call Strike 65,000$, Prime: 3,200$, IV: 85%
# Acheter Call Strike 70,000$, Prime: 1,700$, IV: 80%

# Calcul:
# Prime nette reçue: 3,200$ - 1,700$ = 1,500$ (pour un contrat complet)
# Pour un mini-contrat (0.01 BTC): 15$
# Risque maximal: (70,000$ - 65,000$ - 1,500$) * 0.01 = 35$
# Profit maximal: 1,500$ * 0.01 = 15$
# Ratio risque/récompense: 35$/15$ = 2.33

# Règle de sortie:
# - Prendre profit à 50% du gain maximal: 7.5$
# - Stop-loss à 50% de la perte maximale: 17.5$
```

### Exemple 2: Exploitation du skew de volatilité avec butterfly

```python
# Exemple de position: Put Butterfly sur ETH
# Lorsque le skew de volatilité est exagéré (volatilité plus élevée pour les puts OTM)

# Prix ETH actuel: 3,500$
# Acheter 1 Put Strike 3,300$, Prime: 180$, IV: 75%
# Vendre 2 Puts Strike 3,100$, Prime: 120$ chacun, IV: 85%
# Acheter 1 Put Strike 2,900$, Prime: 80$, IV: 90%

# Calcul:
# Coût net: 180$ + 80$ - (2 * 120$) = 20$ (pour un contrat complet)
# Pour un mini-contrat (0.1 ETH): 2$
# Risque maximal: 2$ (coût initial)
# Profit maximal: (3,300$ - 3,100$) * 0.1 - 2$ = 18$
# Ratio risque/récompense: 2$/18$ = 0.11 (très favorable)

# Règle de sortie:
# - Prendre profit à 30% du gain maximal: 5.4$
# - Sortie à 7 jours de l'expiration quelle que soit la position
```

## Allocation du capital

Pour un capital de 300$:
- Réserve de sécurité: 150$ (50%)
- Capital de trading actif: 150$ (50%)
- Exposition maximale par position: 15$ (10% du capital actif)
- Nombre de positions simultanées: 3-5

## Implémentation technique

```python
import asyncio
import aiohttp
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import time
import hmac
import hashlib
import base64

# Configuration
API_KEY = "YOUR_API_KEY"  # À remplacer par votre clé API Deribit
API_SECRET = "YOUR_API_SECRET"  # À remplacer par votre secret API Deribit
TEST_MODE = True  # Utiliser le testnet de Deribit

# URLs de l'API
BASE_URL = "https://test.deribit.com" if TEST_MODE else "https://www.deribit.com"
API_URL = BASE_URL + "/api/v2/"

# Paramètres de la stratégie
CAPITAL_TOTAL = 300  # Capital total en USD
CAPITAL_ACTIF = CAPITAL_TOTAL * 0.5  # Capital de trading actif (50%)
MAX_POSITION_SIZE = CAPITAL_ACTIF * 0.1  # Taille maximale par position (10% du capital actif)
MAX_POSITIONS = 5  # Nombre maximal de positions simultanées
IV_HV_HIGH_THRESHOLD = 1.3  # Seuil pour considérer la volatilité implicite comme élevée
IV_HV_LOW_THRESHOLD = 0.7  # Seuil pour considérer la volatilité implicite comme basse
PROFIT_TARGET_PCT = 0.5  # Objectif de profit (50% du profit maximal)
STOP_LOSS_PCT = 0.5  # Stop-loss (50% de la perte maximale)
MIN_DAYS_TO_EXPIRY = 7  # Nombre minimal de jours avant expiration
MAX_DAYS_TO_EXPIRY = 21  # Nombre maximal de jours avant expiration

# Fonction pour générer la signature pour l'authentification
def generate_signature(timestamp, method, uri, params=""):
    message = str(timestamp) + "\n" + method + "\n" + uri + "\n" + params
    signature = hmac.new(
        bytes(API_SECRET, "latin-1"),
        msg=bytes(message, "latin-1"),
        digestmod=hashlib.sha256
    ).hexdigest()
    return signature

# Fonction pour l'authentification
async def authenticate(session):
    timestamp = int(time.time() * 1000)
    method = "public/auth"
    params = {
        "grant_type": "client_credentials",
        "client_id": API_KEY,
        "client_secret": API_SECRET
    }
    
    async with session.post(API_URL + method, json=params) as response:
        result = await response.json()
        return result.get("result", {}).get("access_token")

# Fonction pour obtenir les données historiques du sous-jacent
async def get_historical_data(session, currency, resolution="1D", limit=30):
    method = "public/get_tradingview_chart_data"
    params = {
        "instrument_name": f"{currency}-PERPETUAL",
        "resolution": resolution,
        "limit": limit
    }
    
    async with session.get(API_URL + method, params=params) as response:
        result = await response.json()
        return result.get("result", {})

# Fonction pour calculer la volatilité historique
def calculate_historical_volatility(prices, window=14):
    returns = np.log(prices / prices.shift(1)).dropna()
    hist_vol = returns.rolling(window=window).std() * np.sqrt(365)
    return hist_vol.iloc[-1]

# Fonction pour obtenir les options disponibles
async def get_options(session, currency, kind=None):
    method = "public/get_instruments"
    params = {
        "currency": currency,
        "kind": "option",
        "expired": False
    }
    
    async with session.get(API_URL + method, params=params) as response:
        result = await response.json()
        options = result.get("result", [])
        
        # Filtrer par type d'option si spécifié
        if kind:
            options = [opt for opt in options if opt["option_type"] == kind]
            
        return options

# Fonction pour obtenir le carnet d'ordres d'une option
async def get_order_book(session, instrument_name, depth=5):
    method = "public/get_order_book"
    params = {
        "instrument_name": instrument_name,
        "depth": depth
    }
    
    async with session.get(API_URL + method, params=params) as response:
        result = await response.json()
        return result.get("result", {})

# Fonction pour calculer la volatilité implicite
async def get_option_volatility(session, instrument_name):
    method = "public/get_volatility_index_data"
    params = {
        "instrument_name": instrument_name
    }
    
    async with session.get(API_URL + method, params=params) as response:
        result = await response.json()
        return result.get("result", {}).get("data", [])[-1]

# Fonction pour placer un ordre
async def place_order(session, instrument_name, amount, type, price=None, label=None):
    method = "private/buy" if amount > 0 else "private/sell"
    amount = abs(amount)
    
    params = {
        "instrument_name": instrument_name,
        "amount": amount,
        "type": type
    }
    
    if price:
        params["price"] = price
    
    if label:
        params["label"] = label
    
    async with session.post(API_URL + method, json=params) as response:
        result = await response.json()
        return result.get("result", {})

# Fonction pour annuler un ordre
async def cancel_order(session, order_id):
    method = "private/cancel"
    params = {
        "order_id": order_id
    }
    
    async with session.post(API_URL + method, json=params) as response:
        result = await response.json()
        return result.get("result", {})

# Fonction pour obtenir les positions ouvertes
async def get_positions(session, currency):
    method = "private/get_positions"
    params = {
        "currency": currency
    }
    
    async with session.get(API_URL + method, params=params) as response:
        result = await response.json()
        return result.get("result", [])

# Fonction pour identifier les opportunités d'arbitrage de volatilité
async def find_volatility_arbitrage_opportunities(session, currency):
    # Obtenir les données historiques
    hist_data = await get_historical_data(session, currency)
    prices = pd.Series(hist_data.get("close", []))
    
    # Calculer la volatilité historique sur différentes fenêtres
    hv_7d = calculate_historical_volatility(prices, window=7)
    hv_14d = calculate_historical_volatility(prices, window=14)
    hv_30d = calculate_historical_volatility(prices, window=30)
    
    # Moyenne pondérée des volatilités historiques
    hv_weighted = (hv_7d * 0.5) + (hv_14d * 0.3) + (hv_30d * 0.2)
    
    # Obtenir toutes les options disponibles
    options = await get_options(session, currency)
    
    opportunities = []
    
    for option in options:
        # Vérifier si l'option est dans notre plage d'expiration cible
        expiry = datetime.fromtimestamp(option["expiration_timestamp"] / 1000)
        days_to_expiry = (expiry - datetime.now()).days
        
        if MIN_DAYS_TO_EXPIRY <= days_to_expiry <= MAX_DAYS_TO_EXPIRY:
            # Obtenir la volatilité implicite
            iv = await get_option_volatility(session, option["instrument_name"])
            
            # Calculer le ratio IV/HV
            iv_hv_ratio = iv / hv_weighted
            
            # Vérifier si c'est une opportunité
            if iv_hv_ratio > IV_HV_HIGH_THRESHOLD:
                # Opportunité de vente (IV surévaluée)
                opportunities.append({
                    "type": "sell",
                    "instrument": option["instrument_name"],
                    "iv_hv_ratio": iv_hv_ratio,
                    "days_to_expiry": days_to_expiry,
                    "strike": option["strike"],
                    "option_type": option["option_type"]
                })
            elif iv_hv_ratio < IV_HV_LOW_THRESHOLD:
                # Opportunité d'achat (IV sous-évaluée)
                opportunities.append({
                    "type": "buy",
                    "instrument": option["instrument_name"],
                    "iv_hv_ratio": iv_hv_ratio,
                    "days_to_expiry": days_to_expiry,
                    "strike": option["strike"],
                    "option_type": option["option_type"]
                })
    
    return opportunities

# Fonction pour créer un spread vertical
async def create_vertical_spread(session, currency, spread_type, strike1, strike2, expiry, amount):
    """
    Crée un spread vertical
    spread_type: 'bull_call', 'bear_call', 'bull_put', 'bear_put'
    """
    if spread_type == "bull_call":
        # Acheter call strike bas, vendre call strike haut
        buy_option = f"{currency}-{expiry}-{strike1}-C"
        sell_option = f"{currency}-{expiry}-{strike2}-C"
    elif spread_type == "bear_call":
        # Vendre call strike bas, acheter call strike haut
        sell_option = f"{currency}-{expiry}-{strike1}-C"
        buy_option = f"{currency}-{expiry}-{strike2}-C"
    elif spread_type == "bull_put":
        # Vendre put strike haut, acheter put strike bas
        sell_option = f"{currency}-{expiry}-{strike2}-P"
        buy_option = f"{currency}-{expiry}-{strike1}-P"
    elif spread_type == "bear_put":
        # Acheter put strike haut, vendre put strike bas
        buy_option = f"{currency}-{expiry}-{strike2}-P"
        sell_option = f"{currency}-{expiry}-{strike1}-P"
    else:
        raise ValueError("Type de spread non reconnu")
    
    # Obtenir les prix des options
    buy_book = await get_order_book(session, buy_option)
    sell_book = await get_order_book(session, sell_option)
    
    buy_price = buy_book["asks"][0][0]
    sell_price = sell_book["bids"][0][0]
    
    # Calculer le coût net du spread
    net_cost = (buy_price - sell_price) * amount
    
    # Vérifier si le coût est dans notre budget
    if abs(net_cost) > MAX_POSITION_SIZE:
        print(f"Coût du spread ({net_cost}) supérieur au budget par position ({MAX_POSITION_SIZE})")
        return None
    
    # Placer les ordres
    buy_order = await place_order(session, buy_option, amount, "limit", buy_price, "spread_buy")
    sell_order = await place_order(session, sell_option, -amount, "limit", sell_price, "spread_sell")
    
    return {
        "spread_type": spread_type,
        "buy_option": buy_option,
        "sell_option": sell_option,
        "buy_order": buy_order,
        "sell_order": sell_order,
        "net_cost": net_cost,
        "amount": amount
    }

# Fonction principale pour exécuter la stratégie
async def run_strategy():
    async with aiohttp.ClientSession() as session:
        # Authentification
        token = await authenticate(session)
        if not token:
            print("Échec de l'authentification")
            return
        
        # Ajouter le token aux headers pour les requêtes futures
        session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Boucle principale de la stratégie
        while True:
            try:
                # Vérifier les positions actuelles
                btc_positions = await get_positions(session, "BTC")
                eth_positions = await get_positions(session, "ETH")
                
                total_positions = len(btc_positions) + len(eth_positions)
                
                # Si nous avons moins que le nombre maximal de positions, chercher de nouvelles opportunités
                if total_positions < MAX_POSITIONS:
                    # Chercher des opportunités d'arbitrage de volatilité
                    btc_opportunities = await find_volatility_arbitrage_opportunities(session, "BTC")
                    eth_opportunities = await find_volatility_arbitrage_opportunities(session, "ETH")
                    
                    # Trier les opportunités par ratio IV/HV (décroissant pour les ventes, croissant pour les achats)
                    sell_opportunities = sorted(
                        [op for op in btc_opportunities + eth_opportunities if op["type"] == "sell"],
                        key=lambda x: x["iv_hv_ratio"],
                        reverse=True
                    )
                    
                    buy_opportunities = sorted(
                        [op for op in btc_opportunities + eth_opportunities if op["type"] == "buy"],
                        key=lambda x: x["iv_hv_ratio"]
                    )
                    
                    # Prendre la meilleure opportunité
                    if sell_opportunities:
                        best_sell = sell_opportunities[0]
                        print(f"Meilleure opportunité de vente: {best_sell}")
                        
                        # Créer un spread vertical pour vendre de la volatilité
                        currency = best_sell["instrument"].split("-")[0]
                        expiry = "-".join(best_sell["instrument"].split("-")[1:-1])
                        strike = best_sell["strike"]
                        
                        # Déterminer le strike pour l'autre jambe du spread (5-10% d'écart)
                        strike_diff = strike * 0.05  # 5% d'écart
                        
                        if best_sell["option_type"] == "call":
                            # Bear call spread
                            spread = await create_vertical_spread(
                                session, currency, "bear_call",
                                strike, strike + strike_diff, expiry, 0.01  # 0.01 BTC ou 0.1 ETH
                            )
                        else:
                            # Bear put spread
                            spread = await create_vertical_spread(
                                session, currency, "bear_put",
                                strike - strike_diff, strike, expiry, 0.01
                            )
                        
                        if spread:
                            print(f"Spread créé: {spread}")
                    
                    elif buy_opportunities:
                        best_buy = buy_opportunities[0]
                        print(f"Meilleure opportunité d'achat: {best_buy}")
                        
                        # Créer un spread vertical pour acheter de la volatilité
                        currency = best_buy["instrument"].split("-")[0]
                        expiry = "-".join(best_buy["instrument"].split("-")[1:-1])
                        strike = best_buy["strike"]
                        
                        # Déterminer le strike pour l'autre jambe du spread (5-10% d'écart)
                        strike_diff = strike * 0.05  # 5% d'écart
                        
                        if best_buy["option_type"] == "call":
                            # Bull call spread
                            spread = await create_vertical_spread(
                                session, currency, "bull_call",
                                strike, strike + strike_diff, expiry, 0.01
                            )
                        else:
                            # Bull put spread
                            spread = await create_vertical_spread(
                                session, currency, "bull_put",
                                strike - strike_diff, strike, expiry, 0.01
                            )
                        
                        if spread:
                            print(f"Spread créé: {spread}")
                
                # Vérifier les positions existantes pour les règles de sortie
                for position in btc_positions + eth_positions:
                    # Logique de sortie basée sur le profit/perte
                    # À implémenter selon les règles définies
                    pass
                
                # Attendre avant la prochaine itération
                await asyncio.sleep(3600)  # Vérifier toutes les heures
                
            except Exception as e:
                print(f"Erreur dans la boucle principale: {e}")
                await asyncio.sleep(60)  # Attendre une minute en cas d'erreur

# Point d'entrée principal
if __name__ == "__main__":
    asyncio.run(run_strategy())
```

## Notes d'implémentation

1. **Sécurité et test**:
   - Ce code doit d'abord être exécuté sur le testnet de Deribit
   - Les clés API doivent avoir des permissions limitées (lecture et trading uniquement)
   - Activer la protection "Cancel on disconnect" dans les paramètres API

2. **Personnalisation**:
   - Ajuster les seuils IV/HV selon les conditions de marché
   - Modifier les tailles de position en fonction de votre tolérance au risque
   - Adapter les fenêtres temporelles pour le calcul de la volatilité historique

3. **Améliorations futures**:
   - Ajouter des indicateurs techniques pour confirmer les entrées
   - Implémenter une analyse de sentiment pour ajuster les seuils
   - Développer un dashboard pour visualiser les performances

4. **Limitations**:
   - Les frais de transaction ne sont pas pris en compte dans ce code d'exemple
   - La liquidité peut être limitée sur certaines options
   - Les spreads bid-ask peuvent être larges sur les options moins liquides

## Conclusion

Cette implémentation offre un point de départ solide pour exploiter les inefficiences du marché des options crypto avec un capital limité. Elle met l'accent sur la gestion des risques et l'apprentissage progressif, tout en tirant parti des connaissances théoriques en mathématiques financières.

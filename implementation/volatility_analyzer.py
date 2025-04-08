"""
Module d'analyse de volatilité pour les options crypto.
Ce module contient les fonctions pour calculer et analyser la volatilité historique et implicite.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import logging
from config import (
    HV_WINDOW_SHORT, HV_WINDOW_MEDIUM, HV_WINDOW_LONG, 
    HV_WEIGHTS, IV_HV_HIGH_THRESHOLD, IV_HV_LOW_THRESHOLD,
    MIN_DAYS_TO_EXPIRY, MAX_DAYS_TO_EXPIRY
)

# Configuration du logging
logger = logging.getLogger(__name__)

class VolatilityAnalyzer:
    """Classe pour analyser la volatilité des options crypto."""
    
    def __init__(self, deribit_client):
        """
        Initialise l'analyseur de volatilité.
        
        Args:
            deribit_client: Instance de DeribitClient pour les requêtes API
        """
        self.client = deribit_client
    
    async def get_historical_data(self, currency, resolution="1D", limit=30):
        """
        Récupère les données historiques du sous-jacent.
        
        Args:
            currency (str): Devise (BTC, ETH)
            resolution (str): Résolution temporelle (1D, 4H, etc.)
            limit (int): Nombre de points de données à récupérer
            
        Returns:
            dict: Données historiques
        """
        method = "public/get_tradingview_chart_data"
        params = {
            "instrument_name": f"{currency}-PERPETUAL",
            "resolution": resolution,
            "limit": limit
        }
        
        result = await self.client.get_public(method, params)
        
        if "error" in result:
            logger.error(f"Erreur lors de la récupération des données historiques: {result['error']}")
            return None
        
        return result.get("result", {})
    
    def calculate_historical_volatility(self, prices, window):
        """
        Calcule la volatilité historique.
        
        Args:
            prices (list): Liste des prix
            window (int): Fenêtre de calcul
            
        Returns:
            float: Volatilité historique annualisée
        """
        if len(prices) < window + 1:
            logger.warning(f"Pas assez de données pour calculer la volatilité (besoin de {window+1}, a {len(prices)})")
            return None
        
        # Convertir en Series pandas si ce n'est pas déjà le cas
        if not isinstance(prices, pd.Series):
            prices = pd.Series(prices)
        
        # Calculer les rendements logarithmiques
        returns = np.log(prices / prices.shift(1)).dropna()
        
        # Calculer l'écart-type des rendements et annualiser
        # Multiplier par sqrt(365) pour annualiser (jours de trading crypto)
        hist_vol = returns.rolling(window=window).std() * np.sqrt(365)
        
        return hist_vol.iloc[-1] if not hist_vol.empty else None
    
    async def calculate_weighted_historical_volatility(self, currency):
        """
        Calcule une volatilité historique pondérée sur plusieurs fenêtres temporelles.
        
        Args:
            currency (str): Devise (BTC, ETH)
            
        Returns:
            float: Volatilité historique pondérée
        """
        # Récupérer les données historiques
        hist_data = await self.get_historical_data(currency, limit=max(HV_WINDOW_LONG, 30) + 10)
        
        if not hist_data or "close" not in hist_data:
            logger.error(f"Impossible de récupérer les données historiques pour {currency}")
            return None
        
        prices = hist_data.get("close", [])
        
        # Calculer la volatilité sur différentes fenêtres
        hv_short = self.calculate_historical_volatility(prices, HV_WINDOW_SHORT)
        hv_medium = self.calculate_historical_volatility(prices, HV_WINDOW_MEDIUM)
        hv_long = self.calculate_historical_volatility(prices, HV_WINDOW_LONG)
        
        if None in [hv_short, hv_medium, hv_long]:
            logger.warning("Une ou plusieurs volatilités n'ont pas pu être calculées")
            # Utiliser les volatilités disponibles ou une valeur par défaut
            hv_short = hv_short or 0.8
            hv_medium = hv_medium or 0.7
            hv_long = hv_long or 0.6
        
        # Calculer la moyenne pondérée
        hv_weighted = (hv_short * HV_WEIGHTS[0] + 
                       hv_medium * HV_WEIGHTS[1] + 
                       hv_long * HV_WEIGHTS[2])
        
        logger.info(f"Volatilité historique pondérée pour {currency}: {hv_weighted:.2%}")
        return hv_weighted
    
    async def get_option_volatility(self, instrument_name):
        """
        Récupère la volatilité implicite d'une option.
        
        Args:
            instrument_name (str): Nom de l'instrument (ex: BTC-30JUN23-25000-C)
            
        Returns:
            float: Volatilité implicite
        """
        method = "public/get_order_book"
        params = {
            "instrument_name": instrument_name,
            "depth": 1
        }
        
        result = await self.client.get_public(method, params)
        
        if "error" in result:
            logger.error(f"Erreur lors de la récupération de la volatilité: {result['error']}")
            return None
        
        # La volatilité implicite est fournie dans les métadonnées du carnet d'ordres
        return result.get("result", {}).get("mark_iv")
    
    async def get_available_options(self, currency, kind=None):
        """
        Récupère les options disponibles.
        
        Args:
            currency (str): Devise (BTC, ETH)
            kind (str, optional): Type d'option (call, put)
            
        Returns:
            list: Liste des options disponibles
        """
        method = "public/get_instruments"
        params = {
            "currency": currency,
            "kind": "option",
            "expired": False
        }
        
        result = await self.client.get_public(method, params)
        
        if "error" in result:
            logger.error(f"Erreur lors de la récupération des options: {result['error']}")
            return []
        
        options = result.get("result", [])
        
        # Filtrer par type d'option si spécifié
        if kind:
            options = [opt for opt in options if opt["option_type"].lower() == kind.lower()]
        
        return options
    
    async def find_volatility_arbitrage_opportunities(self, currency):
        """
        Identifie les opportunités d'arbitrage de volatilité.
        
        Args:
            currency (str): Devise (BTC, ETH)
            
        Returns:
            list: Liste des opportunités d'arbitrage
        """
        # Calculer la volatilité historique pondérée
        hv_weighted = await self.calculate_weighted_historical_volatility(currency)
        
        if hv_weighted is None:
            logger.error(f"Impossible de calculer la volatilité historique pour {currency}")
            return []
        
        # Obtenir toutes les options disponibles
        options = await self.get_available_options(currency)
        
        opportunities = []
        
        for option in options:
            # Vérifier si l'option est dans notre plage d'expiration cible
            expiry = datetime.fromtimestamp(option["expiration_timestamp"] / 1000)
            days_to_expiry = (expiry - datetime.now()).days
            
            if MIN_DAYS_TO_EXPIRY <= days_to_expiry <= MAX_DAYS_TO_EXPIRY:
                # Obtenir la volatilité implicite
                iv = await self.get_option_volatility(option["instrument_name"])
                
                if iv is None:
                    continue
                
                # Calculer le ratio IV/HV
                iv_hv_ratio = iv / hv_weighted
                
                # Vérifier si c'est une opportunité
                if iv_hv_ratio > IV_HV_HIGH_THRESHOLD:
                    # Opportunité de vente (IV surévaluée)
                    opportunities.append({
                        "type": "sell",
                        "instrument": option["instrument_name"],
                        "iv": iv,
                        "hv": hv_weighted,
                        "iv_hv_ratio": iv_hv_ratio,
                        "days_to_expiry": days_to_expiry,
                        "strike": option["strike"],
                        "option_type": option["option_type"]
                    })
                    logger.info(f"Opportunité de vente identifiée: {option['instrument_name']} (IV/HV: {iv_hv_ratio:.2f})")
                elif iv_hv_ratio < IV_HV_LOW_THRESHOLD:
                    # Opportunité d'achat (IV sous-évaluée)
                    opportunities.append({
                        "type": "buy",
                        "instrument": option["instrument_name"],
                        "iv": iv,
                        "hv": hv_weighted,
                        "iv_hv_ratio": iv_hv_ratio,
                        "days_to_expiry": days_to_expiry,
                        "strike": option["strike"],
                        "option_type": option["option_type"]
                    })
                    logger.info(f"Opportunité d'achat identifiée: {option['instrument_name']} (IV/HV: {iv_hv_ratio:.2f})")
        
        # Trier les opportunités par ratio IV/HV (décroissant pour les ventes, croissant pour les achats)
        sell_opportunities = sorted(
            [op for op in opportunities if op["type"] == "sell"],
            key=lambda x: x["iv_hv_ratio"],
            reverse=True
        )
        
        buy_opportunities = sorted(
            [op for op in opportunities if op["type"] == "buy"],
            key=lambda x: x["iv_hv_ratio"]
        )
        
        return sell_opportunities + buy_opportunities
    
    async def analyze_volatility_skew(self, currency, expiry_date):
        """
        Analyse le skew de volatilité pour une date d'expiration donnée.
        
        Args:
            currency (str): Devise (BTC, ETH)
            expiry_date (str): Date d'expiration (format: DDMMMYY, ex: 30JUN23)
            
        Returns:
            dict: Analyse du skew de volatilité
        """
        # Obtenir toutes les options pour cette expiration
        all_options = await self.get_available_options(currency)
        expiry_options = [opt for opt in all_options if expiry_date in opt["instrument_name"]]
        
        if not expiry_options:
            logger.warning(f"Aucune option trouvée pour {currency} avec expiration {expiry_date}")
            return None
        
        # Séparer les calls et puts
        calls = [opt for opt in expiry_options if opt["option_type"].lower() == "call"]
        puts = [opt for opt in expiry_options if opt["option_type"].lower() == "put"]
        
        # Obtenir le prix actuel du sous-jacent
        index_price = None
        if calls:
            # Récupérer le prix de l'index à partir des métadonnées d'une option
            method = "public/get_order_book"
            params = {"instrument_name": calls[0]["instrument_name"], "depth": 1}
            result = await self.client.get_public(method, params)
            index_price = result.get("result", {}).get("index_price")
        
        if index_price is None:
            logger.error(f"Impossible de récupérer le prix de l'index pour {currency}")
            return None
        
        # Analyser le skew
        call_skew = []
        put_skew = []
        
        # Analyser le skew des calls
        for call in sorted(calls, key=lambda x: x["strike"]):
            iv = await self.get_option_volatility(call["instrument_name"])
            if iv is not None:
                moneyness = call["strike"] / index_price
                call_skew.append({"strike": call["strike"], "moneyness": moneyness, "iv": iv})
        
        # Analyser le skew des puts
        for put in sorted(puts, key=lambda x: x["strike"]):
            iv = await self.get_option_volatility(put["instrument_name"])
            if iv is not None:
                moneyness = put["strike"] / index_price
                put_skew.append({"strike": put["strike"], "moneyness": moneyness, "iv": iv})
        
        # Calculer les métriques du skew
        skew_metrics = {
            "currency": currency,
            "expiry": expiry_date,
            "index_price": index_price,
            "call_skew": call_skew,
            "put_skew": put_skew
        }
        
        # Identifier les anomalies de skew (si suffisamment de données)
        if len(call_skew) >= 3:
            # Calculer la pente du skew des calls
            atm_calls = [c for c in call_skew if 0.95 <= c["moneyness"] <= 1.05]
            otm_calls = [c for c in call_skew if c["moneyness"] > 1.1]
            
            if atm_calls and otm_calls:
                atm_iv_avg = sum(c["iv"] for c in atm_calls) / len(atm_calls)
                otm_iv_avg = sum(c["iv"] for c in otm_calls) / len(otm_calls)
                call_skew_slope = (otm_iv_avg - atm_iv_avg) / (
                    sum(c["moneyness"] for c in otm_calls) / len(otm_calls) - 
                    sum(c["moneyness"] for c in atm_calls) / len(atm_calls)
                )
                skew_metrics["call_skew_slope"] = call_skew_slope
        
        if len(put_skew) >= 3:
            # Calculer la pente du skew des puts
            atm_puts = [p for p in put_skew if 0.95 <= p["moneyness"] <= 1.05]
            otm_puts = [p for p in put_skew if p["moneyness"] < 0.9]
            
            if atm_puts and otm_puts:
                atm_iv_avg = sum(p["iv"] for p in atm_puts) / len(atm_puts)
                otm_iv_avg = sum(p["iv"] for p in otm_puts) / len(otm_puts)
                put_skew_slope = (otm_iv_avg - atm_iv_avg) / (
                    sum(p["moneyness"] for p in otm_puts) / len(otm_puts) - 
                    sum(p["moneyness"] for p in atm_puts) / len(atm_puts)
                )
                skew_metrics["put_skew_slope"] = put_skew_slope
        
        return skew_metrics

"""
Module de trading pour les options crypto.
Ce module contient les fonctions pour exécuter les stratégies de trading d'options.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from config import (
    MAX_POSITION_SIZE, MAX_POSITIONS, STRIKE_SPREAD_PCT,
    PROFIT_TARGET_PCT, STOP_LOSS_PCT, BTC_CONTRACT_SIZE, ETH_CONTRACT_SIZE
)

# Configuration du logging
logger = logging.getLogger(__name__)

class OptionsTrader:
    """Classe pour exécuter les stratégies de trading d'options crypto."""
    
    def __init__(self, deribit_client, volatility_analyzer):
        """
        Initialise le trader d'options.
        
        Args:
            deribit_client: Instance de DeribitClient pour les requêtes API
            volatility_analyzer: Instance de VolatilityAnalyzer pour l'analyse de volatilité
        """
        self.client = deribit_client
        self.analyzer = volatility_analyzer
    
    async def get_account_summary(self, currency):
        """
        Récupère le résumé du compte.
        
        Args:
            currency (str): Devise (BTC, ETH)
            
        Returns:
            dict: Résumé du compte
        """
        method = "private/get_account_summary"
        params = {
            "currency": currency
        }
        
        result = await self.client.get_private(method, params)
        
        if "error" in result:
            logger.error(f"Erreur lors de la récupération du résumé du compte: {result['error']}")
            return None
        
        return result.get("result", {})
    
    async def get_positions(self, currency):
        """
        Récupère les positions ouvertes.
        
        Args:
            currency (str): Devise (BTC, ETH)
            
        Returns:
            list: Positions ouvertes
        """
        method = "private/get_positions"
        params = {
            "currency": currency
        }
        
        result = await self.client.get_private(method, params)
        
        if "error" in result:
            logger.error(f"Erreur lors de la récupération des positions: {result['error']}")
            return []
        
        return result.get("result", [])
    
    async def get_order_book(self, instrument_name, depth=5):
        """
        Récupère le carnet d'ordres d'un instrument.
        
        Args:
            instrument_name (str): Nom de l'instrument
            depth (int): Profondeur du carnet
            
        Returns:
            dict: Carnet d'ordres
        """
        method = "public/get_order_book"
        params = {
            "instrument_name": instrument_name,
            "depth": depth
        }
        
        result = await self.client.get_public(method, params)
        
        if "error" in result:
            logger.error(f"Erreur lors de la récupération du carnet d'ordres: {result['error']}")
            return None
        
        return result.get("result", {})
    
    async def place_order(self, instrument_name, amount, type, price=None, label=None):
        """
        Place un ordre.
        
        Args:
            instrument_name (str): Nom de l'instrument
            amount (float): Quantité (positive pour achat, négative pour vente)
            type (str): Type d'ordre ('limit', 'market')
            price (float, optional): Prix pour les ordres limites
            label (str, optional): Étiquette pour l'ordre
            
        Returns:
            dict: Résultat de l'ordre
        """
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
        
        result = await self.client.post_private(method, params)
        
        if "error" in result:
            logger.error(f"Erreur lors du placement de l'ordre: {result['error']}")
            return None
        
        order_result = result.get("result", {})
        logger.info(f"Ordre placé: {order_result}")
        return order_result
    
    async def cancel_order(self, order_id):
        """
        Annule un ordre.
        
        Args:
            order_id (str): ID de l'ordre
            
        Returns:
            dict: Résultat de l'annulation
        """
        method = "private/cancel"
        params = {
            "order_id": order_id
        }
        
        result = await self.client.post_private(method, params)
        
        if "error" in result:
            logger.error(f"Erreur lors de l'annulation de l'ordre: {result['error']}")
            return None
        
        return result.get("result", {})
    
    async def create_vertical_spread(self, currency, spread_type, strike1, strike2, expiry, amount):
        """
        Crée un spread vertical.
        
        Args:
            currency (str): Devise (BTC, ETH)
            spread_type (str): Type de spread ('bull_call', 'bear_call', 'bull_put', 'bear_put')
            strike1 (float): Premier strike
            strike2 (float): Deuxième strike
            expiry (str): Date d'expiration (format: DDMMMYY, ex: 30JUN23)
            amount (float): Quantité
            
        Returns:
            dict: Résultat du spread
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
            logger.error(f"Type de spread non reconnu: {spread_type}")
            return None
        
        # Obtenir les prix des options
        buy_book = await self.get_order_book(buy_option)
        sell_book = await self.get_order_book(sell_option)
        
        if not buy_book or not sell_book:
            logger.error(f"Impossible d'obtenir les carnets d'ordres pour {buy_option} ou {sell_option}")
            return None
        
        # Vérifier s'il y a des ordres dans le carnet
        if not buy_book.get("asks") or not sell_book.get("bids"):
            logger.error(f"Carnets d'ordres insuffisants pour {buy_option} ou {sell_option}")
            return None
        
        buy_price = buy_book["asks"][0][0]
        sell_price = sell_book["bids"][0][0]
        
        # Calculer le coût net du spread
        net_cost = (buy_price - sell_price) * amount
        
        # Vérifier si le coût est dans notre budget
        if abs(net_cost) > MAX_POSITION_SIZE:
            logger.warning(f"Coût du spread ({net_cost}) supérieur au budget par position ({MAX_POSITION_SIZE})")
            return None
        
        # Placer les ordres
        buy_order = await self.place_order(buy_option, amount, "limit", buy_price, f"spread_{spread_type}_buy")
        if not buy_order:
            logger.error(f"Échec de l'ordre d'achat pour {buy_option}")
            return None
        
        sell_order = await self.place_order(sell_option, -amount, "limit", sell_price, f"spread_{spread_type}_sell")
        if not sell_order:
            # Annuler l'ordre d'achat si l'ordre de vente échoue
            logger.error(f"Échec de l'ordre de vente pour {sell_option}, annulation de l'ordre d'achat")
            await self.cancel_order(buy_order.get("order_id"))
            return None
        
        spread_result = {
            "spread_type": spread_type,
            "buy_option": buy_option,
            "sell_option": sell_option,
            "buy_order": buy_order,
            "sell_order": sell_order,
            "net_cost": net_cost,
            "amount": amount,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Spread vertical créé: {spread_result}")
        return spread_result
    
    async def execute_volatility_arbitrage_strategy(self, currency):
        """
        Exécute la stratégie d'arbitrage de volatilité.
        
        Args:
            currency (str): Devise (BTC, ETH)
            
        Returns:
            dict: Résultat de l'exécution
        """
        # Vérifier les positions actuelles
        positions = await self.get_positions(currency)
        option_positions = [p for p in positions if p.get("instrument_name", "").endswith("-C") or 
                           p.get("instrument_name", "").endswith("-P")]
        
        if len(option_positions) >= MAX_POSITIONS:
            logger.info(f"Nombre maximum de positions atteint ({MAX_POSITIONS})")
            return {"status": "max_positions_reached", "positions": len(option_positions)}
        
        # Trouver des opportunités d'arbitrage de volatilité
        opportunities = await self.analyzer.find_volatility_arbitrage_opportunities(currency)
        
        if not opportunities:
            logger.info(f"Aucune opportunité d'arbitrage de volatilité trouvée pour {currency}")
            return {"status": "no_opportunities"}
        
        # Sélectionner la meilleure opportunité
        best_opportunity = opportunities[0]
        logger.info(f"Meilleure opportunité: {best_opportunity}")
        
        # Déterminer la taille du contrat
        contract_size = BTC_CONTRACT_SIZE if currency == "BTC" else ETH_CONTRACT_SIZE
        
        # Extraire les informations de l'opportunité
        instrument = best_opportunity["instrument"]
        parts = instrument.split("-")
        currency = parts[0]
        expiry = parts[1]
        strike = float(parts[2])
        option_type = parts[3]
        
        # Déterminer le strike pour l'autre jambe du spread (5-10% d'écart)
        strike_diff = strike * STRIKE_SPREAD_PCT
        
        # Créer un spread vertical en fonction du type d'opportunité
        if best_opportunity["type"] == "sell":
            if option_type == "C":
                # Bear call spread
                spread_result = await self.create_vertical_spread(
                    currency, "bear_call", strike, strike + strike_diff, expiry, contract_size
                )
            else:
                # Bear put spread
                spread_result = await self.create_vertical_spread(
                    currency, "bear_put", strike - strike_diff, strike, expiry, contract_size
                )
        else:  # buy
            if option_type == "C":
                # Bull call spread
                spread_result = await self.create_vertical_spread(
                    currency, "bull_call", strike, strike + strike_diff, expiry, contract_size
                )
            else:
                # Bull put spread
                spread_result = await self.create_vertical_spread(
                    currency, "bull_put", strike - strike_diff, strike, expiry, contract_size
                )
        
        if spread_result:
            return {
                "status": "success",
                "opportunity": best_opportunity,
                "spread": spread_result
            }
        else:
            return {
                "status": "failed",
                "opportunity": best_opportunity,
                "reason": "Échec de la création du spread"
            }
    
    async def manage_positions(self, currency):
        """
        Gère les positions existantes selon les règles de sortie.
        
        Args:
            currency (str): Devise (BTC, ETH)
            
        Returns:
            list: Actions effectuées
        """
        positions = await self.get_positions(currency)
        option_positions = [p for p in positions if p.get("instrument_name", "").endswith("-C") or 
                           p.get("instrument_name", "").endswith("-P")]
        
        actions = []
        
        for position in option_positions:
            instrument = position.get("instrument_name")
            entry_price = position.get("average_price")
            current_price = position.get("mark_price")
            size = position.get("size")
            direction = position.get("direction")
            
            if not all([instrument, entry_price, current_price, size, direction]):
                logger.warning(f"Données de position incomplètes: {position}")
                continue
            
            # Calculer le P&L
            pnl_pct = (current_price - entry_price) / entry_price if direction == "buy" else (entry_price - current_price) / entry_price
            
            # Vérifier les règles de sortie
            action = None
            
            # 1. Règle de prise de profit
            if pnl_pct >= PROFIT_TARGET_PCT:
                action = "take_profit"
            
            # 2. Règle de stop-loss
            elif pnl_pct <= -STOP_LOSS_PCT:
                action = "stop_loss"
            
            # 3. Règle de proximité d'expiration
            expiry_parts = instrument.split("-")
            if len(expiry_parts) >= 2:
                expiry_str = expiry_parts[1]
                try:
                    # Convertir la date d'expiration (format: DDMMMYY)
                    expiry_date = datetime.strptime(expiry_str, "%d%b%y")
                    days_to_expiry = (expiry_date - datetime.now()).days
                    
                    if days_to_expiry <= 2:
                        action = "close_to_expiry"
                except ValueError:
                    logger.error(f"Format de date d'expiration non reconnu: {expiry_str}")
            
            # Exécuter l'action si nécessaire
            if action:
                close_order = await self.place_order(
                    instrument,
                    -size if direction == "buy" else size,
                    "market",
                    label=f"close_{action}"
                )
                
                if close_order:
                    actions.append({
                        "instrument": instrument,
                        "action": action,
                        "pnl_pct": pnl_pct,
                        "order": close_order
                    })
                    logger.info(f"Position fermée ({action}): {instrument}, P&L: {pnl_pct:.2%}")
        
        return actions

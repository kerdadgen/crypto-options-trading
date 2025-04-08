"""
Script principal pour la stratégie de trading d'options crypto.
Ce script intègre tous les composants et exécute la stratégie de trading.
"""

import asyncio
import logging
import os
import json
from datetime import datetime, timedelta
import time

# Importer les modules de l'application
from deribit_client import DeribitClient
from volatility_analyzer import VolatilityAnalyzer
from options_trader import OptionsTrader
from config import (
    LOG_LEVEL, LOG_FILE, CHECK_INTERVAL, POSITION_CHECK_INTERVAL,
    CAPITAL_TOTAL, CAPITAL_ACTIF, RESERVE_SECURITE
)

# Configuration du logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Créer le répertoire de données s'il n'existe pas
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

class TradingSystem:
    """Système principal de trading d'options crypto."""
    
    def __init__(self):
        """Initialise le système de trading."""
        self.client = DeribitClient()
        self.analyzer = None
        self.trader = None
        self.running = False
        self.last_position_check = 0
        self.trades_history = []
        
    async def initialize(self):
        """Initialise les composants du système."""
        logger.info("Initialisation du système de trading...")
        
        # Créer une session et s'authentifier
        await self.client.create_session()
        auth_result = await self.client.authenticate()
        
        if not auth_result:
            logger.error("Échec de l'authentification. Arrêt du système.")
            return False
        
        # Initialiser l'analyseur de volatilité et le trader
        self.analyzer = VolatilityAnalyzer(self.client)
        self.trader = OptionsTrader(self.client, self.analyzer)
        
        logger.info("Système initialisé avec succès.")
        return True
    
    async def check_account_status(self):
        """Vérifie l'état du compte et affiche un résumé."""
        btc_summary = await self.trader.get_account_summary("BTC")
        eth_summary = await self.trader.get_account_summary("ETH")
        
        if btc_summary and eth_summary:
            logger.info("=== État du compte ===")
            logger.info(f"BTC: {btc_summary.get('equity')} BTC (${btc_summary.get('equity_usd', 0):.2f})")
            logger.info(f"ETH: {eth_summary.get('equity')} ETH (${eth_summary.get('equity_usd', 0):.2f})")
            logger.info(f"Total USD: ${btc_summary.get('equity_usd', 0) + eth_summary.get('equity_usd', 0):.2f}")
            
            # Vérifier si le capital est conforme aux attentes
            total_usd = btc_summary.get('equity_usd', 0) + eth_summary.get('equity_usd', 0)
            if total_usd < CAPITAL_TOTAL * 0.9:
                logger.warning(f"Capital total (${total_usd:.2f}) inférieur à 90% du capital initial (${CAPITAL_TOTAL:.2f})")
            elif total_usd > CAPITAL_TOTAL * 1.1:
                logger.info(f"Capital total (${total_usd:.2f}) supérieur à 110% du capital initial (${CAPITAL_TOTAL:.2f})")
            
            return {
                "btc": btc_summary,
                "eth": eth_summary,
                "total_usd": btc_summary.get('equity_usd', 0) + eth_summary.get('equity_usd', 0)
            }
        else:
            logger.error("Impossible d'obtenir l'état du compte")
            return None
    
    async def check_open_positions(self):
        """Vérifie les positions ouvertes et affiche un résumé."""
        btc_positions = await self.trader.get_positions("BTC")
        eth_positions = await self.trader.get_positions("ETH")
        
        option_positions = []
        for pos in btc_positions + eth_positions:
            if pos.get("instrument_name", "").endswith("-C") or pos.get("instrument_name", "").endswith("-P"):
                option_positions.append(pos)
        
        if option_positions:
            logger.info("=== Positions ouvertes ===")
            for pos in option_positions:
                instrument = pos.get("instrument_name")
                size = pos.get("size")
                direction = pos.get("direction")
                entry_price = pos.get("average_price")
                current_price = pos.get("mark_price")
                pnl = pos.get("floating_profit_loss")
                pnl_usd = pos.get("floating_profit_loss_usd")
                
                logger.info(f"{instrument}: {direction} {size} @ {entry_price} (P&L: {pnl} / ${pnl_usd:.2f})")
        else:
            logger.info("Aucune position d'options ouverte")
        
        return option_positions
    
    async def save_trade_history(self, trade):
        """Sauvegarde l'historique des trades."""
        self.trades_history.append(trade)
        
        # Sauvegarder dans un fichier JSON
        history_file = os.path.join(DATA_DIR, 'trade_history.json')
        try:
            with open(history_file, 'w') as f:
                json.dump(self.trades_history, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de l'historique des trades: {e}")
    
    async def execute_strategy_cycle(self):
        """Exécute un cycle complet de la stratégie."""
        logger.info("=== Début du cycle de stratégie ===")
        
        # Vérifier l'état du compte
        account_status = await self.check_account_status()
        if not account_status:
            logger.error("Impossible de continuer sans état du compte")
            return
        
        # Vérifier les positions ouvertes
        open_positions = await self.check_open_positions()
        
        # Gérer les positions existantes si nécessaire
        current_time = time.time()
        if current_time - self.last_position_check >= POSITION_CHECK_INTERVAL:
            logger.info("Vérification et gestion des positions existantes...")
            btc_actions = await self.trader.manage_positions("BTC")
            eth_actions = await self.trader.manage_positions("ETH")
            
            for action in btc_actions + eth_actions:
                logger.info(f"Action effectuée: {action}")
                await self.save_trade_history({
                    "type": "close",
                    "timestamp": datetime.now().isoformat(),
                    "action": action
                })
            
            self.last_position_check = current_time
        
        # Exécuter la stratégie d'arbitrage de volatilité pour BTC
        logger.info("Recherche d'opportunités d'arbitrage de volatilité pour BTC...")
        btc_result = await self.trader.execute_volatility_arbitrage_strategy("BTC")
        
        if btc_result.get("status") == "success":
            logger.info(f"Stratégie BTC exécutée avec succès: {btc_result}")
            await self.save_trade_history({
                "type": "open",
                "timestamp": datetime.now().isoformat(),
                "currency": "BTC",
                "result": btc_result
            })
        else:
            logger.info(f"Pas d'action pour BTC: {btc_result.get('status')}")
        
        # Exécuter la stratégie d'arbitrage de volatilité pour ETH
        logger.info("Recherche d'opportunités d'arbitrage de volatilité pour ETH...")
        eth_result = await self.trader.execute_volatility_arbitrage_strategy("ETH")
        
        if eth_result.get("status") == "success":
            logger.info(f"Stratégie ETH exécutée avec succès: {eth_result}")
            await self.save_trade_history({
                "type": "open",
                "timestamp": datetime.now().isoformat(),
                "currency": "ETH",
                "result": eth_result
            })
        else:
            logger.info(f"Pas d'action pour ETH: {eth_result.get('status')}")
        
        logger.info("=== Fin du cycle de stratégie ===")
    
    async def run(self):
        """Exécute la boucle principale du système de trading."""
        if not await self.initialize():
            return
        
        self.running = True
        logger.info("Démarrage du système de trading...")
        
        try:
            while self.running:
                try:
                    await self.execute_strategy_cycle()
                except Exception as e:
                    logger.error(f"Erreur pendant le cycle de stratégie: {e}", exc_info=True)
                
                logger.info(f"Attente de {CHECK_INTERVAL} secondes avant le prochain cycle...")
                await asyncio.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            logger.info("Interruption utilisateur détectée. Arrêt du système...")
        except Exception as e:
            logger.error(f"Erreur inattendue: {e}", exc_info=True)
        finally:
            self.running = False
            await self.client.close_session()
            logger.info("Système de trading arrêté.")
    
    def stop(self):
        """Arrête le système de trading."""
        self.running = False
        logger.info("Demande d'arrêt du système de trading...")

async def main():
    """Fonction principale."""
    logger.info("=== Démarrage du système de trading d'options crypto ===")
    logger.info(f"Capital total: ${CAPITAL_TOTAL}")
    logger.info(f"Capital actif: ${CAPITAL_ACTIF}")
    logger.info(f"Réserve de sécurité: ${RESERVE_SECURITE}")
    
    system = TradingSystem()
    await system.run()

if __name__ == "__main__":
    asyncio.run(main())

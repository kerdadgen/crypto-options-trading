"""
Script de test pour la stratégie de trading d'options crypto en mode paper trading.
Ce script permet de tester la stratégie sans risquer de capital réel.
"""

import asyncio
import logging
import os
import json
from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import sys

# Ajouter le répertoire parent au chemin pour importer les modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importer les modules de l'application
from implementation.deribit_client import DeribitClient
from implementation.volatility_analyzer import VolatilityAnalyzer
from implementation.options_trader import OptionsTrader
from implementation.config import (
    LOG_LEVEL, CHECK_INTERVAL, POSITION_CHECK_INTERVAL,
    CAPITAL_TOTAL, CAPITAL_ACTIF, RESERVE_SECURITE,
    IV_HV_HIGH_THRESHOLD, IV_HV_LOW_THRESHOLD,
    PROFIT_TARGET_PCT, STOP_LOSS_PCT
)

# Configuration du logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('paper_trading_test.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Créer le répertoire de données s'il n'existe pas
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

class PaperTradingTest:
    """Classe pour tester la stratégie en mode paper trading."""
    
    def __init__(self, test_duration_hours=24, initial_capital=CAPITAL_TOTAL):
        """
        Initialise le test de paper trading.
        
        Args:
            test_duration_hours (int): Durée du test en heures
            initial_capital (float): Capital initial pour le test
        """
        self.client = DeribitClient()
        self.analyzer = None
        self.trader = None
        self.test_duration = test_duration_hours * 3600  # Convertir en secondes
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.paper_positions = []
        self.trade_history = []
        self.performance_metrics = {
            'capital_history': [],
            'trades': [],
            'win_rate': 0,
            'profit_factor': 0,
            'max_drawdown': 0,
            'sharpe_ratio': 0
        }
        self.start_time = None
    
    async def initialize(self):
        """Initialise les composants du système."""
        logger.info("Initialisation du test de paper trading...")
        
        # Créer une session et s'authentifier
        await self.client.create_session()
        auth_result = await self.client.authenticate()
        
        if not auth_result:
            logger.error("Échec de l'authentification. Arrêt du test.")
            return False
        
        # Initialiser l'analyseur de volatilité et le trader
        self.analyzer = VolatilityAnalyzer(self.client)
        self.trader = OptionsTrader(self.client, self.analyzer)
        
        logger.info("Test initialisé avec succès.")
        self.start_time = datetime.now()
        
        # Enregistrer le capital initial
        self.performance_metrics['capital_history'].append({
            'timestamp': self.start_time.isoformat(),
            'capital': self.initial_capital
        })
        
        return True
    
    async def simulate_trade(self, trade_type, instrument, amount, price, direction):
        """
        Simule un trade en paper trading.
        
        Args:
            trade_type (str): Type de trade ('open', 'close')
            instrument (str): Nom de l'instrument
            amount (float): Quantité
            price (float): Prix
            direction (str): Direction ('buy', 'sell')
            
        Returns:
            dict: Résultat du trade simulé
        """
        # Calculer la valeur du trade
        value = amount * price
        
        # Créer un ID de position unique
        position_id = f"paper_{len(self.trade_history) + 1}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Créer l'objet trade
        trade = {
            'id': position_id,
            'type': trade_type,
            'instrument': instrument,
            'amount': amount,
            'price': price,
            'direction': direction,
            'value': value,
            'timestamp': datetime.now().isoformat()
        }
        
        # Mettre à jour le capital et les positions
        if trade_type == 'open':
            # Ajouter aux positions ouvertes
            self.paper_positions.append({
                'id': position_id,
                'instrument': instrument,
                'amount': amount,
                'entry_price': price,
                'direction': direction,
                'open_timestamp': datetime.now().isoformat(),
                'value': value
            })
            
            # Soustraire la valeur du capital (pour les achats)
            if direction == 'buy':
                self.current_capital -= value
            # Ajouter la valeur au capital (pour les ventes)
            else:
                self.current_capital += value
        
        elif trade_type == 'close':
            # Trouver la position correspondante
            position = None
            for i, pos in enumerate(self.paper_positions):
                if pos['instrument'] == instrument and pos['direction'] != direction:
                    position = pos
                    del self.paper_positions[i]
                    break
            
            if position:
                # Calculer le P&L
                if position['direction'] == 'buy':
                    pnl = (price - position['entry_price']) * position['amount']
                else:
                    pnl = (position['entry_price'] - price) * position['amount']
                
                # Mettre à jour le capital
                self.current_capital += position['value'] + pnl
                
                # Ajouter le P&L au trade
                trade['pnl'] = pnl
                trade['pnl_pct'] = pnl / position['value']
                trade['position_id'] = position['id']
                
                logger.info(f"Position fermée: {instrument}, P&L: ${pnl:.2f} ({trade['pnl_pct']:.2%})")
            else:
                logger.warning(f"Aucune position correspondante trouvée pour {instrument}")
        
        # Enregistrer le trade dans l'historique
        self.trade_history.append(trade)
        
        # Enregistrer le capital actuel
        self.performance_metrics['capital_history'].append({
            'timestamp': datetime.now().isoformat(),
            'capital': self.current_capital
        })
        
        return trade
    
    async def simulate_volatility_arbitrage(self, currency):
        """
        Simule la stratégie d'arbitrage de volatilité en paper trading.
        
        Args:
            currency (str): Devise (BTC, ETH)
            
        Returns:
            dict: Résultat de la simulation
        """
        # Trouver des opportunités d'arbitrage de volatilité
        opportunities = await self.analyzer.find_volatility_arbitrage_opportunities(currency)
        
        if not opportunities:
            logger.info(f"Aucune opportunité d'arbitrage de volatilité trouvée pour {currency}")
            return {"status": "no_opportunities"}
        
        # Sélectionner la meilleure opportunité
        best_opportunity = opportunities[0]
        logger.info(f"Meilleure opportunité: {best_opportunity}")
        
        # Extraire les informations de l'opportunité
        instrument = best_opportunity["instrument"]
        
        # Obtenir le prix actuel de l'option
        order_book = await self.trader.get_order_book(instrument)
        if not order_book or not order_book.get("asks") or not order_book.get("bids"):
            logger.error(f"Impossible d'obtenir le carnet d'ordres pour {instrument}")
            return {"status": "failed", "reason": "Carnet d'ordres non disponible"}
        
        # Déterminer le prix et la direction
        if best_opportunity["type"] == "sell":
            price = order_book["bids"][0][0]
            direction = "sell"
        else:
            price = order_book["asks"][0][0]
            direction = "buy"
        
        # Déterminer la taille du contrat (simulée)
        amount = 0.01 if currency == "BTC" else 0.1
        
        # Simuler l'ouverture de la position
        trade = await self.simulate_trade("open", instrument, amount, price, direction)
        
        return {
            "status": "success",
            "opportunity": best_opportunity,
            "trade": trade
        }
    
    async def manage_paper_positions(self):
        """
        Gère les positions paper trading selon les règles de sortie.
        
        Returns:
            list: Actions effectuées
        """
        actions = []
        
        for position in list(self.paper_positions):  # Utiliser une copie pour éviter les problèmes de modification pendant l'itération
            instrument = position['instrument']
            entry_price = position['entry_price']
            direction = position['direction']
            amount = position['amount']
            
            # Obtenir le prix actuel
            order_book = await self.trader.get_order_book(instrument)
            if not order_book:
                logger.warning(f"Impossible d'obtenir le carnet d'ordres pour {instrument}")
                continue
            
            # Déterminer le prix actuel
            if direction == "buy":
                current_price = order_book["bids"][0][0] if order_book.get("bids") else None
            else:
                current_price = order_book["asks"][0][0] if order_book.get("asks") else None
            
            if not current_price:
                logger.warning(f"Prix actuel non disponible pour {instrument}")
                continue
            
            # Calculer le P&L
            if direction == "buy":
                pnl_pct = (current_price - entry_price) / entry_price
            else:
                pnl_pct = (entry_price - current_price) / entry_price
            
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
                # Simuler la fermeture de la position
                close_direction = "buy" if direction == "sell" else "sell"
                close_trade = await self.simulate_trade("close", instrument, amount, current_price, close_direction)
                
                actions.append({
                    "instrument": instrument,
                    "action": action,
                    "pnl_pct": pnl_pct,
                    "trade": close_trade
                })
                
                logger.info(f"Position fermée ({action}): {instrument}, P&L: {pnl_pct:.2%}")
        
        return actions
    
    async def calculate_performance_metrics(self):
        """
        Calcule les métriques de performance de la stratégie.
        
        Returns:
            dict: Métriques de performance
        """
        # Extraire les trades fermés
        closed_trades = [t for t in self.trade_history if t.get('type') == 'close' and 'pnl' in t]
        
        if not closed_trades:
            logger.warning("Aucun trade fermé pour calculer les métriques de performance")
            return self.performance_metrics
        
        # Calculer le taux de réussite
        winning_trades = [t for t in closed_trades if t['pnl'] > 0]
        losing_trades = [t for t in closed_trades if t['pnl'] <= 0]
        
        win_rate = len(winning_trades) / len(closed_trades) if closed_trades else 0
        
        # Calculer le profit factor
        gross_profit = sum(t['pnl'] for t in winning_trades)
        gross_loss = abs(sum(t['pnl'] for t in losing_trades))
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Calculer le drawdown maximal
        capital_history = pd.DataFrame(self.performance_metrics['capital_history'])
        if not capital_history.empty and 'capital' in capital_history:
            capital_history['timestamp'] = pd.to_datetime(capital_history['timestamp'])
            capital_history = capital_history.sort_values('timestamp')
            
            # Calculer le drawdown
            capital_history['peak'] = capital_history['capital'].cummax()
            capital_history['drawdown'] = (capital_history['capital'] - capital_history['peak']) / capital_history['peak']
            
            max_drawdown = abs(capital_history['drawdown'].min())
        else:
            max_drawdown = 0
        
        # Calculer le ratio de Sharpe
        if len(capital_history) > 1:
            capital_history['returns'] = capital_history['capital'].pct_change()
            avg_return = capital_history['returns'].mean()
            std_return = capital_history['returns'].std()
            
            sharpe_ratio = avg_return / std_return * np.sqrt(365) if std_return > 0 else 0
        else:
            sharpe_ratio = 0
        
        # Mettre à jour les métriques
        self.performance_metrics.update({
            'trades': closed_trades,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'total_trades': len(closed_trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'final_capital': self.current_capital,
            'total_return': (self.current_capital - self.initial_capital) / self.initial_capital,
            'test_duration': str(datetime.now() - self.start_time)
        })
        
        return self.performance_metrics
    
    async def generate_performance_report(self):
        """
        Génère un rapport de performance complet.
        
        Returns:
            str: Chemin du rapport généré
        """
        # Calculer les métriques finales
        await self.calculate_performance_metrics()
        
        # Créer un DataFrame pour l'évolution du capital
        capital_df = pd.DataFrame(self.performance_metrics['capital_history'])
        capital_df['timestamp'] = pd.to_datetime(capital_df['timestamp'])
        capital_df = capital_df.sort_values('timestamp')
        
        # Créer un DataFrame pour les trades
        trades_df = pd.DataFrame(self.trade_history)
        if not trades_df.empty and 'timestamp' in trades_df:
            trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp'])
            trades_df = trades_df.sort_values('timestamp')
        
        # Générer des graphiques
        plt.figure(figsize=(12, 8))
        
        # Graphique de l'évolution du capital
        plt.subplot(2, 1, 1)
        plt.plot(capital_df['timestamp'], capital_df['capital'])
        plt.title('Évolution du capital')
        plt.xlabel('Date')
        plt.ylabel('Capital ($)')
        plt.grid(True)
        
        # Graphique des P&L des trades
        if 'pnl' in trades_df.columns:
            plt.subplot(2, 1, 2)
            trades_df_with_pnl = trades_df[trades_df['type'] == 'close'].copy()
            if not trades_df_with_pnl.empty:
                plt.bar(range(len(trades_df_with_pnl)), trades_df_with_pnl['pnl'])
                plt.title('P&L par trade')
                plt.xlabel('Numéro de trade')
                plt.ylabel('P&L ($)')
                plt.grid(True)
        
        # Sauvegarder le graphique
        plot_path = os.path.join(DATA_DIR, 'performance_plot.png')
        plt.tight_layout()
        plt.savefig(plot_path)
        
        # Générer un rapport HTML
        report_path = os.path.join(DATA_DIR, 'performance_report.html')
        
        with open(report_path, 'w') as f:
            f.write(f"""
            <html>
            <head>
                <title>Rapport de Performance - Stratégie d'Options Crypto</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    h1, h2 {{ color: #333366; }}
                    table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
                    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                    th {{ background-color: #f2f2f2; }}
                    tr:nth-child(even) {{ background-color: #f9f9f9; }}
                    .positive {{ color: green; }}
                    .negative {{ color: red; }}
                    .metrics {{ display: flex; flex-wrap: wrap; }}
                    .metric-box {{ border: 1px solid #ddd; padding: 15px; margin: 10px; flex: 1; min-width: 200px; }}
                </style>
            </head>
            <body>
                <h1>Rapport de Performance - Stratégie d'Options Crypto</h1>
                <p>Période de test: {self.start_time} à {datetime.now()}</p>
                <p>Durée: {self.performance_metrics['test_duration']}</p>
                
                <h2>Résumé</h2>
                <div class="metrics">
                    <div class="metric-box">
                        <h3>Capital</h3>
                        <p>Initial: ${self.initial_capital:.2f}</p>
                        <p>Final: ${self.performance_metrics['final_capital']:.2f}</p>
                        <p>Rendement total: <span class="{'positive' if self.performance_metrics['total_return'] >= 0 else 'negative'}">{self.performance_metrics['total_return']:.2%}</span></p>
                    </div>
                    <div class="metric-box">
                        <h3>Trades</h3>
                        <p>Total: {self.performance_metrics['total_trades']}</p>
                        <p>Gagnants: {self.performance_metrics['winning_trades']} ({self.performance_metrics['win_rate']:.2%})</p>
                        <p>Perdants: {self.performance_metrics['losing_trades']} ({1 - self.performance_metrics['win_rate']:.2%})</p>
                    </div>
                    <div class="metric-box">
                        <h3>Métriques de risque</h3>
                        <p>Profit Factor: {self.performance_metrics['profit_factor']:.2f}</p>
                        <p>Drawdown maximal: {self.performance_metrics['max_drawdown']:.2%}</p>
                        <p>Ratio de Sharpe: {self.performance_metrics['sharpe_ratio']:.2f}</p>
                    </div>
                </div>
                
                <h2>Évolution du capital</h2>
                <img src="performance_plot.png" alt="Graphique de performance" style="width: 100%;">
                
                <h2>Détail des trades</h2>
                <table>
                    <tr>
                        <th>Date</th>
                        <th>Type</th>
                        <th>Instrument</th>
                        <th>Direction</th>
                        <th>Quantité</th>
                        <th>Prix</th>
                        <th>Valeur</th>
                        <th>P&L</th>
                        <th>P&L %</th>
                    </tr>
            """)
            
            # Ajouter les détails des trades
            for trade in sorted(self.trade_history, key=lambda x: x.get('timestamp', '')):
                pnl = trade.get('pnl', '')
                pnl_pct = trade.get('pnl_pct', '')
                
                pnl_class = ''
                if pnl:
                    pnl_class = 'positive' if pnl > 0 else 'negative'
                
                f.write(f"""
                    <tr>
                        <td>{trade.get('timestamp', '').split('T')[0]}</td>
                        <td>{trade.get('type', '')}</td>
                        <td>{trade.get('instrument', '')}</td>
                        <td>{trade.get('direction', '')}</td>
                        <td>{trade.get('amount', '')}</td>
                        <td>${trade.get('price', ''):.2f}</td>
                        <td>${trade.get('value', ''):.2f}</td>
                        <td class="{pnl_class}">${pnl:.2f if pnl else ''}</td>
                        <td class="{pnl_class}">{pnl_pct:.2%if pnl_pct else ''}</td>
                    </tr>
                """)
            
            f.write("""
                </table>
            </body>
            </html>
            """)
        
        logger.info(f"Rapport de performance généré: {report_path}")
        return report_path
    
    async def run(self):
        """Exécute le test de paper trading."""
        if not await self.initialize():
            return
        
        logger.info(f"Démarrage du test de paper trading pour {self.test_duration / 3600} heures...")
        logger.info(f"Capital initial: ${self.initial_capital}")
        
        start_time = datetime.now()
        end_time = start_time + timedelta(seconds=self.test_duration)
        
        try:
            while datetime.now() < end_time:
                try:
                    # Simuler la stratégie d'arbitrage de volatilité pour BTC
                    logger.info("Recherche d'opportunités d'arbitrage de volatilité pour BTC...")
                    btc_result = await self.simulate_volatility_arbitrage("BTC")
                    
                    if btc_result.get("status") == "success":
                        logger.info(f"Stratégie BTC exécutée avec succès: {btc_result}")
                    else:
                        logger.info(f"Pas d'action pour BTC: {btc_result.get('status')}")
                    
                    # Simuler la stratégie d'arbitrage de volatilité pour ETH
                    logger.info("Recherche d'opportunités d'arbitrage de volatilité pour ETH...")
                    eth_result = await self.simulate_volatility_arbitrage("ETH")
                    
                    if eth_result.get("status") == "success":
                        logger.info(f"Stratégie ETH exécutée avec succès: {eth_result}")
                    else:
                        logger.info(f"Pas d'action pour ETH: {eth_result.get('status')}")
                    
                    # Gérer les positions existantes
                    logger.info("Gestion des positions existantes...")
                    actions = await self.manage_paper_positions()
                    
                    for action in actions:
                        logger.info(f"Action effectuée: {action}")
                    
                    # Afficher l'état actuel
                    logger.info(f"Capital actuel: ${self.current_capital:.2f} (Variation: {(self.current_capital - self.initial_capital) / self.initial_capital:.2%})")
                    logger.info(f"Positions ouvertes: {len(self.paper_positions)}")
                    
                    # Calculer les métriques intermédiaires
                    await self.calculate_performance_metrics()
                    
                    # Attendre avant la prochaine itération
                    logger.info(f"Attente de {CHECK_INTERVAL} secondes avant le prochain cycle...")
                    await asyncio.sleep(CHECK_INTERVAL)
                    
                except Exception as e:
                    logger.error(f"Erreur pendant le cycle de test: {e}", exc_info=True)
                    await asyncio.sleep(60)  # Attendre une minute en cas d'erreur
        
        except KeyboardInterrupt:
            logger.info("Interruption utilisateur détectée. Arrêt du test...")
        
        finally:
            # Fermer toutes les positions ouvertes
            logger.info("Fermeture de toutes les positions ouvertes...")
            for position in list(self.paper_positions):
                instrument = position['instrument']
                direction = position['direction']
                amount = position['amount']
                
                # Obtenir le prix actuel
                order_book = await self.trader.get_order_book(instrument)
                if not order_book:
                    logger.warning(f"Impossible d'obtenir le carnet d'ordres pour {instrument}")
                    continue
                
                # Déterminer le prix actuel
                if direction == "buy":
                    current_price = order_book["bids"][0][0] if order_book.get("bids") else None
                else:
                    current_price = order_book["asks"][0][0] if order_book.get("asks") else None
                
                if not current_price:
                    logger.warning(f"Prix actuel non disponible pour {instrument}")
                    continue
                
                # Simuler la fermeture de la position
                close_direction = "buy" if direction == "sell" else "sell"
                await self.simulate_trade("close", instrument, amount, current_price, close_direction)
            
            # Générer le rapport final
            report_path = await self.generate_performance_report()
            
            # Fermer la session
            await self.client.close_session()
            
            logger.info(f"Test de paper trading terminé. Rapport disponible: {report_path}")
            logger.info(f"Capital final: ${self.current_capital:.2f} (Rendement: {(self.current_capital - self.initial_capital) / self.initial_capital:.2%})")
            
            return self.performance_metrics

async def main():
    """Fonction principale."""
    logger.info("=== Démarrage du test de paper trading ===")
    
    # Créer et exécuter le test
    test = PaperTradingTest(test_duration_hours=24)  # Test sur 24 heures
    metrics = await test.run()
    
    # Afficher les métriques finales
    logger.info("=== Métriques de performance ===")
    logger.info(f"Capital initial: ${test.initial_capital:.2f}")
    logger.info(f"Capital final: ${metrics['final_capital']:.2f}")
    logger.info(f"Rendement total: {metrics['total_return']:.2%}")
    logger.info(f"Nombre de trades: {metrics['total_trades']}")
    logger.info(f"Taux de réussite: {metrics['win_rate']:.2%}")
    logger.info(f"Profit Factor: {metrics['profit_factor']:.2f}")
    logger.info(f"Drawdown maximal: {metrics['max_drawdown']:.2%}")
    logger.info(f"Ratio de Sharpe: {metrics['sharpe_ratio']:.2f}")

if __name__ == "__main__":
    asyncio.run(main())

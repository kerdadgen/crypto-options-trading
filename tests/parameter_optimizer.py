"""
Script d'optimisation des paramètres pour la stratégie de trading d'options crypto.
Ce script permet de tester différentes combinaisons de paramètres pour trouver les valeurs optimales.
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
from itertools import product

# Ajouter le répertoire parent au chemin pour importer les modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importer les modules de l'application
from implementation.deribit_client import DeribitClient
from implementation.volatility_analyzer import VolatilityAnalyzer
from implementation.options_trader import OptionsTrader
from implementation.config import (
    LOG_LEVEL, CHECK_INTERVAL, POSITION_CHECK_INTERVAL,
    CAPITAL_TOTAL, CAPITAL_ACTIF, RESERVE_SECURITE
)

# Configuration du logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('parameter_optimization.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Créer le répertoire de données s'il n'existe pas
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

class ParameterOptimizer:
    """Classe pour optimiser les paramètres de la stratégie."""
    
    def __init__(self, test_duration_hours=12, initial_capital=CAPITAL_TOTAL):
        """
        Initialise l'optimiseur de paramètres.
        
        Args:
            test_duration_hours (int): Durée du test en heures
            initial_capital (float): Capital initial pour le test
        """
        self.client = DeribitClient()
        self.test_duration = test_duration_hours * 3600  # Convertir en secondes
        self.initial_capital = initial_capital
        self.results = []
    
    async def initialize(self):
        """Initialise les composants du système."""
        logger.info("Initialisation de l'optimiseur de paramètres...")
        
        # Créer une session et s'authentifier
        await self.client.create_session()
        auth_result = await self.client.authenticate()
        
        if not auth_result:
            logger.error("Échec de l'authentification. Arrêt de l'optimisation.")
            return False
        
        logger.info("Optimiseur initialisé avec succès.")
        return True
    
    async def run_test_with_parameters(self, params):
        """
        Exécute un test avec un ensemble spécifique de paramètres.
        
        Args:
            params (dict): Paramètres à tester
            
        Returns:
            dict: Résultats du test
        """
        from tests.paper_trading_test import PaperTradingTest
        
        # Créer une instance de test avec les paramètres spécifiés
        test = PaperTradingTest(test_duration_hours=self.test_duration / 3600, initial_capital=self.initial_capital)
        
        # Remplacer les paramètres par défaut par ceux à tester
        test.analyzer = VolatilityAnalyzer(self.client)
        
        # Modifier les paramètres de l'analyseur
        test.analyzer.IV_HV_HIGH_THRESHOLD = params['IV_HV_HIGH_THRESHOLD']
        test.analyzer.IV_HV_LOW_THRESHOLD = params['IV_HV_LOW_THRESHOLD']
        
        # Modifier les paramètres du trader
        test.trader = OptionsTrader(self.client, test.analyzer)
        test.trader.PROFIT_TARGET_PCT = params['PROFIT_TARGET_PCT']
        test.trader.STOP_LOSS_PCT = params['STOP_LOSS_PCT']
        
        # Exécuter le test
        logger.info(f"Démarrage du test avec paramètres: {params}")
        metrics = await test.run()
        
        # Ajouter les paramètres aux résultats
        result = {
            'parameters': params,
            'metrics': metrics
        }
        
        self.results.append(result)
        return result
    
    async def optimize(self):
        """
        Exécute l'optimisation des paramètres.
        
        Returns:
            dict: Meilleurs paramètres et leurs résultats
        """
        if not await self.initialize():
            return None
        
        # Définir les plages de paramètres à tester
        param_ranges = {
            'IV_HV_HIGH_THRESHOLD': [1.2, 1.3, 1.4],
            'IV_HV_LOW_THRESHOLD': [0.6, 0.7, 0.8],
            'PROFIT_TARGET_PCT': [0.3, 0.5, 0.7],
            'STOP_LOSS_PCT': [0.3, 0.5, 0.7]
        }
        
        # Générer toutes les combinaisons de paramètres
        param_combinations = [dict(zip(param_ranges.keys(), values)) 
                             for values in product(*param_ranges.values())]
        
        logger.info(f"Optimisation avec {len(param_combinations)} combinaisons de paramètres")
        
        try:
            # Exécuter les tests pour chaque combinaison de paramètres
            for params in param_combinations:
                await self.run_test_with_parameters(params)
                
                # Sauvegarder les résultats intermédiaires
                self.save_results()
        
        except KeyboardInterrupt:
            logger.info("Interruption utilisateur détectée. Arrêt de l'optimisation...")
        
        finally:
            # Fermer la session
            await self.client.close_session()
            
            # Analyser les résultats
            best_result = self.analyze_results()
            
            logger.info("Optimisation terminée.")
            return best_result
    
    def save_results(self):
        """Sauvegarde les résultats de l'optimisation."""
        results_file = os.path.join(DATA_DIR, 'optimization_results.json')
        
        try:
            with open(results_file, 'w') as f:
                json.dump(self.results, f, indent=2, default=str)
            
            logger.info(f"Résultats sauvegardés dans {results_file}")
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des résultats: {e}")
    
    def analyze_results(self):
        """
        Analyse les résultats de l'optimisation.
        
        Returns:
            dict: Meilleurs paramètres et leurs résultats
        """
        if not self.results:
            logger.warning("Aucun résultat à analyser")
            return None
        
        # Convertir les résultats en DataFrame pour faciliter l'analyse
        results_data = []
        
        for result in self.results:
            params = result['parameters']
            metrics = result['metrics']
            
            row = {
                'IV_HV_HIGH_THRESHOLD': params['IV_HV_HIGH_THRESHOLD'],
                'IV_HV_LOW_THRESHOLD': params['IV_HV_LOW_THRESHOLD'],
                'PROFIT_TARGET_PCT': params['PROFIT_TARGET_PCT'],
                'STOP_LOSS_PCT': params['STOP_LOSS_PCT'],
                'total_return': metrics.get('total_return', 0),
                'win_rate': metrics.get('win_rate', 0),
                'profit_factor': metrics.get('profit_factor', 0),
                'max_drawdown': metrics.get('max_drawdown', 1),
                'sharpe_ratio': metrics.get('sharpe_ratio', 0),
                'total_trades': metrics.get('total_trades', 0)
            }
            
            results_data.append(row)
        
        df = pd.DataFrame(results_data)
        
        # Sauvegarder le DataFrame
        csv_file = os.path.join(DATA_DIR, 'optimization_results.csv')
        df.to_csv(csv_file, index=False)
        
        # Trouver les meilleurs paramètres selon différents critères
        best_return = df.loc[df['total_return'].idxmax()]
        best_sharpe = df.loc[df['sharpe_ratio'].idxmax()]
        best_profit_factor = df.loc[df['profit_factor'].idxmax()]
        
        # Créer un score composite (pondéré)
        df['composite_score'] = (
            df['total_return'] * 0.4 + 
            df['sharpe_ratio'] * 0.3 + 
            df['profit_factor'] * 0.2 + 
            (1 - df['max_drawdown']) * 0.1
        )
        
        best_composite = df.loc[df['composite_score'].idxmax()]
        
        # Générer des visualisations
        self.generate_optimization_visualizations(df)
        
        # Créer un rapport HTML
        self.generate_optimization_report(df, best_return, best_sharpe, best_profit_factor, best_composite)
        
        logger.info("=== Meilleurs paramètres ===")
        logger.info(f"Meilleur rendement: {best_return.to_dict()}")
        logger.info(f"Meilleur ratio de Sharpe: {best_sharpe.to_dict()}")
        logger.info(f"Meilleur profit factor: {best_profit_factor.to_dict()}")
        logger.info(f"Meilleur score composite: {best_composite.to_dict()}")
        
        return {
            'best_return': best_return.to_dict(),
            'best_sharpe': best_sharpe.to_dict(),
            'best_profit_factor': best_profit_factor.to_dict(),
            'best_composite': best_composite.to_dict(),
            'all_results': df.to_dict(orient='records')
        }
    
    def generate_optimization_visualizations(self, df):
        """
        Génère des visualisations pour les résultats de l'optimisation.
        
        Args:
            df (DataFrame): DataFrame contenant les résultats
        """
        # Créer un répertoire pour les visualisations
        viz_dir = os.path.join(DATA_DIR, 'visualizations')
        os.makedirs(viz_dir, exist_ok=True)
        
        # 1. Heatmap des rendements par IV_HV_HIGH_THRESHOLD et IV_HV_LOW_THRESHOLD
        plt.figure(figsize=(10, 8))
        pivot_iv = df.pivot_table(
            values='total_return', 
            index='IV_HV_HIGH_THRESHOLD', 
            columns='IV_HV_LOW_THRESHOLD',
            aggfunc='mean'
        )
        plt.imshow(pivot_iv, cmap='viridis')
        plt.colorbar(label='Rendement total')
        plt.title('Rendement par seuils IV/HV')
        plt.xlabel('IV_HV_LOW_THRESHOLD')
        plt.ylabel('IV_HV_HIGH_THRESHOLD')
        plt.xticks(range(len(pivot_iv.columns)), pivot_iv.columns)
        plt.yticks(range(len(pivot_iv.index)), pivot_iv.index)
        
        for i in range(len(pivot_iv.index)):
            for j in range(len(pivot_iv.columns)):
                plt.text(j, i, f"{pivot_iv.iloc[i, j]:.2%}", ha='center', va='center', color='white')
        
        plt.savefig(os.path.join(viz_dir, 'heatmap_iv_thresholds.png'))
        
        # 2. Heatmap des rendements par PROFIT_TARGET_PCT et STOP_LOSS_PCT
        plt.figure(figsize=(10, 8))
        pivot_pnl = df.pivot_table(
            values='total_return', 
            index='PROFIT_TARGET_PCT', 
            columns='STOP_LOSS_PCT',
            aggfunc='mean'
        )
        plt.imshow(pivot_pnl, cmap='viridis')
        plt.colorbar(label='Rendement total')
        plt.title('Rendement par seuils de profit et stop-loss')
        plt.xlabel('STOP_LOSS_PCT')
        plt.ylabel('PROFIT_TARGET_PCT')
        plt.xticks(range(len(pivot_pnl.columns)), pivot_pnl.columns)
        plt.yticks(range(len(pivot_pnl.index)), pivot_pnl.index)
        
        for i in range(len(pivot_pnl.index)):
            for j in range(len(pivot_pnl.columns)):
                plt.text(j, i, f"{pivot_pnl.iloc[i, j]:.2%}", ha='center', va='center', color='white')
        
        plt.savefig(os.path.join(viz_dir, 'heatmap_profit_stoploss.png'))
        
        # 3. Graphique à barres des meilleurs paramètres par métrique
        metrics = ['total_return', 'sharpe_ratio', 'profit_factor', 'win_rate']
        best_params = {}
        
        for metric in metrics:
            best_idx = df[metric].idxmax()
            best_params[metric] = df.iloc[best_idx]
        
        # Créer un graphique pour chaque paramètre
        params = ['IV_HV_HIGH_THRESHOLD', 'IV_HV_LOW_THRESHOLD', 'PROFIT_TARGET_PCT', 'STOP_LOSS_PCT']
        
        for param in params:
            plt.figure(figsize=(10, 6))
            values = [best_params[metric][param] for metric in metrics]
            plt.bar(metrics, values)
            plt.title(f'Meilleure valeur de {param} par métrique')
            plt.ylabel(param)
            plt.savefig(os.path.join(viz_dir, f'best_{param}_by_metric.png'))
        
        # 4. Graphique de dispersion 3D
        from mpl_toolkits.mplot3d import Axes3D
        
        fig = plt.figure(figsize=(12, 10))
        ax = fig.add_subplot(111, projection='3d')
        
        x = df['IV_HV_HIGH_THRESHOLD']
        y = df['IV_HV_LOW_THRESHOLD']
        z = df['total_return']
        c = df['sharpe_ratio']
        
        scatter = ax.scatter(x, y, z, c=c, cmap='viridis', s=50)
        
        ax.set_xlabel('IV_HV_HIGH_THRESHOLD')
        ax.set_ylabel('IV_HV_LOW_THRESHOLD')
        ax.set_zlabel('Rendement total')
        
        plt.colorbar(scatter, label='Ratio de Sharpe')
        plt.title('Relation entre seuils IV/HV, rendement et ratio de Sharpe')
        
        plt.savefig(os.path.join(viz_dir, '3d_scatter.png'))
    
    def generate_optimization_report(self, df, best_return, best_sharpe, best_profit_factor, best_composite):
        """
        Génère un rapport HTML pour les résultats de l'optimisation.
        
        Args:
            df (DataFrame): DataFrame contenant tous les résultats
            best_return (Series): Meilleurs paramètres pour le rendement
            best_sharpe (Series): Meilleurs paramètres pour le ratio de Sharpe
            best_profit_factor (Series): Meilleurs paramètres pour le profit factor
            best_composite (Series): Meilleurs paramètres pour le score composite
        """
        report_path = os.path.join(DATA_DIR, 'optimization_report.html')
        viz_dir = os.path.join(DATA_DIR, 'visualizations')
        
        with open(report_path, 'w') as f:
            f.write(f"""
            <html>
            <head>
                <title>Rapport d'Optimisation - Stratégie d'Options Crypto</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    h1, h2, h3 {{ color: #333366; }}
                    table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
                    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                    th {{ background-color: #f2f2f2; }}
                    tr:nth-child(even) {{ background-color: #f9f9f9; }}
                    .positive {{ color: green; }}
                    .negative {{ color: red; }}
                    .metrics {{ display: flex; flex-wrap: wrap; }}
                    .metric-box {{ border: 1px solid #ddd; padding: 15px; margin: 10px; flex: 1; min-width: 200px; }}
                    .parameter-section {{ margin-bottom: 30px; }}
                    .visualization {{ margin: 20px 0; text-align: center; }}
                </style>
            </head>
            <body>
                <h1>Rapport d'Optimisation - Stratégie d'Options Crypto</h1>
                <p>Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                
                <h2>Résumé</h2>
                <p>Nombre total de combinaisons testées: {len(df)}</p>
                
                <div class="parameter-section">
                    <h2>Meilleurs paramètres</h2>
                    
                    <h3>Meilleur rendement total</h3>
                    <div class="metric-box">
                        <p>IV_HV_HIGH_THRESHOLD: {best_return['IV_HV_HIGH_THRESHOLD']}</p>
                        <p>IV_HV_LOW_THRESHOLD: {best_return['IV_HV_LOW_THRESHOLD']}</p>
                        <p>PROFIT_TARGET_PCT: {best_return['PROFIT_TARGET_PCT']}</p>
                        <p>STOP_LOSS_PCT: {best_return['STOP_LOSS_PCT']}</p>
                        <p>Rendement: <span class="positive">{best_return['total_return']:.2%}</span></p>
                        <p>Ratio de Sharpe: {best_return['sharpe_ratio']:.2f}</p>
                        <p>Profit Factor: {best_return['profit_factor']:.2f}</p>
                        <p>Taux de réussite: {best_return['win_rate']:.2%}</p>
                        <p>Drawdown maximal: {best_return['max_drawdown']:.2%}</p>
                    </div>
                    
                    <h3>Meilleur ratio de Sharpe</h3>
                    <div class="metric-box">
                        <p>IV_HV_HIGH_THRESHOLD: {best_sharpe['IV_HV_HIGH_THRESHOLD']}</p>
                        <p>IV_HV_LOW_THRESHOLD: {best_sharpe['IV_HV_LOW_THRESHOLD']}</p>
                        <p>PROFIT_TARGET_PCT: {best_sharpe['PROFIT_TARGET_PCT']}</p>
                        <p>STOP_LOSS_PCT: {best_sharpe['STOP_LOSS_PCT']}</p>
                        <p>Rendement: <span class="positive">{best_sharpe['total_return']:.2%}</span></p>
                        <p>Ratio de Sharpe: {best_sharpe['sharpe_ratio']:.2f}</p>
                        <p>Profit Factor: {best_sharpe['profit_factor']:.2f}</p>
                        <p>Taux de réussite: {best_sharpe['win_rate']:.2%}</p>
                        <p>Drawdown maximal: {best_sharpe['max_drawdown']:.2%}</p>
                    </div>
                    
                    <h3>Meilleur profit factor</h3>
                    <div class="metric-box">
                        <p>IV_HV_HIGH_THRESHOLD: {best_profit_factor['IV_HV_HIGH_THRESHOLD']}</p>
                        <p>IV_HV_LOW_THRESHOLD: {best_profit_factor['IV_HV_LOW_THRESHOLD']}</p>
                        <p>PROFIT_TARGET_PCT: {best_profit_factor['PROFIT_TARGET_PCT']}</p>
                        <p>STOP_LOSS_PCT: {best_profit_factor['STOP_LOSS_PCT']}</p>
                        <p>Rendement: <span class="positive">{best_profit_factor['total_return']:.2%}</span></p>
                        <p>Ratio de Sharpe: {best_profit_factor['sharpe_ratio']:.2f}</p>
                        <p>Profit Factor: {best_profit_factor['profit_factor']:.2f}</p>
                        <p>Taux de réussite: {best_profit_factor['win_rate']:.2%}</p>
                        <p>Drawdown maximal: {best_profit_factor['max_drawdown']:.2%}</p>
                    </div>
                    
                    <h3>Meilleur score composite</h3>
                    <div class="metric-box">
                        <p>IV_HV_HIGH_THRESHOLD: {best_composite['IV_HV_HIGH_THRESHOLD']}</p>
                        <p>IV_HV_LOW_THRESHOLD: {best_composite['IV_HV_LOW_THRESHOLD']}</p>
                        <p>PROFIT_TARGET_PCT: {best_composite['PROFIT_TARGET_PCT']}</p>
                        <p>STOP_LOSS_PCT: {best_composite['STOP_LOSS_PCT']}</p>
                        <p>Rendement: <span class="positive">{best_composite['total_return']:.2%}</span></p>
                        <p>Ratio de Sharpe: {best_composite['sharpe_ratio']:.2f}</p>
                        <p>Profit Factor: {best_composite['profit_factor']:.2f}</p>
                        <p>Taux de réussite: {best_composite['win_rate']:.2%}</p>
                        <p>Drawdown maximal: {best_composite['max_drawdown']:.2%}</p>
                        <p>Score composite: {best_composite['composite_score']:.4f}</p>
                    </div>
                </div>
                
                <div class="visualization-section">
                    <h2>Visualisations</h2>
                    
                    <div class="visualization">
                        <h3>Rendement par seuils IV/HV</h3>
                        <img src="visualizations/heatmap_iv_thresholds.png" alt="Heatmap des seuils IV/HV" style="max-width: 100%;">
                    </div>
                    
                    <div class="visualization">
                        <h3>Rendement par seuils de profit et stop-loss</h3>
                        <img src="visualizations/heatmap_profit_stoploss.png" alt="Heatmap des seuils de profit et stop-loss" style="max-width: 100%;">
                    </div>
                    
                    <div class="visualization">
                        <h3>Relation entre seuils IV/HV, rendement et ratio de Sharpe</h3>
                        <img src="visualizations/3d_scatter.png" alt="Graphique 3D" style="max-width: 100%;">
                    </div>
                </div>
                
                <h2>Tous les résultats</h2>
                <table>
                    <tr>
                        <th>IV_HV_HIGH</th>
                        <th>IV_HV_LOW</th>
                        <th>PROFIT_TARGET</th>
                        <th>STOP_LOSS</th>
                        <th>Rendement</th>
                        <th>Sharpe</th>
                        <th>Profit Factor</th>
                        <th>Win Rate</th>
                        <th>Max Drawdown</th>
                        <th>Trades</th>
                    </tr>
            """)
            
            # Ajouter tous les résultats
            for _, row in df.sort_values('composite_score', ascending=False).iterrows():
                f.write(f"""
                    <tr>
                        <td>{row['IV_HV_HIGH_THRESHOLD']}</td>
                        <td>{row['IV_HV_LOW_THRESHOLD']}</td>
                        <td>{row['PROFIT_TARGET_PCT']}</td>
                        <td>{row['STOP_LOSS_PCT']}</td>
                        <td class="{'positive' if row['total_return'] >= 0 else 'negative'}">{row['total_return']:.2%}</td>
                        <td>{row['sharpe_ratio']:.2f}</td>
                        <td>{row['profit_factor']:.2f}</td>
                        <td>{row['win_rate']:.2%}</td>
                        <td>{row['max_drawdown']:.2%}</td>
                        <td>{row['total_trades']}</td>
                    </tr>
                """)
            
            f.write("""
                </table>
                
                <h2>Recommandations</h2>
                <p>Basé sur les résultats de l'optimisation, nous recommandons les paramètres suivants pour la stratégie de trading d'options crypto:</p>
                <ul>
            """)
            
            # Ajouter les recommandations
            f.write(f"""
                    <li><strong>IV_HV_HIGH_THRESHOLD:</strong> {best_composite['IV_HV_HIGH_THRESHOLD']} - Seuil pour considérer la volatilité implicite comme élevée</li>
                    <li><strong>IV_HV_LOW_THRESHOLD:</strong> {best_composite['IV_HV_LOW_THRESHOLD']} - Seuil pour considérer la volatilité implicite comme basse</li>
                    <li><strong>PROFIT_TARGET_PCT:</strong> {best_composite['PROFIT_TARGET_PCT']} - Objectif de profit (pourcentage du profit maximal)</li>
                    <li><strong>STOP_LOSS_PCT:</strong> {best_composite['STOP_LOSS_PCT']} - Stop-loss (pourcentage de la perte maximale)</li>
            """)
            
            f.write("""
                </ul>
                
                <p>Ces paramètres offrent le meilleur équilibre entre rendement, risque et stabilité.</p>
            </body>
            </html>
            """)
        
        logger.info(f"Rapport d'optimisation généré: {report_path}")
        return report_path

async def main():
    """Fonction principale."""
    logger.info("=== Démarrage de l'optimisation des paramètres ===")
    
    # Créer et exécuter l'optimiseur
    optimizer = ParameterOptimizer(test_duration_hours=12)  # Test sur 12 heures
    best_params = await optimizer.optimize()
    
    if best_params:
        logger.info("=== Optimisation terminée ===")
        logger.info(f"Meilleurs paramètres (score composite): {best_params['best_composite']}")
    else:
        logger.error("Échec de l'optimisation")

if __name__ == "__main__":
    asyncio.run(main())

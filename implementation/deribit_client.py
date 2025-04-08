"""
Module d'authentification et de connexion à l'API Deribit.
Ce module gère l'authentification et les requêtes HTTP vers l'API Deribit.
"""

import time
import hmac
import hashlib
import aiohttp
import asyncio
import logging
from config import API_KEY, API_SECRET, API_URL

# Configuration du logging
logger = logging.getLogger(__name__)

class DeribitClient:
    """Client pour interagir avec l'API Deribit."""
    
    def __init__(self):
        """Initialise le client Deribit."""
        self.session = None
        self.access_token = None
        self.refresh_token = None
        self.token_expiry = 0
        
    async def create_session(self):
        """Crée une session HTTP pour les requêtes API."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close_session(self):
        """Ferme la session HTTP."""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def _generate_signature(self, timestamp, method, uri, params=""):
        """Génère une signature HMAC pour l'authentification."""
        message = str(timestamp) + "\n" + method + "\n" + uri + "\n" + params
        signature = hmac.new(
            bytes(API_SECRET, "latin-1"),
            msg=bytes(message, "latin-1"),
            digestmod=hashlib.sha256
        ).hexdigest()
        return signature
    
    async def authenticate(self):
        """Authentifie auprès de l'API Deribit et obtient un token d'accès."""
        session = await self.create_session()
        
        timestamp = int(time.time() * 1000)
        method = "public/auth"
        params = {
            "grant_type": "client_credentials",
            "client_id": API_KEY,
            "client_secret": API_SECRET
        }
        
        try:
            async with session.post(API_URL + method, json=params) as response:
                result = await response.json()
                
                if "error" in result:
                    logger.error(f"Erreur d'authentification: {result['error']}")
                    return False
                
                self.access_token = result.get("result", {}).get("access_token")
                self.refresh_token = result.get("result", {}).get("refresh_token")
                expires_in = result.get("result", {}).get("expires_in", 0)
                self.token_expiry = time.time() + expires_in - 60  # Renouveler 60s avant expiration
                
                # Mettre à jour les headers pour les requêtes futures
                session.headers.update({"Authorization": f"Bearer {self.access_token}"})
                
                logger.info("Authentification réussie")
                return True
        except Exception as e:
            logger.error(f"Erreur lors de l'authentification: {e}")
            return False
    
    async def refresh_auth(self):
        """Rafraîchit le token d'authentification."""
        if not self.refresh_token:
            return await self.authenticate()
        
        session = await self.create_session()
        
        method = "public/auth"
        params = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token
        }
        
        try:
            async with session.post(API_URL + method, json=params) as response:
                result = await response.json()
                
                if "error" in result:
                    logger.error(f"Erreur de rafraîchissement du token: {result['error']}")
                    return await self.authenticate()
                
                self.access_token = result.get("result", {}).get("access_token")
                self.refresh_token = result.get("result", {}).get("refresh_token")
                expires_in = result.get("result", {}).get("expires_in", 0)
                self.token_expiry = time.time() + expires_in - 60
                
                # Mettre à jour les headers pour les requêtes futures
                session.headers.update({"Authorization": f"Bearer {self.access_token}"})
                
                logger.info("Token rafraîchi avec succès")
                return True
        except Exception as e:
            logger.error(f"Erreur lors du rafraîchissement du token: {e}")
            return await self.authenticate()
    
    async def check_auth(self):
        """Vérifie si l'authentification est valide et la rafraîchit si nécessaire."""
        if not self.access_token or time.time() > self.token_expiry:
            if self.refresh_token and time.time() <= self.token_expiry + 3600:
                return await self.refresh_auth()
            else:
                return await self.authenticate()
        return True
    
    async def request(self, method, endpoint, params=None, is_private=False):
        """
        Effectue une requête à l'API Deribit.
        
        Args:
            method (str): Méthode HTTP ('GET', 'POST')
            endpoint (str): Endpoint API
            params (dict, optional): Paramètres de la requête
            is_private (bool): Si True, vérifie l'authentification avant la requête
            
        Returns:
            dict: Résultat de la requête
        """
        if is_private and not await self.check_auth():
            logger.error("Échec de l'authentification pour une requête privée")
            return {"error": "Authentication failed"}
        
        session = await self.create_session()
        url = API_URL + endpoint
        
        try:
            if method.upper() == 'GET':
                async with session.get(url, params=params) as response:
                    result = await response.json()
            elif method.upper() == 'POST':
                async with session.post(url, json=params) as response:
                    result = await response.json()
            else:
                logger.error(f"Méthode HTTP non supportée: {method}")
                return {"error": f"Unsupported HTTP method: {method}"}
            
            if "error" in result:
                logger.error(f"Erreur API: {result['error']}")
            
            return result
        except Exception as e:
            logger.error(f"Erreur lors de la requête {endpoint}: {e}")
            return {"error": str(e)}
    
    async def get_public(self, endpoint, params=None):
        """Effectue une requête GET publique."""
        return await self.request('GET', endpoint, params)
    
    async def get_private(self, endpoint, params=None):
        """Effectue une requête GET privée (authentifiée)."""
        return await self.request('GET', endpoint, params, is_private=True)
    
    async def post_private(self, endpoint, params=None):
        """Effectue une requête POST privée (authentifiée)."""
        return await self.request('POST', endpoint, params, is_private=True)

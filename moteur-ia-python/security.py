from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration Keycloak (Alignée avec le Frontend)
# Port 8081 est celui utilisé dans keycloak.js
KEYCLOAK_URL = "http://localhost:8081/realms/digitalbank-realm"
JWKS_URL = f"{KEYCLOAK_URL}/protocol/openid-connect/certs"

# Swagger UI configuration
TOKEN_URL = f"{KEYCLOAK_URL}/protocol/openid-connect/token"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=TOKEN_URL)

def get_public_keys():
    try:
        response = requests.get(JWKS_URL)
        return response.json()
    except Exception as e:
        print(f"❌ Erreur contact Keycloak ({JWKS_URL}): {e}")
        raise HTTPException(status_code=500, detail="Impossible de contacter Keycloak")

def verify_token(token: str = Depends(oauth2_scheme)):
    jwks = get_public_keys()
    
    try:
        unverified_header = jwt.get_unverified_header(token)
        rsa_key = {}
        for key in jwks.get("keys", []):
            if key["kid"] == unverified_header.get("kid"):
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"]
                }
                break
        
        if not rsa_key:
            raise HTTPException(status_code=401, detail="Clé de signature introuvable")
        
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            options={"verify_aud": False} # Le frontend et le backend peuvent avoir des audiences différentes
        )
        return payload
        
    except JWTError as e:
        print(f"❌ Erreur validation JWT: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )
import sys
import os

# Ajouter le répertoire src au chemin
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

print("=== TEST DES IMPORTS ===")

# Test 1: Imports de base
try:
    print("\n1. Test imports de base...")
    from database import init_database, get_db
    print("✓ database: OK")
except Exception as e:
    print(f"✗ database: {e}")

# Test 2: Modèles
try:
    print("\n2. Test modèles...")
    from models.user import User
    print("✓ models.user: OK")
except Exception as e:
    print(f"✗ models.user: {e}")

# Test 3: Services
try:
    print("\n3. Test services...")
    from services.auth_service import AuthService
    from services.user_service import UserService
    print("✓ services: OK")
except Exception as e:
    print(f"✗ services: {e}")

# Test 4: Routers
try:
    print("\n4. Test routers...")
    from routers.auth import router as auth_router
    from routers.users import router as users_router
    print("✓ routers: OK")
except Exception as e:
    print(f"✗ routers: {e}")

print("\n=== FIN DES TESTS ===")
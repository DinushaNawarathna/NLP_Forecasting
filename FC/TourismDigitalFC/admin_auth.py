"""
Admin Authentication Module for Sigiriya Tourism Digital Twin

Handles admin registration, login, and JWT token management.
Uses MongoDB for storing admin credentials.
"""

import os
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

class AdminConfig:
    """Admin authentication configuration"""
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here-change-this-in-production')
    ALGORITHM = os.getenv('ALGORITHM', 'HS256')
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', '30'))


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class AdminRegisterRequest(BaseModel):
    """Admin registration request model"""
    name: str
    email: EmailStr
    password: str
    phone: Optional[str] = None


class AdminLoginRequest(BaseModel):
    """Admin login request model"""
    email: EmailStr
    password: str


class AdminResponse(BaseModel):
    """Admin response model (excludes password)"""
    id: Optional[str] = None
    name: str
    email: str
    phone: Optional[str] = None
    created_at: Optional[str] = None


class TokenResponse(BaseModel):
    """Token response model"""
    access_token: str
    token_type: str = "bearer"
    admin: AdminResponse
    name: str


# ============================================================================
# PASSWORD HASHING
# ============================================================================

def hash_password(password: str) -> str:
    """
    Hash password using PBKDF2.
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password string
    """
    salt = os.urandom(16).hex()
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"{salt}${pwd_hash.hex()}"


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verify password against hash.
    
    Args:
        password: Plain text password to verify
        hashed_password: Stored hashed password
        
    Returns:
        True if password matches, False otherwise
    """
    try:
        salt, pwd_hash = hashed_password.split('$')
        new_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return new_hash.hex() == pwd_hash
    except Exception as e:
        logger.error(f"Error verifying password: {e}")
        return False


# ============================================================================
# JWT TOKEN MANAGEMENT
# ============================================================================

def create_access_token(admin_id: str, email: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token.
    
    Args:
        admin_id: Admin user ID
        email: Admin email
        expires_delta: Token expiration time delta
        
    Returns:
        JWT token string
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=AdminConfig.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    expire = datetime.utcnow() + expires_delta
    to_encode = {
        'sub': str(admin_id),
        'email': email,
        'exp': expire,
        'iat': datetime.utcnow()
    }
    
    encoded_jwt = jwt.encode(to_encode, AdminConfig.SECRET_KEY, algorithm=AdminConfig.ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify JWT token.
    
    Args:
        token: JWT token to verify
        
    Returns:
        Decoded token payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, AdminConfig.SECRET_KEY, algorithms=[AdminConfig.ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired")
        return None
    except jwt.InvalidTokenError:
        logger.warning("Invalid token")
        return None
    except Exception as e:
        logger.error(f"Error verifying token: {e}")
        return None


# ============================================================================
# ADMIN OPERATIONS
# ============================================================================

class AdminOperations:
    """Handle admin authentication and management operations"""
    
    @staticmethod
    def register_admin(db_config, db_operations, name: str, email: str, 
                      password: str, phone: Optional[str] = None) -> tuple[bool, Optional[Dict]]:
        """
        Register a new admin user.
        
        Args:
            db_config: MongoDB configuration instance
            db_operations: Database operations instance
            name: Admin name
            email: Admin email
            password: Admin password
            phone: Admin phone number (optional)
            
        Returns:
            (success: bool, data: Dict with token/error)
        """
        try:
            # Get admin collection
            admin_collection = db_config.get_collection('admin_users')
            if admin_collection is None:
                return False, {'error': 'Database not connected'}
            
            # Check if email already exists
            existing = admin_collection.find_one({'email': email.lower()})
            if existing:
                logger.warning(f"Registration failed: Email {email} already exists")
                return False, {'error': 'Email already registered'}
            
            # Hash password
            hashed_pwd = hash_password(password)
            
            # Create admin document
            admin_doc = {
                'name': name,
                'email': email.lower(),
                'password': hashed_pwd,
                'phone': phone,
                'created_at': datetime.utcnow(),
                'is_active': True,
                'last_login': None
            }
            
            # Insert into database
            result = admin_collection.insert_one(admin_doc)
            admin_id = result.inserted_id
            
            # Create token
            token = create_access_token(str(admin_id), email)
            
            logger.info(f"✅ Admin registered successfully: {email}")
            
            return True, {
                'token': token,
                'name': name,
                'email': email,
                'message': 'Registration successful'
            }
            
        except Exception as e:
            logger.error(f"❌ Error registering admin: {e}")
            return False, {'error': str(e)}
    
    @staticmethod
    def login_admin(db_config, email: str, password: str) -> tuple[bool, Optional[Dict]]:
        """
        Login an admin user.
        
        Supports:
        1. Database-backed login (when MongoDB is running)
        2. Demo credentials (when database is unavailable)
        
        Demo Credentials:
        - Email: admin@sigiriya.local
        - Password: demo123
        
        Args:
            db_config: MongoDB configuration instance
            email: Admin email
            password: Admin password
            
        Returns:
            (success: bool, data: Dict with token/error)
        """
        try:
            # Demo credentials for testing without MongoDB
            DEMO_EMAIL = "admin@sigiriya.local"
            DEMO_PASSWORD = "demo123"
            
            # Get admin collection
            admin_collection = db_config.get_collection('admin_users')
            
            # If database is connected, use database authentication
            if admin_collection is not None:
                # Find admin by email
                admin = admin_collection.find_one({'email': email.lower()})
                if not admin:
                    logger.warning(f"Login failed: Admin not found: {email}")
                    return False, {'error': 'Invalid email or password'}
                
                # Verify password
                if not verify_password(password, admin['password']):
                    logger.warning(f"Login failed: Invalid password for {email}")
                    return False, {'error': 'Invalid email or password'}
                
                # Check if admin is active
                if not admin.get('is_active', True):
                    logger.warning(f"Login failed: Admin account inactive: {email}")
                    return False, {'error': 'Admin account is inactive'}
                
                # Update last login
                admin_collection.update_one(
                    {'_id': admin['_id']},
                    {'$set': {'last_login': datetime.utcnow()}}
                )
                
                # Create token
                token = create_access_token(str(admin['_id']), email)
                
                logger.info(f"✅ Admin login successful: {email}")
                
                return True, {
                    'token': token,
                    'name': admin['name'],
                    'email': admin['email'],
                    'message': 'Login successful'
                }
            
            # Fallback: Demo credentials when database is unavailable
            else:
                logger.warning("⚠️  Database unavailable - using demo credentials")
                
                if email.lower() == DEMO_EMAIL and password == DEMO_PASSWORD:
                    # Create demo token
                    token = create_access_token('demo_admin_id', DEMO_EMAIL)
                    
                    logger.info(f"✅ Demo login successful: {DEMO_EMAIL}")
                    logger.warning("   (Database is offline - using demo mode)")
                    
                    return True, {
                        'token': token,
                        'name': 'Demo Admin',
                        'email': DEMO_EMAIL,
                        'message': 'Demo login - database offline'
                    }
                else:
                    logger.warning(f"Login failed: Invalid credentials (database offline)")
                    logger.info(f"   Hint: Use admin@sigiriya.local / demo123 for demo")
                    return False, {
                        'error': 'Invalid credentials',
                        'hint': 'Database offline. Try admin@sigiriya.local / demo123'
                    }
            
        except Exception as e:
            logger.error(f"Error logging in admin: {e}")
            return False, {'error': str(e)}
    
    @staticmethod
    def get_admin_by_id(db_config, admin_id: str) -> Optional[Dict]:
        """
        Get admin user by ID.
        
        Args:
            db_config: MongoDB configuration instance
            admin_id: Admin user ID
            
        Returns:
            Admin document without password, or None
        """
        try:
            from bson import ObjectId
            
            admin_collection = db_config.get_collection('admin_users')
            if admin_collection is None:
                return None
            
            admin = admin_collection.find_one({'_id': ObjectId(admin_id)})
            if admin:
                admin.pop('password', None)  # Remove password
                admin['_id'] = str(admin['_id'])
                return admin
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting admin: {e}")
            return None
    
    @staticmethod
    def update_admin_profile(db_config, admin_id: str, updates: Dict) -> bool:
        """
        Update admin profile information.
        
        Args:
            db_config: MongoDB configuration instance
            admin_id: Admin user ID
            updates: Dictionary with fields to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            from bson import ObjectId
            
            # Remove sensitive fields from updates
            updates.pop('password', None)
            updates.pop('email', None)
            updates['updated_at'] = datetime.utcnow()
            
            admin_collection = db_config.get_collection('admin_users')
            if admin_collection is None:
                return False
            
            result = admin_collection.update_one(
                {'_id': ObjectId(admin_id)},
                {'$set': updates}
            )
            
            logger.info(f"Admin profile updated: {admin_id}")
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error updating admin profile: {e}")
            return False


# ============================================================================
# TEST FUNCTION
# ============================================================================

if __name__ == "__main__":
    print("\n🧪 Testing Admin Authentication System\n")
    
    # Test password hashing
    print("Testing password hashing...")
    pwd = "TestPassword123!"
    hashed = hash_password(pwd)
    print(f"Original: {pwd}")
    print(f"Hashed: {hashed}")
    print(f"Verified: {verify_password(pwd, hashed)}")
    print(f"Wrong pwd: {verify_password('WrongPassword', hashed)}")
    
    # Test JWT token
    print("\nTesting JWT token creation...")
    token = create_access_token("admin_123", "admin@example.com")
    print(f"Token: {token}")
    payload = verify_token(token)
    if payload:
        print(f"Token verified successfully!")
        print(f"Payload: {payload}")
    else:
        print("Token verification failed!")
    
    print("\n Admin authentication system ready for use!")

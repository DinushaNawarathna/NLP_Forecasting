"""
MongoDB Configuration Module for Sigiriya Tourism Digital Twin

Handles connection to MongoDB Atlas for storing:
- Chat conversation history
- User sessions
- Weather data cache
- Crowd analytics
- System logs
"""

import os
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from typing import Optional, Dict, Any
from datetime import datetime
import logging

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# MONGODB CONNECTION CONFIGURATION
# ============================================================================

class MongoDBConfig:
    """MongoDB configuration and connection management.
    
    Supports both local and cloud MongoDB instances:
    - Local: mongodb://localhost:27017 (default for development)
    - Cloud: MongoDB Atlas URI from environment variable
    """
    
    def __init__(self):
        # Get MongoDB URI from environment variables
        # Default to local MongoDB instance running on port 27017
        use_local = os.getenv('USE_LOCAL_MONGODB', 'true').lower() == 'true'
        
        if use_local:
            self.MONGO_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
            self.is_local = True
        else:
            self.MONGO_URI = os.getenv('MONGODB_URI', 'mongodb+srv://localhost:27017')
            self.is_local = False
        
        # Database name from environment or default
        self.DATABASE_NAME = os.getenv('MONGODB_DB_NAME', 'sigiriya_tourism')
        
        # Collection names
        self.COLLECTIONS = {
            'admin_users': 'admin_users',
            'chat_history': 'chat_conversations',
            'user_sessions': 'user_sessions',
            'visitor_predictions': 'visitor_predictions',
            'weather_data': 'weather_data',
            'system_logs': 'system_logs',
            'user_feedback': 'user_feedback',
            'analytics': 'analytics'
        }
        
        self.client: Optional[MongoClient] = None
        self.db = None
        self._connected = False
    
    def connect(self) -> bool:
        """
        Establish connection to MongoDB (local or cloud).
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            connection_type = "local MongoDB" if self.is_local else "MongoDB Atlas"
            logger.info(f"🔗 Connecting to {connection_type}...")
            
            # Create client with appropriate timeout settings
            client_kwargs = {
                'serverSelectionTimeoutMS': 5000,
                'connectTimeoutMS': 10000,
                'socketTimeoutMS': 10000,
            }
            
            # Add Atlas-specific options only for cloud connections
            if not self.is_local:
                import certifi
                client_kwargs['retryWrites'] = True
                client_kwargs['w'] = 'majority'
                client_kwargs['tlsCAFile'] = certifi.where()
            
            self.client = MongoClient(self.MONGO_URI, **client_kwargs)
            
            # Verify connection with a ping
            self.client.admin.command('ping')
            
            # Get database
            self.db = self.client[self.DATABASE_NAME]
            
            # Create collections if they don't exist
            self._initialize_collections()
            
            self._connected = True
            connection_label = "📍 Local MongoDB" if self.is_local else "☁️  MongoDB Atlas"
            logger.info(f"✅ Successfully connected to {connection_label}!")
            logger.info(f"📊 Database: {self.DATABASE_NAME}")
            logger.info(f"📁 Collections: {list(self.COLLECTIONS.values())}")
            
            return True
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            connection_type = "local MongoDB" if self.is_local else "MongoDB Atlas"
            logger.error(f"❌ Failed to connect to {connection_type}: {e}")
            
            # If local connection fails, suggest checking MongoDB service
            if self.is_local:
                logger.error("⚠️  Please ensure MongoDB is running locally:")
                logger.error("   macOS: brew services start mongodb-community")
                logger.error("   macOS alt: mongod --config /usr/local/etc/mongod.conf")
                logger.error("   OR use Docker: docker run -d -p 27017:27017 mongo:latest")
            
            self._connected = False
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error connecting to MongoDB: {e}")
            self._connected = False
            return False
    
    def _initialize_collections(self):
        """Initialize collections with proper indexes."""
        try:
            # Admin users collection
            admin_coll = self.db[self.COLLECTIONS['admin_users']]
            admin_coll.create_index('email', unique=True)
            admin_coll.create_index('created_at')
            
            # Chat history collection
            chat_coll = self.db[self.COLLECTIONS['chat_history']]
            chat_coll.create_index('user_id')
            chat_coll.create_index('timestamp')
            chat_coll.create_index('session_id')
            
            # User sessions collection
            sessions_coll = self.db[self.COLLECTIONS['user_sessions']]
            sessions_coll.create_index('session_id', unique=True)
            sessions_coll.create_index('user_id')
            sessions_coll.create_index('created_at')
            
            # Visitor predictions collection
            pred_coll = self.db[self.COLLECTIONS['visitor_predictions']]
            pred_coll.create_index('date')
            pred_coll.create_index('predicted_visitors')
            
            # Weather data collection
            weather_coll = self.db[self.COLLECTIONS['weather_data']]
            weather_coll.create_index('date')
            weather_coll.create_index('temperature')
            
            # System logs collection
            logs_coll = self.db[self.COLLECTIONS['system_logs']]
            logs_coll.create_index('timestamp')
            logs_coll.create_index('level')
            
            # Analytics collection
            analytics_coll = self.db[self.COLLECTIONS['analytics']]
            analytics_coll.create_index('date')
            analytics_coll.create_index('event_type')
            
            logger.info("📑 Collections initialized with indexes")
            
        except Exception as e:
            logger.warning(f"⚠️  Error initializing collections: {e}")
    
    def is_connected(self) -> bool:
        """Check if MongoDB is connected."""
        return self._connected
    
    def get_collection(self, collection_name: str):
        """
        Get a specific collection.
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            MongoDB collection object
        """
        if not self._connected or self.db is None:
            logger.error("Database not connected!")
            return None
        
        return self.db[collection_name]
    
    def disconnect(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            self._connected = False
            logger.info("🔌 Disconnected from MongoDB Atlas")


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

# Create global MongoDB configuration instance
db_config = MongoDBConfig()


# ============================================================================
# DATABASE OPERATIONS
# ============================================================================

class DatabaseOperations:
    """Handle all database operations."""
    
    @staticmethod
    def save_chat_message(user_id: str, session_id: str, message: str, 
                         response: str, query_type: str) -> bool:
        """Save chat message and response to database."""
        try:
            chat_coll = db_config.get_collection(db_config.COLLECTIONS['chat_history'])
            if chat_coll is None:
                return False
            
            chat_doc = {
                'user_id': user_id,
                'session_id': session_id,
                'user_message': message,
                'bot_response': response,
                'query_type': query_type,
                'timestamp': datetime.utcnow(),
                'message_length': len(message),
                'response_length': len(response)
            }
            
            result = chat_coll.insert_one(chat_doc)
            logger.info(f"💬 Saved chat message: {result.inserted_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error saving chat message: {e}")
            return False
    
    @staticmethod
    def save_visitor_prediction(date: str, predicted_visitors: int, 
                               confidence: float, crowding_level: str) -> bool:
        """Save visitor prediction to database."""
        try:
            pred_coll = db_config.get_collection(db_config.COLLECTIONS['visitor_predictions'])
            if pred_coll is None:
                return False
            
            pred_doc = {
                'date': date,
                'predicted_visitors': predicted_visitors,
                'confidence': confidence,
                'crowding_level': crowding_level,
                'saved_at': datetime.utcnow()
            }
            
            result = pred_coll.insert_one(pred_doc)
            logger.info(f"📊 Saved prediction for {date}: {result.inserted_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error saving prediction: {e}")
            return False
    
    @staticmethod
    def save_weather_data(date: str, temperature: float, rainfall: float, 
                         wind_speed: float, condition: str) -> bool:
        """Save weather data to database."""
        try:
            weather_coll = db_config.get_collection(db_config.COLLECTIONS['weather_data'])
            if weather_coll is None:
                return False
            
            weather_doc = {
                'date': date,
                'temperature': temperature,
                'rainfall': rainfall,
                'wind_speed': wind_speed,
                'condition': condition,
                'saved_at': datetime.utcnow()
            }
            
            result = weather_coll.insert_one(weather_doc)
            logger.info(f"🌡️  Saved weather data for {date}: {result.inserted_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error saving weather data: {e}")
            return False
    
    @staticmethod
    def save_user_session(user_id: str, session_id: str, location: str = None) -> bool:
        """Save user session information."""
        try:
            sessions_coll = db_config.get_collection(db_config.COLLECTIONS['user_sessions'])
            if sessions_coll is None:
                return False
            
            session_doc = {
                'user_id': user_id,
                'session_id': session_id,
                'location': location,
                'created_at': datetime.utcnow(),
                'last_activity': datetime.utcnow(),
                'messages_count': 0
            }
            
            result = sessions_coll.insert_one(session_doc)
            logger.info(f"👤 Saved user session: {result.inserted_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error saving session: {e}")
            return False
    
    @staticmethod
    def log_system_event(level: str, message: str, data: Dict = None) -> bool:
        """Log system event to database."""
        try:
            logs_coll = db_config.get_collection(db_config.COLLECTIONS['system_logs'])
            if logs_coll is None:
                return False
            
            log_doc = {
                'level': level,
                'message': message,
                'data': data,
                'timestamp': datetime.utcnow()
            }
            
            result = logs_coll.insert_one(log_doc)
            logger.info(f"📝 Logged system event: {result.inserted_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error logging event: {e}")
            return False
    
    @staticmethod
    def get_recent_chat_history(user_id: str, limit: int = 10) -> list:
        """Retrieve recent chat history for a user."""
        try:
            chat_coll = db_config.get_collection(db_config.COLLECTIONS['chat_history'])
            if chat_coll is None:
                return []
            
            messages = list(chat_coll.find({'user_id': user_id})
                          .sort('timestamp', -1)
                          .limit(limit))
            
            # Convert ObjectId to string for JSON serialization
            for msg in messages:
                msg['_id'] = str(msg['_id'])
            
            return messages
            
        except Exception as e:
            logger.error(f"❌ Error retrieving chat history: {e}")
            return []
    
    @staticmethod
    def record_analytics(event_type: str, data: Dict = None) -> bool:
        """Record analytics event."""
        try:
            analytics_coll = db_config.get_collection(db_config.COLLECTIONS['analytics'])
            if analytics_coll is None:
                return False
            
            analytics_doc = {
                'event_type': event_type,
                'data': data,
                'date': datetime.utcnow().date().isoformat(),
                'timestamp': datetime.utcnow()
            }
            
            result = analytics_coll.insert_one(analytics_doc)
            logger.info(f"📈 Recorded analytics: {result.inserted_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error recording analytics: {e}")
            return False


# ============================================================================
# INITIALIZATION FUNCTION
# ============================================================================

def initialize_database() -> bool:
    """Initialize database connection at application startup."""
    logger.info("=" * 60)
    logger.info("🚀 Initializing MongoDB Connection")
    logger.info("=" * 60)
    
    success = db_config.connect()
    
    if success:
        logger.info("✅ Database initialization complete!")
        logger.info(f"📍 Using MongoDB URI from environment variables")
        logger.info(f"📚 Database: {db_config.DATABASE_NAME}")
    else:
        logger.error("❌ Database initialization failed!")
        logger.error("⚠️  Application will continue without database persistence")
    
    logger.info("=" * 60)
    
    return success


if __name__ == "__main__":
    # Test database connection
    print("\n🧪 Testing MongoDB Connection...\n")
    
    if initialize_database():
        print("\n✅ MongoDB connection successful!")
        
        # Test saving data
        print("\n📝 Testing database operations...")
        
        # Save a test chat message
        DatabaseOperations.save_chat_message(
            user_id="test_user_001",
            session_id="session_001",
            message="What's the crowd today?",
            response="Expected 250 visitors today with low crowds!",
            query_type="crowd"
        )
        
        # Save a test prediction
        DatabaseOperations.save_visitor_prediction(
            date="2026-03-15",
            predicted_visitors=350,
            confidence=0.92,
            crowding_level="Moderate"
        )
        
        # Save test weather data
        DatabaseOperations.save_weather_data(
            date="2026-03-15",
            temperature=28.5,
            rainfall=2.3,
            wind_speed=4.2,
            condition="Partly Cloudy"
        )
        
        print("\n✅ All database operations successful!")
        
        # Disconnect
        db_config.disconnect()
    else:
        print("\n❌ Failed to connect to MongoDB")
        print("Make sure your .env file has the correct MONGODB_URI")

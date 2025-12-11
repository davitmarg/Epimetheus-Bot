"""
Database connection utilities for Redis, MongoDB, and ChromaDB

This module provides centralized database connection management
that can be used across multiple services.
"""

import os
import redis
import chromadb
from chromadb import HttpClient
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from dotenv import load_dotenv

load_dotenv()

# Redis configuration
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_DB = int(os.environ.get("REDIS_DB", 0))

# Redis key constants
REDIS_QUEUE_KEY = "epimetheus:updater_queue"  # Queue for batches to be processed

# MongoDB configuration
MONGODB_HOST = os.environ.get("MONGODB_HOST", "localhost")
MONGODB_PORT = int(os.environ.get("MONGODB_PORT", 27017))
MONGODB_DATABASE = os.environ.get("MONGODB_DATABASE", "epimetheus")
MONGODB_USERNAME = os.environ.get("MONGODB_USERNAME")
MONGODB_PASSWORD = os.environ.get("MONGODB_PASSWORD")
MONGODB_URI = os.environ.get("MONGODB_URI")

# ChromaDB configuration
CHROMA_DB_PATH = os.environ.get("CHROMA_DB_PATH", "./chroma_db")
CHROMA_HOST = os.environ.get("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.environ.get("CHROMA_PORT", 8000))
CHROMA_USE_HTTP = os.environ.get("CHROMA_USE_HTTP", "false").lower() == "true"

# Global connection instances
_redis_client = None
_mongodb_client = None
_mongodb_db = None
_chroma_client = None
_chroma_collection = None


def get_redis_client() -> redis.Redis:
    """Get or create Redis client instance"""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True
        )
        # Test connection
        try:
            _redis_client.ping()
            print(f"✓ Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
        except redis.ConnectionError as e:
            print(f"✗ Warning: Could not connect to Redis: {e}")
    return _redis_client


def get_mongodb_client() -> MongoClient:
    """Get or create MongoDB client instance"""
    global _mongodb_client
    if _mongodb_client is None:
        try:
            # Build connection URI with authentication if username/password provided
            if MONGODB_URI:
                connection_uri = MONGODB_URI
                print('Using MongoDB connection URI: ', connection_uri)
                _mongodb_client = MongoClient(
                    connection_uri,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=5000
                )
            elif MONGODB_USERNAME and MONGODB_PASSWORD:
                # Use MongoDB connection string format: mongodb://username:password@host:port/database
                connection_uri = f"mongodb://{MONGODB_USERNAME}:{MONGODB_PASSWORD}@{MONGODB_HOST}:{MONGODB_PORT}/{MONGODB_DATABASE}?authSource=admin"
                print('Using MongoDB connection string: ', connection_uri)
                _mongodb_client = MongoClient(
                    connection_uri,
                    serverSelectionTimeoutMS=5000
                )
            else:
                # Connect without authentication
                _mongodb_client = MongoClient(
                    host=MONGODB_HOST,
                    port=MONGODB_PORT,
                    serverSelectionTimeoutMS=5000
                )
            # Test connection
            _mongodb_client.admin.command('ping')
            auth_info = f" as {MONGODB_USERNAME}" if MONGODB_USERNAME else ""
            print(f"✓ Connected to MongoDB at {MONGODB_HOST}:{MONGODB_PORT}{auth_info}")
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            print(f"✗ Warning: Could not connect to MongoDB: {e}")
            _mongodb_client = None
    return _mongodb_client


def get_mongodb_db():
    """Get or create MongoDB database instance"""
    global _mongodb_db
    if _mongodb_db is None:
        client = get_mongodb_client()
        if client:
            _mongodb_db = client[MONGODB_DATABASE]
        else:
            return None
    return _mongodb_db


def get_chroma_client():
    """Get or create ChromaDB client instance"""
    global _chroma_client
    if _chroma_client is None:
        try:
            if CHROMA_USE_HTTP:
                _chroma_client = HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
            else:
                _chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
            print(f"✓ Connected to ChromaDB")
        except Exception as e:
            print(f"✗ Warning: Could not initialize ChromaDB: {e}")
            _chroma_client = None
    return _chroma_client


def get_chroma_collection(collection_name: str = "document_chunks"):
    """Get or create ChromaDB collection instance"""
    global _chroma_collection
    if _chroma_collection is None:
        client = get_chroma_client()
        if client:
            try:
                _chroma_collection = client.get_or_create_collection(
                    name=collection_name,
                    metadata={"hnsw:space": "cosine"}
                )
            except Exception as e:
                print(f"✗ Warning: Could not get/create ChromaDB collection: {e}")
                _chroma_collection = None
    return _chroma_collection


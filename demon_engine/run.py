# 🔥 DEMON ENGINE STARTUP SCRIPT - Ready to Launch the Legendary System
"""
Launch the Demon Engine with all the bells and whistles
Sets up environment, initializes database, and starts the API
"""

import asyncio
import os
import sys
import logging
from pathlib import Path

# Add the parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from demon_engine.api import app
from demon_engine.core import DemonEngineBrain
from demon_engine.schemas import DemonEngineConfig
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_environment():
    """🔍 Check that all required environment variables are set"""
    required_vars = [
        'MONGODB_URI',
        'OPENAI_API_KEY'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        logger.info("💡 Set them using:")
        for var in missing_vars:
            if var == 'MONGODB_URI':
                logger.info(f"   export {var}='mongodb+srv://username:password@cluster.mongodb.net/dbname'")
            elif var == 'OPENAI_API_KEY':
                logger.info(f"   export {var}='sk-your-openai-api-key-here'")
            else:
                logger.info(f"   export {var}='your-value-here'")
        sys.exit(1)
    
    logger.info("✅ Environment variables are set")

def print_banner():
    """🎭 Print the epic Demon Engine banner"""
    banner = """
    🧙‍♂️ ============================================= 🧙‍♂️
    
         THE LEGENDARY DEMON ENGINE
         
         Where 230 prompt techniques become
         enterprise-grade AI orchestration magic
         
         🔥 Ready to make Elon cry 🔥
    
    🧙‍♂️ ============================================= 🧙‍♂️
    """
    print(banner)

async def main():
    """🚀 Main startup function"""
    print_banner()
    
    # Check environment
    check_environment()
    
    # Get configuration
    host = os.getenv('API_HOST', '0.0.0.0')
    port = int(os.getenv('API_PORT', 8000))
    reload = os.getenv('API_RELOAD', 'true').lower() == 'true'
    
    logger.info(f"🚀 Starting Demon Engine API on {host}:{port}")
    logger.info(f"📚 API Documentation: http://{host if host != '0.0.0.0' else 'localhost'}:{port}/docs")
    logger.info(f"🏥 Health Check: http://{host if host != '0.0.0.0' else 'localhost'}:{port}/health")
    
    # Start the server
    uvicorn.run(
        "demon_engine.api:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
        access_log=True
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Demon Engine shutting down gracefully...")
    except Exception as e:
        logger.error(f"💥 Demon Engine startup failed: {e}")
        sys.exit(1)

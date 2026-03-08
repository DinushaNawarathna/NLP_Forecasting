#!/usr/bin/env python3
"""
OpenWeatherMap Integration Setup Script

This script helps set up the OpenWeatherMap integration and verifies the API key.
"""

import os
import sys
import subprocess

def install_requirements():
    """Install required packages."""
    print("📦 Installing requirements...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Requirements installed successfully")
        return True
    except Exception as e:
        print(f"❌ Error installing requirements: {e}")
        return False


def setup_api_key():
    """Help user set up OpenWeatherMap API key."""
    print("\n🔑 OpenWeatherMap API Key Setup")
    print("-" * 50)
    
    api_key = os.getenv('OPENWEATHER_API_KEY')
    
    if api_key and api_key != 'YOUR_API_KEY_HERE':
        print(f"✅ API Key found: {api_key[:10]}...")
        return True
    
    print("\n📍 Steps to get your API key:")
    print("1. Visit: https://openweathermap.org/api")
    print("2. Sign up for a free account")
    print("3. Go to API keys section")
    print("4. Copy your API key")
    
    user_input = input("\n➡️  Enter your OpenWeatherMap API key: ").strip()
    
    if user_input:
        # Try to set it for current session
        os.environ['OPENWEATHER_API_KEY'] = user_input
        
        # Show how to persist it
        print("\n✅ API key set for current session")
        print("\nTo persist the API key, add to your shell profile (~/.bashrc, ~/.zshrc, etc):")
        print(f'export OPENWEATHER_API_KEY="{user_input}"')
        
        return True
    else:
        print("⚠️  No API key provided. OpenWeatherMap endpoints will not work.")
        return False


def test_api_connection():
    """Test the OpenWeatherMap API connection."""
    print("\n🌐 Testing OpenWeatherMap API Connection...")
    print("-" * 50)
    
    api_key = os.getenv('OPENWEATHER_API_KEY')
    
    if not api_key or api_key == 'YOUR_API_KEY_HERE':
        print("⚠️  No API key set. Skipping connection test.")
        return False
    
    try:
        import requests
        
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            'lat': 7.9570,
            'lon': 80.7595,
            'units': 'metric',
            'appid': api_key
        }
        
        response = requests.get(url, params=params, timeout=5)
        
        if response.status_code == 200:
            print("✅ API Connection Successful")
            data = response.json()
            print(f"   Location: {data['name']}")
            print(f"   Temperature: {data['main']['temp']}°C")
            print(f"   Condition: {data['weather'][0]['main']}")
            return True
        elif response.status_code == 401:
            print("❌ Invalid API Key")
            return False
        else:
            print(f"❌ Error: {response.status_code}")
            return False
    except ImportError:
        print("⚠️  'requests' library not installed")
        return False
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return False


def verify_setup():
    """Verify the complete setup."""
    print("\n✨ Verifying OpenWeatherMap Integration Setup")
    print("=" * 50)
    
    # Check Python version
    print(f"✅ Python {sys.version.split()[0]}")
    
    # Check API key
    api_key = os.getenv('OPENWEATHER_API_KEY')
    if api_key and api_key != 'YOUR_API_KEY_HERE':
        print(f"✅ API Key configured")
    else:
        print(f"⚠️  API Key NOT configured")
    
    # Check module imports
    try:
        import requests
        print(f"✅ requests {requests.__version__}")
    except:
        print("⚠️  requests not installed")
    
    try:
        from openweather_integration import OpenWeatherMapClient
        print("✅ OpenWeather integration module loaded")
    except:
        print("⚠️  OpenWeather integration module not found")
    
    print("\n" + "=" * 50)
    print("Setup verification complete!")


def main():
    """Main setup workflow."""
    print("\n🚀 OpenWeatherMap Integration Setup")
    print("=" * 50)
    
    # Step 1: Install requirements
    if not install_requirements():
        print("\n⚠️  Please install requirements manually:")
        print("   pip install -r requirements.txt")
        return
    
    # Step 2: Setup API key
    setup_api_key()
    
    # Step 3: Test API connection
    test_api_connection()
    
    # Step 4: Verify setup
    verify_setup()
    
    print("\n✅ Setup complete!")
    print("\nNext steps:")
    print("1. Set OPENWEATHER_API_KEY environment variable")
    print("2. Run: python main.py")
    print("3. Test endpoints:")
    print("   - GET http://localhost:8000/weather/current")
    print("   - GET http://localhost:8000/weather/hourly?hours=48")
    print("   - GET http://localhost:8000/weather/daily?days=5")
    print("\n📖 See OPENWEATHER_INTEGRATION.md for more details")


if __name__ == "__main__":
    main()

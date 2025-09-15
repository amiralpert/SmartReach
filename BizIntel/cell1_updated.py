# Cell 1: GitHub Setup and Simplified Configuration

# Install required packages first
!pip install edgartools transformers torch accelerate huggingface_hub requests beautifulsoup4 'lxml[html_clean]' uuid numpy newspaper3k --quiet
!pip install -U bitsandbytes --quiet

print("🔧 Installing additional packages...")
!pip install psycopg2-binary --quiet
!pip install accelerate --quiet

print("✅ All packages installed successfully")

# ============================================================================
# GITHUB SETUP AND PATH CONFIGURATION
# ============================================================================

print("\n🔄 Setting up GitHub repository...")

# GitHub configuration
user_secrets = UserSecretsClient()
GITHUB_TOKEN = user_secrets.get_secret("GITHUB_TOKEN")
REPO_URL = f"https://{GITHUB_TOKEN}@github.com/amiralpert/SmartReach.git"
LOCAL_PATH = "/kaggle/working/SmartReach"

# Clone or update the repository
if os.path.exists(LOCAL_PATH):
    print("   📂 Repository exists, pulling latest changes...")
    !cd {LOCAL_PATH} && git pull origin main > /dev/null 2>&1
    print("   ✅ Repository updated")
else:
    print("   📥 Cloning repository...")
    !git clone {REPO_URL} {LOCAL_PATH} > /dev/null 2>&1
    print("   ✅ Repository cloned")

# Add paths for module imports
bizintel_path = f'{LOCAL_PATH}/BizIntel'
scripts_path = f'{LOCAL_PATH}/BizIntel/Scripts'

if bizintel_path not in sys.path:
    sys.path.insert(0, bizintel_path)
if scripts_path not in sys.path:
    sys.path.insert(0, scripts_path)

print(f"   ✅ Added {bizintel_path} to Python path")
print(f"   ✅ Added {scripts_path} to Python path")

# ============================================================================
# IMPORT MODULAR COMPONENTS
# ============================================================================

# Import from our modular EntityExtractionEngine
from EntityExtractionEngine import (
    SEC_FILINGS_PROMPT,
    SizeLimitedLRUCache,
    log_error,
    log_warning, 
    log_info,
    get_db_connection
)

print("✅ Imported modular EntityExtractionEngine components")

# ============================================================================
# CENTRALIZED CONFIGURATION
# ============================================================================

# Neon database configuration (from secrets)
NEON_CONFIG = {
    'host': user_secrets.get_secret("NEON_HOST"),
    'database': user_secrets.get_secret("NEON_DATABASE"), 
    'user': user_secrets.get_secret("NEON_USER"),
    'password': user_secrets.get_secret("NEON_PASSWORD"),
    'port': 5432,
    'sslmode': 'require'
}

# Complete centralized configuration
CONFIG = {
    'github': {
        'token': user_secrets.get_secret("GITHUB_TOKEN"),
        'repo_url': 'https://github.com/amiralpert/SmartReach.git',
        'local_path': '/kaggle/working/SmartReach',
        'branch': 'main'
    },
    'database': {
        'connection_pool_size': 5,
        'max_connections': 10,
        'connection_timeout': 30,
        'query_timeout': 60,
        'retry_attempts': 3,
        'batch_size': 100
    },
    'models': {
        'confidence_threshold': 0.75,
        'warm_up_enabled': True,
        'warm_up_text': 'Test entity extraction with biotechnology company.',
        'device_preference': 'auto',  # 'auto', 'cuda', 'cpu'
        'model_timeout': 30
    },
    'cache': {
        'enabled': True,
        'max_size_mb': 512,
        'ttl_hours': 24,
        'cleanup_interval': 3600
    },
    'processing': {
        'filing_batch_size': 3,
        'entity_batch_size': 50,
        'max_section_length': 50000,
        'enable_parallel': True,
        'max_workers': 4,
        'section_validation': True,
        'filing_query_limit': 10,
        'enable_relationships': True,
        'relationship_batch_size': 15,
        'context_window_chars': 400
    },
    'llama': {
        'enabled': True,
        'model_name': 'meta-llama/Llama-3.1-8B-Instruct',
        'batch_size': 15,
        'max_new_tokens': 50,
        'context_window': 400,
        'temperature': 0.3,
        'entity_context_window': 400,
        'test_max_tokens': 50,
        'min_confidence_filter': 0.8,
        'timeout_seconds': 30,
        'SEC_FilingsPrompt': SEC_FILINGS_PROMPT,  # Now imported from module
    },
    'edgar': {
        'identity': 'SmartReach BizIntel amir.alpert@gmail.com',
        'rate_limit_delay': 0.1,
        'max_retries': 3,
        'timeout_seconds': 30
    }
}

# Error checking for required secrets
required_secrets = ['NEON_HOST', 'NEON_DATABASE', 'NEON_USER', 'NEON_PASSWORD', 'GITHUB_TOKEN']
missing_secrets = []

for secret in required_secrets:
    try:
        value = user_secrets.get_secret(secret)
        if not value:
            missing_secrets.append(secret)
    except Exception as e:
        missing_secrets.append(secret)

if missing_secrets:
    print(f"❌ Missing required secrets: {missing_secrets}")
    print("   Please add these secrets in Kaggle's Settings > Secrets")
    raise ValueError("Missing required secrets")

print("✅ All required secrets validated")

# Configuration validation and display
print("\n🔧 Configuration Summary:")
print(f"   • Database: {NEON_CONFIG['host']} / {NEON_CONFIG['database']}")
print(f"   • Models: {len(['biobert', 'bert', 'roberta', 'finbert'])} NER models + Llama 3.1-8B")
print(f"   • Processing: {CONFIG['processing']['filing_batch_size']} filings/batch")
print(f"   • Cache: {CONFIG['cache']['max_size_mb']}MB limit")
print(f"   • Relationships: {'Enabled' if CONFIG['processing']['enable_relationships'] else 'Disabled'}")

# ============================================================================
# INITIALIZE COMPONENTS
# ============================================================================

# Initialize global cache for section extraction using imported class
SECTION_CACHE = SizeLimitedLRUCache(max_size_mb=CONFIG['cache']['max_size_mb'])

# Create database connection function with NEON_CONFIG
def get_db_connection_configured():
    """Database connection using our configuration"""
    return get_db_connection(NEON_CONFIG)

# ============================================================================
# MODULE CLEARING AND EDGARTOOLS SETUP
# ============================================================================

print("\n🧹 Clearing modules and setting up EdgarTools...")

# Clear any existing modules to ensure fresh imports
modules_to_clear = [mod for mod in sys.modules.keys() if 'SmartReach' in mod]
for module in modules_to_clear:
    del sys.modules[module]

# Configure EdgarTools identity
set_identity(CONFIG['edgar']['identity'])
print(f"   ✅ EdgarTools identity set: {CONFIG['edgar']['identity']}")

# ============================================================================
# FINAL INITIALIZATION MESSAGES
# ============================================================================

print("\n" + "="*80)
print("🎉 CELL 1 INITIALIZATION COMPLETE")
print("="*80)

print(f"✅ GitHub repository ready at: {LOCAL_PATH}")
print(f"✅ Database connection configured: {NEON_CONFIG['host']}")
print(f"✅ Configuration loaded with {len(CONFIG)} main sections")
print(f"✅ Modular components imported from EntityExtractionEngine")
print(f"✅ Size-limited cache initialized: {CONFIG['cache']['max_size_mb']}MB limit")
print(f"✅ EdgarTools identity configured")
print(f"✅ Logging functions available: log_error, log_warning, log_info")
print(f"✅ Database context manager available: get_db_connection_configured()")
print(f"✅ Llama 3.1-8B relationship extraction prompt configured")

print(f"\n🚀 Ready to proceed to Cell 2 for EdgarTools section extraction!")
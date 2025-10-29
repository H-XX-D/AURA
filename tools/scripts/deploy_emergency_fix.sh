#!/bin/bash
# Emergency Deployment Script - Week 1 Fix
# Deploys validated emergency configuration to stop compression expansion

set -e  # Exit on error

echo "=================================================================================="
echo "AURA Emergency Configuration Deployment"
echo "=================================================================================="
echo ""
echo "This script will deploy the Week 1 emergency fix to address:"
echo "  - Compression expansion issue (0.70x ratio)"
echo "  - Low template hit rate (12%)"
echo "  - High bandwidth waste (-356.9%)"
echo ""
echo "Expected improvements:"
echo "  - Compression ratio: 1.69x (46% improvement)"
echo "  - Bandwidth savings: 40.8% (192% improvement)"
echo "  - Template hit rate: 72.0% (500% improvement)"
echo ""
read -p "Continue with deployment? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled."
    exit 1
fi

echo ""
echo "Step 1: Backing up current configuration..."
BACKUP_DIR="./backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

if [ -f "config/production_config.py" ]; then
    cp config/production_config.py "$BACKUP_DIR/"
    echo "  ✓ Backed up production_config.py"
fi

if [ -f "template_store.json" ]; then
    cp template_store.json "$BACKUP_DIR/"
    echo "  ✓ Backed up template_store.json"
fi

echo ""
echo "Step 2: Deploying expanded template store..."
cp template_store_expanded.json template_store.json
echo "  ✓ Deployed template_store_expanded.json → template_store.json"

echo ""
echo "Step 3: Updating configuration..."

# Create production config if it doesn't exist
if [ ! -f "config/production_config.py" ]; then
    cat > config/production_config.py << 'EOF'
#!/usr/bin/env python3
"""
Production Configuration - Emergency Week 1 Fix
Deployed: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
"""

PRODUCTION_COMPRESSION_CONFIG = {
    # CRITICAL: Disable BRIO to eliminate header overhead
    'enable_aura': False,

    # Use proven methods (binary_semantic + brotli)
    'min_compression_size': 30,

    # Template configuration
    'template_store_path': 'template_store.json',
    'template_cache_size': 128,

    # Audit logging (enable with proper directory)
    'enable_audit_logging': True,
    'audit_log_directory': '/var/log/aura',

    # Binary semantic settings
    'binary_advantage_threshold': 1.1,
}


def get_compressor(**overrides):
    """Create production compressor with emergency configuration"""
    from aura_compression import ProductionHybridCompressor

    config = PRODUCTION_COMPRESSION_CONFIG.copy()
    config.update(overrides)

    return ProductionHybridCompressor(**config)
EOF
    echo "  ✓ Created config/production_config.py"
else
    echo "  ⚠ config/production_config.py already exists"
    echo "    Please manually update to use emergency configuration"
    echo "    See: config/emergency_config.py for reference"
fi

echo ""
echo "Step 4: Validating deployment..."
python3 << 'EOF'
import sys
sys.path.insert(0, '.')

from config.emergency_config import get_compressor

# Test compression
compressor = get_compressor()
test_message = "Processing request..."
compressed, method, metadata = compressor.compress(test_message)

print(f"  Compression ratio: {metadata['ratio']:.2f}x")
print(f"  Method: {metadata['method']}")
print(f"  Template hit: {metadata.get('template_id') is not None}")

if metadata['ratio'] >= 1.5 and metadata.get('template_id') is not None:
    print("  ✓ Validation PASSED")
    sys.exit(0)
else:
    print("  ✗ Validation FAILED")
    sys.exit(1)
EOF

VALIDATION_STATUS=$?

if [ $VALIDATION_STATUS -eq 0 ]; then
    echo ""
    echo "=================================================================================="
    echo "Deployment Complete ✓"
    echo "=================================================================================="
    echo ""
    echo "Next Steps:"
    echo "  1. Monitor metrics for 48 hours"
    echo "  2. Verify compression ratio > 1.5x"
    echo "  3. Verify bandwidth savings > 33%"
    echo "  4. Verify expansion rate < 10%"
    echo ""
    echo "Monitoring:"
    echo "  - Check Grafana dashboard: http://grafana/d/aura"
    echo "  - Check health endpoint: curl localhost:8000/health/detailed"
    echo "  - Check audit logs: tail -f /var/log/aura/compression.log"
    echo ""
    echo "Rollback (if needed):"
    echo "  cp $BACKUP_DIR/production_config.py config/"
    echo "  cp $BACKUP_DIR/template_store.json ."
    echo ""
    echo "Documentation:"
    echo "  - docs/WEEK1_DEPLOYMENT_RESULTS.md"
    echo "  - docs/STACK_TUNING_PLAN.md"
    echo ""
else
    echo ""
    echo "=================================================================================="
    echo "Deployment Failed ✗"
    echo "=================================================================================="
    echo ""
    echo "Validation failed. Rolling back..."

    if [ -f "$BACKUP_DIR/template_store.json" ]; then
        cp "$BACKUP_DIR/template_store.json" .
        echo "  ✓ Restored template_store.json"
    fi

    echo ""
    echo "Please investigate the issue and try again."
    exit 1
fi

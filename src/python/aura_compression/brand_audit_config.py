#!/usr/bin/env python3
"""
Brand-Specific AURA Audit Configurations

Enterprise customers can customize audit behavior to match their brand:
- Custom audit database paths
- Brand-specific retention policies
- White-label reporting
- Custom compliance rules (GDPR, HIPAA, SOC2, etc.)
- Performance tuning per brand requirements

Usage:
    config = BrandAuditConfig.for_brand("acme-corp")
    auditor = config.create_auditor()
    compressor = config.create_auditable_compressor()
"""
import json
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import timedelta

from aura_compression.audit_layer import CompressionAuditor
from aura_compression.auditable_compressor import (
    AuditableCompressor,
    AuditableHeavy,
    AuditableAICompressor
)
from aura_compression.compressor import ProductionHybridCompressor


class ComplianceProfile:
    """Compliance profile for different regulatory requirements."""

    GDPR = {
        'name': 'GDPR (General Data Protection Regulation)',
        'retention_days': 90,  # 90 days default
        'requires_encryption': True,
        'requires_data_lineage': True,
        'requires_audit_chain': True,
        'right_to_be_forgotten': True,
        'data_portability': True
    }

    HIPAA = {
        'name': 'HIPAA (Health Insurance Portability and Accountability Act)',
        'retention_days': 2555,  # 7 years
        'requires_encryption': True,
        'requires_data_lineage': True,
        'requires_audit_chain': True,
        'minimum_security_level': 'SECURITY',
        'requires_access_logs': True
    }

    SOC2 = {
        'name': 'SOC 2 Type II',
        'retention_days': 365,  # 1 year minimum
        'requires_encryption': True,
        'requires_data_lineage': True,
        'requires_audit_chain': True,
        'continuous_monitoring': True,
        'incident_tracking': True
    }

    PCI_DSS = {
        'name': 'PCI DSS (Payment Card Industry Data Security Standard)',
        'retention_days': 365,  # 1 year
        'requires_encryption': True,
        'requires_data_lineage': True,
        'requires_audit_chain': True,
        'requires_quarterly_review': True,
        'cardholder_data_tracking': True
    }

    CCPA = {
        'name': 'CCPA (California Consumer Privacy Act)',
        'retention_days': 730,  # 2 years
        'requires_encryption': False,  # Recommended but not required
        'requires_data_lineage': True,
        'requires_audit_chain': True,
        'right_to_be_forgotten': True,
        'data_sale_tracking': True
    }


class PerformanceProfile:
    """Performance profiles for different use cases."""

    LOW_LATENCY = {
        'name': 'Low Latency (Real-time streaming)',
        'prefer_speed': True,
        'compression_level': 1,  # Fastest
        'enable_aggressive_ai': False,
        'large_file_threshold': 10240,  # 10KB - higher threshold
        'priority': 'latency'
    }

    BALANCED = {
        'name': 'Balanced (Default)',
        'prefer_speed': False,
        'compression_level': 6,  # Default
        'enable_aggressive_ai': False,
        'large_file_threshold': 2048,  # 2KB
        'priority': 'balanced'
    }

    HIGH_COMPRESSION = {
        'name': 'High Compression (Bandwidth savings)',
        'prefer_speed': False,
        'compression_level': 9,  # Maximum
        'enable_aggressive_ai': True,
        'large_file_threshold': 1024,  # 1KB - lower threshold
        'priority': 'compression_ratio'
    }


class BrandAuditConfig:
    """
    Brand-specific AURA audit configuration.

    Each enterprise customer gets their own configuration:
    - Isolated audit database
    - Custom retention policies
    - Brand-specific compliance requirements
    - Performance tuning
    """

    def __init__(self,
                 brand_name: str,
                 audit_db_path: Optional[str] = None,
                 compliance_profiles: Optional[list] = None,
                 performance_profile: Optional[Dict] = None,
                 custom_config: Optional[Dict] = None):
        """
        Initialize brand-specific configuration.

        Args:
            brand_name: Unique brand identifier (e.g., "acme-corp")
            audit_db_path: Custom audit database path
            compliance_profiles: List of compliance profiles to apply
            performance_profile: Performance optimization profile
            custom_config: Additional custom configuration
        """
        self.brand_name = brand_name
        self.audit_db_path = audit_db_path or f"audit/{brand_name}/compression_audit.db"
        self.compliance_profiles = compliance_profiles or []
        self.performance_profile = performance_profile or PerformanceProfile.BALANCED
        self.custom_config = custom_config or {}

        # Compute effective configuration
        self._compute_effective_config()

    def _compute_effective_config(self):
        """Compute effective configuration from all profiles."""
        # Start with defaults
        self.config = {
            'retention_days': 90,
            'requires_encryption': False,
            'requires_audit_chain': True,
            'requires_data_lineage': True,
            'prefer_speed': False,
            'compression_level': 6,
            'enable_aggressive_ai': False,
            'large_file_threshold': 2048
        }

        # Apply each compliance profile (most restrictive wins)
        for profile_name in self.compliance_profiles:
            if hasattr(ComplianceProfile, profile_name):
                profile = getattr(ComplianceProfile, profile_name)

                # Retention: use longest
                if 'retention_days' in profile:
                    self.config['retention_days'] = max(
                        self.config['retention_days'],
                        profile['retention_days']
                    )

                # Boolean requirements: any True makes it True
                for key in ['requires_encryption', 'requires_audit_chain', 'requires_data_lineage']:
                    if profile.get(key):
                        self.config[key] = True

        # Apply performance profile
        self.config.update({
            'prefer_speed': self.performance_profile.get('prefer_speed', False),
            'compression_level': self.performance_profile.get('compression_level', 6),
            'enable_aggressive_ai': self.performance_profile.get('enable_aggressive_ai', False),
            'large_file_threshold': self.performance_profile.get('large_file_threshold', 2048)
        })

        # Apply custom overrides
        self.config.update(self.custom_config)

    def create_auditor(self) -> CompressionAuditor:
        """Create auditor instance with this configuration."""
        return CompressionAuditor(
            db_path=self.audit_db_path,
            enable_chain=self.config['requires_audit_chain']
        )

    def create_auditable_compressor(self,
                                    compressor_type: str = 'hybrid',
                                    user_id: Optional[str] = None,
                                    session_id: Optional[str] = None,
                                    source_ip: Optional[str] = None) -> Any:
        """
        Create auditable compressor with this configuration.

        Args:
            compressor_type: 'standard', 'hybrid', or 'ai'
            user_id: User identifier
            session_id: Session identifier
            source_ip: Source IP address

        Returns:
            Configured auditable compressor instance
        """
        auditor = self.create_auditor()

        if compressor_type == 'standard':
            return AuditableCompressor(
                compressor=ProductionHybridCompressor(),
                auditor=auditor,
                user_id=user_id,
                session_id=session_id,
                source_ip=source_ip
            )

        elif compressor_type == 'hybrid':
            return AuditableHeavy(
                enable_aura=True,
                prefer_speed=self.config['prefer_speed'],
                auditor=auditor,
                user_id=user_id,
                session_id=session_id,
                source_ip=source_ip
            )

        elif compressor_type == 'ai':
            return AuditableAICompressor(
                aggressive=self.config['enable_aggressive_ai'],
                auditor=auditor,
                user_id=user_id,
                session_id=session_id,
                source_ip=source_ip
            )

        else:
            raise ValueError(f"Unknown compressor type: {compressor_type}")

    def get_retention_policy(self) -> Dict:
        """Get data retention policy for this brand."""
        return {
            'retention_days': self.config['retention_days'],
            'auto_cleanup_enabled': True,
            'compliance_profiles': self.compliance_profiles
        }

    def save(self, path: Optional[str] = None):
        """Save configuration to file."""
        config_path = path or f"audit/{self.brand_name}/config.json"
        Path(config_path).parent.mkdir(parents=True, exist_ok=True)

        data = {
            'brand_name': self.brand_name,
            'audit_db_path': self.audit_db_path,
            'compliance_profiles': self.compliance_profiles,
            'performance_profile': self.performance_profile,
            'custom_config': self.custom_config,
            'effective_config': self.config
        }

        with open(config_path, 'w') as f:
            json.dump(data, f, indent=2)

        return config_path

    @staticmethod
    def load(path: str) -> 'BrandAuditConfig':
        """Load configuration from file."""
        with open(path, 'r') as f:
            data = json.load(f)

        return BrandAuditConfig(
            brand_name=data['brand_name'],
            audit_db_path=data.get('audit_db_path'),
            compliance_profiles=data.get('compliance_profiles'),
            performance_profile=data.get('performance_profile'),
            custom_config=data.get('custom_config')
        )

    @staticmethod
    def for_brand(brand_name: str,
                  compliance: Optional[list] = None,
                  performance: str = 'BALANCED') -> 'BrandAuditConfig':
        """
        Quick factory method for common configurations.

        Args:
            brand_name: Brand identifier
            compliance: List of compliance profile names (e.g., ['GDPR', 'SOC2'])
            performance: Performance profile name ('LOW_LATENCY', 'BALANCED', 'HIGH_COMPRESSION')

        Returns:
            Configured BrandAuditConfig instance
        """
        perf_profile = getattr(PerformanceProfile, performance, PerformanceProfile.BALANCED)

        return BrandAuditConfig(
            brand_name=brand_name,
            compliance_profiles=compliance or [],
            performance_profile=perf_profile
        )


# Pre-configured examples for common use cases
class PredefinedConfigs:
    """Pre-configured brand audit setups for common scenarios."""

    @staticmethod
    def healthcare_provider(brand_name: str) -> BrandAuditConfig:
        """Configuration for healthcare providers (HIPAA compliant)."""
        return BrandAuditConfig.for_brand(
            brand_name=brand_name,
            compliance=['HIPAA'],
            performance='BALANCED'
        )

    @staticmethod
    def financial_services(brand_name: str) -> BrandAuditConfig:
        """Configuration for financial services (PCI DSS + SOC2)."""
        return BrandAuditConfig.for_brand(
            brand_name=brand_name,
            compliance=['PCI_DSS', 'SOC2'],
            performance='BALANCED'
        )

    @staticmethod
    def european_enterprise(brand_name: str) -> BrandAuditConfig:
        """Configuration for European enterprises (GDPR + SOC2)."""
        return BrandAuditConfig.for_brand(
            brand_name=brand_name,
            compliance=['GDPR', 'SOC2'],
            performance='BALANCED'
        )

    @staticmethod
    def real_time_streaming(brand_name: str) -> BrandAuditConfig:
        """Configuration for real-time streaming (low latency priority)."""
        return BrandAuditConfig.for_brand(
            brand_name=brand_name,
            compliance=[],
            performance='LOW_LATENCY'
        )

    @staticmethod
    def high_volume_archival(brand_name: str) -> BrandAuditConfig:
        """Configuration for high-volume archival (maximum compression)."""
        return BrandAuditConfig.for_brand(
            brand_name=brand_name,
            compliance=[],
            performance='HIGH_COMPRESSION'
        )


if __name__ == "__main__":
    print("AURA Brand-Specific Audit Configuration")
    print("=" * 70)
    print("Patent US 19/366,538 - Enterprise-Ready Audit Layer\n")

    # Example 1: Healthcare provider
    print("Example 1: Healthcare Provider (HIPAA Compliant)")
    print("-" * 70)
    config1 = PredefinedConfigs.healthcare_provider("general-hospital")
    print(f"Brand: {config1.brand_name}")
    print(f"Compliance: {config1.compliance_profiles}")
    print(f"Retention: {config1.config['retention_days']} days")
    print(f"Audit Chain: {config1.config['requires_audit_chain']}")
    print(f"Encryption Required: {config1.config['requires_encryption']}")

    # Save configuration
    path1 = config1.save()
    print(f"Configuration saved: {path1}\n")

    # Example 2: Real-time streaming platform
    print("Example 2: Real-time Streaming Platform (Low Latency)")
    print("-" * 70)
    config2 = PredefinedConfigs.real_time_streaming("streamco")
    print(f"Brand: {config2.brand_name}")
    print(f"Performance Priority: {config2.performance_profile['priority']}")
    print(f"Compression Level: {config2.config['compression_level']}")
    print(f"Large File Threshold: {config2.config['large_file_threshold']} bytes")
    print(f"Prefer Speed: {config2.config['prefer_speed']}")

    # Create compressor
    compressor = config2.create_auditable_compressor(
        compressor_type='hybrid',
        user_id='stream_user_123',
        session_id='session_456',
        source_ip='10.0.0.5'
    )
    print(f"Created: {compressor.__class__.__name__}\n")

    # Example 3: European enterprise
    print("Example 3: European Enterprise (GDPR + SOC2)")
    print("-" * 70)
    config3 = PredefinedConfigs.european_enterprise("euro-tech-gmbh")
    print(f"Brand: {config3.brand_name}")
    print(f"Compliance: {config3.compliance_profiles}")
    print(f"Retention: {config3.config['retention_days']} days")
    print(f"Data Lineage: {config3.config['requires_data_lineage']}")

    retention = config3.get_retention_policy()
    print(f"Retention Policy: {json.dumps(retention, indent=2)}\n")

    print("=" * 70)
    print("Summary:")
    print("  ✓ Brand-specific isolated audit databases")
    print("  ✓ Multiple compliance profiles (GDPR, HIPAA, SOC2, PCI DSS, CCPA)")
    print("  ✓ Performance tuning (Low Latency, Balanced, High Compression)")
    print("  ✓ Customizable retention policies")
    print("  ✓ Enterprise white-label ready")
    print("\nAURA: Auditable compression for every brand.")

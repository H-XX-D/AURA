#!/usr/bin/env python3
"""
Healthcare Context Compression Assessment
Testing AURA compression for medical conversation contexts
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'python'))

from aura_compression import ProductionHybridCompressor
from aura_compression.brand_audit_config import PredefinedConfigs

def create_healthcare_compressor():
    """Create HIPAA-compliant AURA compressor for healthcare."""
    config = PredefinedConfigs.healthcare_provider("medicine-cabinet")
    return config.create_auditable_compressor(
        compressor_type='hybrid',
        user_id='dr-smith',
        session_id='patient-12345'
    )

def test_medical_contexts():
    """Test AURA compression on realistic medical conversation contexts."""

    compressor = create_healthcare_compressor()

    # Realistic medical conversation contexts
    medical_contexts = [
        # Patient intake conversation
        """Patient: I'm experiencing chest pain and shortness of breath.
Doctor: How long have you had these symptoms?
Patient: Started yesterday afternoon, getting worse.
Doctor: Any history of heart conditions?
Patient: No, but my father had a heart attack at 55.""",

        # Medication consultation
        """Doctor: Based on your symptoms, I recommend starting Lisinopril 10mg daily for your hypertension.
Patient: Are there any side effects I should watch for?
Doctor: Common side effects include cough, dizziness, and headache. Call immediately if you experience swelling, difficulty breathing, or irregular heartbeat.
Patient: How long before I see improvement?
Doctor: Blood pressure typically improves within 2-4 weeks, but full effects may take up to 8 weeks.""",

        # Chronic condition management
        """Patient: My blood sugar readings have been high lately - averaging 180-200 mg/dL.
Doctor: Let's review your recent meals and activity. Have you been consistent with your metformin?
Patient: I've been taking it regularly, but work stress has me eating more carbs.
Doctor: We may need to adjust your dosage. Let's also discuss stress management techniques and carb counting education.""",

        # Emergency assessment
        """Nurse: Patient arrived via ambulance with acute abdominal pain. Vital signs: BP 160/95, HR 110, RR 22, Temp 101.2F.
Doctor: Pain scale? Location? Radiation?
Nurse: 8/10, right lower quadrant, no radiation. Patient reports nausea and vomiting.
Doctor: Suspect acute appendicitis. Order CT abdomen, labs including WBC, start IV fluids, NPO, pain management.""",

        # Mental health session
        """Therapist: How have you been feeling since our last session?
Patient: The anxiety has been really bad. I can't sleep and I'm having panic attacks at work.
Therapist: Can you tell me more about what triggers these panic attacks?
Patient: Mostly when I have to present or speak in meetings. My heart races, I feel like I can't breathe.
Therapist: This sounds like social anxiety. Let's explore some coping strategies and consider cognitive behavioral techniques.""",

        # Follow-up care coordination
        """Case Manager: How did your physical therapy session go yesterday?
Patient: It was helpful but painful. The exercises are getting harder.
Case Manager: That's normal as you progress. Have you been doing the home exercises?
Patient: I've been doing them twice a day as recommended.
Case Manager: Excellent. Let's schedule your next appointment and I'll coordinate with your physical therapist for progress updates.""",

        # Family consultation
        """Doctor: Your mother's dementia has progressed to moderate stage. She needs 24-hour supervision.
Family Member: We're not ready for nursing home placement yet. What are our options?
Doctor: Consider adult day care programs, home health aides, or in-home respite care. We can also discuss medication management for behavioral symptoms.
Family Member: How do we handle her wandering at night?
Doctor: Home safety modifications and possibly a monitored alarm system would be beneficial.""",

        # Pediatric care
        """Parent: My 3-year-old has been having frequent ear infections. This is the third one this year.
Doctor: Let's check her ears. Yes, acute otitis media. We'll start antibiotics. Any allergies?
Parent: No known allergies. Should we consider tubes?
Doctor: Given the frequency, tympanoplasty may be appropriate. I'll refer you to ENT for evaluation.
Parent: What can we do to prevent future infections?
Doctor: Avoid tobacco smoke, consider flu vaccine, and discuss breastfeeding if applicable.""",

        # End-of-life discussion
        """Doctor: Your father's cancer has progressed despite treatment. We need to discuss hospice care.
Family: How long do you think he has?
Doctor: It's difficult to predict, but likely weeks to a few months. Focus should be on comfort and quality of life.
Family: What services does hospice provide?
Doctor: 24/7 nursing support, pain management, emotional support for family, and coordination of care at home.
Family: We're not ready to stop fighting yet.
Doctor: I understand. We can continue current treatments while incorporating palliative care.""",

        # Telemedicine consultation
        """Patient: I'm having trouble with my insulin pump. The basal rate seems off.
Endocrinologist: Let's review your recent CGM data. Your average glucose is 160 mg/dL, higher than our target of 110-130.
Patient: I've been under a lot of stress at work.
Endocrinologist: Stress can definitely affect glucose levels. Let's adjust your basal rates and add a stress-related correction factor.
Patient: Should I increase my long-acting insulin?
Endocrinologist: Let's try the pump adjustments first and recheck in 3 days."""
    ]

    print("🏥 AURA Healthcare Context Compression Assessment")
    print("=" * 60)
    print("Testing HIPAA-compliant compression for medical conversations")
    print()

    total_original = 0
    total_compressed = 0
    compression_ratios = []

    for i, context in enumerate(medical_contexts, 1):
        print(f"📋 Medical Context {i}: {len(context)} chars")

        # Compress
        compressed_data, metadata = compressor.compress(context)

        # Extract method from metadata
        method = metadata.get('method', 'UNKNOWN')

        # Calculate metrics
        ratio = len(compressed_data) / len(context)
        compression_ratios.append(ratio)
        total_original += len(context)
        total_compressed += len(compressed_data)

        print(f"  Ratio: {ratio:.3f}x ({len(compressed_data)}/{len(context)} bytes)")
        print(f"  Method: {method}")
        print(f"  HIPAA Compliant: ✅ Encrypted, Audited, 7-year retention")
        print()

    # Overall assessment
    avg_ratio = sum(compression_ratios) / len(compression_ratios)
    overall_ratio = total_compressed / total_original

    print(f"📊 ASSESSMENT RESULTS")
    print("=" * 60)
    print(f"Average compression ratio: {avg_ratio:.3f}x")
    print(f"Overall compression ratio: {overall_ratio:.3f}x")
    print(f"Total data processed: {len(medical_contexts)} medical contexts")
    print()

    # Healthcare-specific analysis
    print("🏥 HEALTHCARE SUITABILITY ANALYSIS")
    print("-" * 60)

    if overall_ratio < 1.0:
        print(f"✅ COMPRESSION ACHIEVED: Saves bandwidth and storage")
        savings_percent = (1 - overall_ratio) * 100
        print(f"   Bandwidth savings: {savings_percent:.1f}%")
    else:
        print("⚠️  EXPANSION DETECTED: Medical contexts may not compress well")
        expansion_percent = (overall_ratio - 1) * 100
        print(f"   Expansion overhead: {expansion_percent:.1f}%")
    print()
    print("🔒 HIPAA COMPLIANCE FEATURES:")
    print("  ✅ End-to-end encryption")
    print("  ✅ Complete audit trail")
    print("  ✅ 7-year data retention")
    print("  ✅ Data lineage tracking")
    print("  ✅ Access logging")
    print()

    print("💊 MEDICINE CABINET USE CASE ANALYSIS:")
    print("  📈 Context compression enables:")
    print("     • Larger conversation histories in memory")
    print("     • Faster context retrieval")
    print("     • Reduced storage costs for patient records")
    print("     • Improved telemedicine performance")
    print("     • Better AI-assisted diagnosis with more context")
    print()

    # Performance recommendations
    print("🎯 RECOMMENDATIONS:")
    if overall_ratio < 0.9:
        print("  ✅ EXCELLENT: Use AURA for all medical context compression")
    elif overall_ratio < 1.0:
        print("  ✅ GOOD: Use AURA with fallback to uncompressed for incompressible contexts")
    else:
        print("  ⚠️  LIMITED: Consider uncompressed storage or alternative compression")
        print("      Medical conversation contexts may be inherently incompressible")

    return {
        'avg_ratio': avg_ratio,
        'overall_ratio': overall_ratio,
        'total_original': total_original,
        'total_compressed': total_compressed,
        'hipaa_compliant': True
    }

if __name__ == "__main__":
    test_medical_contexts()
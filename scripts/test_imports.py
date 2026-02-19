#!/usr/bin/env python3
"""Test script to verify imports work correctly."""
import sys
sys.path.insert(0, '.')
print("Testing Funnelier imports...")
try:
    from src.core.domain.entities import PhoneNumber
    print("✓ PhoneNumber imported")
    phone = PhoneNumber.from_string('+989123456789')
    print(f"✓ Phone normalized: {phone.normalized}")
    from src.core.domain.enums import FunnelStage, RFMSegment
    print("✓ Enums imported")
    stages = FunnelStage.get_order()
    print(f"✓ Funnel has {len(stages)} stages")
    segment = RFMSegment.from_rfm_score(5, 5, 5)
    print(f"✓ RFM 555 = {segment.value}")
    print("\n✅ All core imports successful!")
except Exception as e:
    import traceback
    print(f"\n❌ Error: {e}")
    traceback.print_exc()

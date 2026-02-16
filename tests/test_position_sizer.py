"""Tests for Position Sizer."""

import pytest
from risk.position_sizer import calculate_position_size
from risk.constants import MAX_EXPOSURE_PER_STOCK, MAX_SMALL_CAP_EXPOSURE

class TestPositionSizer:
    
    def test_calculate_normal_case(self):
        # Case from SRS: Capital 1B, Risk 1%, Entry 72, SL 68
        capital = 1_000_000_000
        risk_pct = 0.01
        entry = 72
        sl = 68
        
        result = calculate_position_size(capital, risk_pct, entry, sl)
        
        assert "error" not in result
        assert result["risk_amount"] == 10_000_000
        assert result["sl_distance"] == 4
        assert result["sl_distance_pct"] == pytest.approx(0.0556, rel=1e-3) # 5.56%
        
        # Shares = 10M / 4 = 2,500,000
        assert result["shares"] == 2_500_000
        assert result["lots"] == 25_000
        
        # Exposure = 2.5M * 72 = 180M
        assert result["exposure_rupiah"] == 180_000_000
        assert result["exposure_pct"] == 0.18 # 18%
        assert result["exposure_rupiah"] <= capital * MAX_EXPOSURE_PER_STOCK
        assert not result["warnings"]

    def test_sl_too_wide_warning(self):
        # Entry 100, SL 80 (20% distance)
        result = calculate_position_size(100_000_000, 0.01, 100, 80)
        assert result["sl_distance_pct"] == 0.20
        assert any("SL too wide" in w for w in result["warnings"])
        
    def test_exposure_limit_capping(self):
        # High capital, tiny SL distance -> Huge size -> Exposure limit
        # Capital 1B, Risk 1% (10M). Entry 1000, SL 999 (dist 1)
        # Raw Shares = 10M / 1 = 10,000,000 shares
        # Raw Exposure = 10M * 1000 = 10B (1000% exposure) -> Should be capped at 25% (250M)
        
        capital = 1_000_000_000
        result = calculate_position_size(capital, 0.01, 1000, 999)
        
        assert result["exposure_pct"] <= MAX_EXPOSURE_PER_STOCK
        assert result["exposure_rupiah"] <= capital * MAX_EXPOSURE_PER_STOCK
        # Max exposure = 250M. Shares = 250M / 1000 = 250,000
        assert result["shares"] == 250_000
        assert any("exceeds" in w for w in result["warnings"])

    def test_small_cap_capping(self):
        # Same as above but small cap -> 15% limit
        capital = 1_000_000_000
        result = calculate_position_size(capital, 0.01, 1000, 999, is_small_cap=True)
        
        assert result["exposure_pct"] <= MAX_SMALL_CAP_EXPOSURE
        assert result["exposure_rupiah"] <= capital * MAX_SMALL_CAP_EXPOSURE
        # Max 150M -> 150,000 shares
        assert result["shares"] == 150_000

    def test_invalid_inputs(self):
        assert "error" in calculate_position_size(0, 0.01, 100, 90)
        assert "error" in calculate_position_size(100, 0.01, 0, 90)
        assert "error" in calculate_position_size(100, 0.01, 100, 110) # SL > Entry

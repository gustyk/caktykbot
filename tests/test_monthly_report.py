
import pytest
from unittest.mock import MagicMock, patch
import sys

# Mock dependencies before import to avoid ImportError
# We keep these globally to ensure import succeeds
mock_plt_module = MagicMock()
mock_pdf_module = MagicMock()
sys.modules["matplotlib"] = MagicMock()
sys.modules["matplotlib.pyplot"] = mock_plt_module
sys.modules["fpdf"] = MagicMock()
sys.modules["fpdf"].FPDF = MagicMock()

from datetime import datetime
import pandas as pd
# Now import module under test
from analytics.monthly_report import generate_markdown_report, generate_pdf_report

@pytest.fixture
def mock_trades():
    return [
        {
            "symbol": "BBCA.JK",
            "exit_date": datetime(2023, 1, 15),
            "pnl_rupiah": 100000,
            "pnl_percent": 5.0,
            "strategy": "vcp",
            "entry_date": datetime(2023, 1, 10),
            "entry_price": 8000,
            "exit_price": 8400,
            "qty": 100
        },
        {
            "symbol": "ASII.JK",
            "exit_date": datetime(2023, 1, 20),
            "pnl_rupiah": -50000,
            "pnl_percent": -2.0,
            "strategy": "ema_pullback",
            "entry_date": datetime(2023, 1, 18),
            "entry_price": 5000,
            "exit_price": 4900,
            "qty": 500
        }
    ]

@patch("analytics.monthly_report.plt")
@patch("analytics.monthly_report.PDFReport")
@patch("analytics.monthly_report.os")
def test_generate_pdf_report(mock_os, MockPDFReport, mock_plt, mock_trades):
    # Setup Mocks
    mock_pdf_instance = MockPDFReport.return_value
    mock_os.path.join.return_value = "/tmp/report.pdf"
    mock_os.path.exists.return_value = False 
    
    # Run
    path = generate_pdf_report(mock_trades, 1, 2023)
    
    # Verify basics
    assert path == "/tmp/report.pdf"
    assert mock_pdf_instance.add_page.called
    assert mock_pdf_instance.output.called
    
    # Verify Chart generation
    assert mock_plt.figure.called
    assert mock_plt.savefig.called

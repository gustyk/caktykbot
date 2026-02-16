from typing import List, Dict
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
from fpdf import FPDF
import tempfile
import os

from .breakdown import analyze_by_strategy
from .bias_detector import detect_biases

class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'CakTykBot Monthly Report', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def generate_monthly_report(trades: List[Dict], month: int, year: int) -> str:
    """
    Generate markdown report for a specific month.
    """
    # ... existing markdown generation ...
    # Refactoring to return both Markdown and PDF path? 
    # Or separate function?
    # Let's keep this for Markdown (text message) and add new one.
    pass 

# I'll overwrite the file to include both functions, reusing logic.

def _get_monthly_df(trades: List[Dict], month: int, year: int) -> pd.DataFrame:
    if not trades:
        return pd.DataFrame()
    df = pd.DataFrame(trades)
    if "exit_date" in df.columns:
        df["exit_date"] = pd.to_datetime(df["exit_date"])
    return df[
        (df["exit_date"].dt.month == month) & 
        (df["exit_date"].dt.year == year)
    ]

def generate_markdown_report(trades: List[Dict], month: int, year: int) -> str:
    df = _get_monthly_df(trades, month, year)
    if df.empty:
        return f"No trades found for {month}/{year}."
        
    total_trades = len(df)
    total_pnl = df["pnl_rupiah"].sum()
    wins = len(df[df["pnl_rupiah"] > 0])
    win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
    
    strat_stats = analyze_by_strategy(df.to_dict("records"))
    biases = detect_biases(df.to_dict("records"))
    
    report = [
        f"# Monthly Trading Report: {month}/{year}",
        "",
        "## Performance Summary",
        f"- **Total PnL**: Rp {total_pnl:,.0f}",
        f"- **Win Rate**: {win_rate:.1f}% ({wins}/{total_trades})",
        "",
        "## Strategy Performance",
        strat_stats.to_string(index=False) if not strat_stats.empty else "No strategy data.",
        "",
        "## Behavioral Analysis",
    ]
    
    if biases:
        for b in biases:
            report.append(f"- ⚠️ {b}")
    else:
        report.append("- No significant biases detected.")
    
    return "\n".join(report)

def generate_pdf_report(trades: List[Dict], month: int, year: int) -> str:
    """
    Generate PDF report and return file path.
    """
    df = _get_monthly_df(trades, month, year)
    if df.empty:
        return None
        
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Title Info
    pdf.cell(200, 10, txt=f"Period: {month}/{year}", ln=1, align='C')
    pdf.ln(10)
    
    # Metrics
    total_trades = len(df)
    total_pnl = df["pnl_rupiah"].sum()
    wins = len(df[df["pnl_rupiah"] > 0])
    win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Performance Summary", 0, 1)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 5, f"Total PnL: Rp {total_pnl:,.0f}", 0, 1)
    pdf.cell(0, 5, f"Win Rate: {win_rate:.1f}% ({wins}/{total_trades})", 0, 1)
    pdf.ln(5)
    
    # Equity Chart
    # Sort by exit date
    df = df.sort_values("exit_date")
    cum_pnl = df["pnl_rupiah"].cumsum()
    
    plt.figure(figsize=(6, 3))
    plt.plot(df["exit_date"], cum_pnl, marker='o', linestyle='-')
    plt.title("Cumulative PnL (Month)")
    plt.xlabel("Date")
    plt.ylabel("PnL (Rp)")
    plt.grid(True)
    plt.tight_layout()
    
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_img:
        plt.savefig(tmp_img.name)
        pdf.image(tmp_img.name, x=10, w=190)
        chart_path = tmp_img.name
    
    plt.close()
    
    pdf.ln(5)
    
    # Strategy Breakdown
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Strategy Performance", 0, 1)
    pdf.set_font("Times", size=10) # Fixed width somewhat better, or use create_table
    
    strat_stats = analyze_by_strategy(df.to_dict("records"))
    if not strat_stats.empty:
        # Simple table rendering line by line
        # Header
        cols = list(strat_stats.columns)
        header = " | ".join(cols)
        pdf.cell(0, 5, header, 0, 1)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        
        for _, row in strat_stats.iterrows():
            line = " | ".join([str(val) for val in row.values])
            pdf.cell(0, 5, line, 0, 1)
    else:
        pdf.cell(0, 5, "No strategy data available.", 0, 1)

    pdf.ln(5)
    
    # Trade Log
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Trade Log (Top 10)", 0, 1)
    pdf.set_font("Arial", size=8)
    
    # Top 10 by PnL
    top_trades = df.sort_values("pnl_rupiah", ascending=False).head(10)
    
    pdf.cell(25, 5, "Date", 1)
    pdf.cell(25, 5, "Symbol", 1)
    pdf.cell(20, 5, "Type", 1)
    pdf.cell(30, 5, "PnL (Rp)", 1)
    pdf.cell(20, 5, "PnL %", 1)
    pdf.ln()
    
    for _, t in top_trades.iterrows():
        pnl_str = f"{t['pnl_rupiah']:,.0f}"
        pct_str = f"{t['pnl_percent']:.1f}%"
        date_str = t["exit_date"].strftime('%Y-%m-%d')
        
        pdf.cell(25, 5, date_str, 1)
        pdf.cell(25, 5, t["symbol"], 1)
        pdf.cell(20, 5, t.get("strategy", "-"), 1)
        pdf.cell(30, 5, pnl_str, 1)
        pdf.cell(20, 5, pct_str, 1)
        pdf.ln()
        
    filename = f"report_{year}_{month}.pdf"
    output_path = f"/tmp/{filename}" # In production use proper temp dir or artifact storage
    # Windows doesn't have /tmp usually, use tempfile dir
    
    output_path = os.path.join(tempfile.gettempdir(), filename)
    pdf.output(output_path)
    
    # Cleanup image
    if os.path.exists(chart_path):
        os.remove(chart_path)
        
    return output_path

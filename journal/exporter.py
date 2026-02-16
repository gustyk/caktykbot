"""Export module for Journal."""
import csv
import io
from typing import List
from db.schemas import Trade

class Exporter:
    """Exports data to various formats."""
    
    @staticmethod
    def to_csv(trades: List[Trade]) -> io.StringIO:
        """Convert list of trades to CSV string buffer."""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            "Symbol", "Entry Date", "Exit Date", "Status", 
            "Qty", "Entry Price", "Exit Price", 
            "PnL (Rp)", "PnL (%)", "Strategy", "Tags"
        ])
        
        for t in trades:
            exit_date = t.exit_date.strftime("%Y-%m-%d") if t.exit_date else ""
            exit_price = f"{t.exit_price:.0f}" if t.exit_price else ""
            pnl_rp = f"{t.pnl_rupiah:.0f}" if t.pnl_rupiah is not None else ""
            pnl_pct = f"{t.pnl_percent:.2f}" if t.pnl_percent is not None else ""
            
            row = [
                t.symbol,
                t.entry_date.strftime("%Y-%m-%d"),
                exit_date,
                t.status,
                t.qty,
                f"{t.entry_price:.0f}",
                exit_price,
                pnl_rp,
                pnl_pct,
                t.strategy,
                f"{t.emotion_tag or ''} {t.setup_tag or ''}"
            ]
            writer.writerow(row)
            
        output.seek(0)
        return output

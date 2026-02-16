
import time
import cProfile
import pstats
from io import StringIO
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data.pipeline import DataPipeline
from db.connection import get_database
from db.repositories.stock_repo import StockRepository
from db.repositories.price_repo import PriceRepository
from db.repositories.pipeline_repo import PipelineRepository
from db.repositories.signal_repo import SignalRepository

from db.schemas import StockCreate

def profile_pipeline():
    print("Setting up pipeline components...")
    db = get_database()
    stock_repo = StockRepository(db)
    price_repo = PriceRepository(db)
    pipeline_repo = PipelineRepository(db)
    signal_repo = SignalRepository(db)
    
    # Ensure we have active stocks
    stocks = stock_repo.get_all_stocks(only_active=True)
    if not stocks or len(stocks) < 5:
        print(f"Only {len(stocks)} active stocks found. Seeding test stocks...")
        test_stocks = ["BBCA.JK", "BBRI.JK", "BMRI.JK", "ASII.JK", "TLKM.JK"]
        for s in test_stocks:
            try:
                stock_repo.add_stock(StockCreate(symbol=s, is_active=True, sector="Finance"))
            except Exception as e:
                print(f"Skipping {s}: {e}")
    
    pipeline = DataPipeline(stock_repo, price_repo, pipeline_repo, signal_repo, max_workers=5)
    
    print("Starting profiling...")
    pr = cProfile.Profile()
    pr.enable()
    
    start_time = time.time()
    try:
        report = pipeline.run()
        print(f"Pipeline completed in {report.duration:.2f}s")
        print(f"Success: {report.success_count}, Failed: {report.fail_count}")
    except Exception as e:
        print(f"Pipeline failed: {e}")
        
    pr.disable()
    end_time = time.time()
    
    print(f"Total Wall Time: {end_time - start_time:.2f}s")
    
    s = StringIO()
    sortby = 'cumulative'
    ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
    ps.print_stats(20) # Print top 20 lines
    print(s.getvalue())

if __name__ == "__main__":
    profile_pipeline()

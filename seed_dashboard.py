from datetime import datetime, timedelta, timezone
from db.connection import get_database
from db.repositories.trade_repo import TradeRepository
from db.schemas import Trade, TradeLeg

def seed_data():
    db = get_database()
    repo = TradeRepository(db)
    
    # Clear existing trades for nesa to ensure fresh start
    print("Clearing existing trades for 'nesa'...")
    repo.collection.delete_many({"user": "nesa"})

    print("Seeding dummy trades...")
    
    # 1. Winning Trade (VCP)
    t1 = Trade(
        symbol="BBCA.JK",
        user="nesa",
        status="closed",
        entry_price=9000,
        qty=100,
        qty_remaining=0,
        entry_date=datetime.now(timezone.utc) - timedelta(days=10),
        exit_date=datetime.now(timezone.utc) - timedelta(days=5),
        strategy="VCP",
        emotion_tag="Disciplined",
        risk_percent=1.0,
        pnl_rupiah=60000.0,
        pnl_percent=6.67,
        legs=[
            TradeLeg(
                exit_date=datetime.now(timezone.utc) - timedelta(days=5),
                exit_price=9600.0,
                qty=100,
                pnl_rupiah=60000.0,
                pnl_percent=6.67,
                emotion_tag="Disciplined"
            )
        ]
    )
    
    # 2. Losing Trade (EMA)
    t2 = Trade(
        symbol="TLKM.JK",
        user="nesa",
        status="closed",
        entry_price=4000,
        qty=1000,
        qty_remaining=0,
        entry_date=datetime.now(timezone.utc) - timedelta(days=8),
        exit_date=datetime.now(timezone.utc) - timedelta(days=7),
        strategy="EMA_PULLBACK",
        emotion_tag="Anxious",
        risk_percent=1.0,
        pnl_rupiah=-150000.0,
        pnl_percent=-3.75,
        legs=[
            TradeLeg(
                exit_date=datetime.now(timezone.utc) - timedelta(days=7),
                exit_price=3850.0,
                qty=1000,
                pnl_rupiah=-150000.0,
                pnl_percent=-3.75,
                emotion_tag="Anxious"
            )
        ]
    )
    
    # 3. Winning Trade (Bandarmologi)
    t3 = Trade(
        symbol="ASII.JK",
        user="nesa",
        status="closed",
        entry_price=5000,
        qty=500,
        qty_remaining=0,
        entry_date=datetime.now(timezone.utc) - timedelta(days=4),
        exit_date=datetime.now(timezone.utc) - timedelta(days=1),
        strategy="BANDARMOLOGI",
        emotion_tag="Disciplined",
        risk_percent=1.0,
        pnl_rupiah=200000.0,
        pnl_percent=8.0,
        legs=[
            TradeLeg(
                exit_date=datetime.now(timezone.utc) - timedelta(days=1),
                exit_price=5400.0,
                qty=500,
                pnl_rupiah=200000.0,
                pnl_percent=8.0,
                emotion_tag="Disciplined"
            )
        ]
    )

    for t in [t1, t2, t3]:
        repo.collection.insert_one(t.model_dump())
    
    print("Done seeding 3 trades.")

if __name__ == "__main__":
    seed_data()

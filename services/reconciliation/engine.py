from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from packages.schemas.reconciliation import ReconciliationRunStatus
from database.models.reconciliation import ReconciliationRun
from services.reconciliation.matchers.payment_settlement import PaymentToSettlementMatcher
from services.reconciliation.matchers.settlement_bank import SettlementToBankTransactionMatcher

class ReconciliationEngine:
    def __init__(self, session: AsyncSession):
        self.session = session
        
    async def run_reconciliation(self) -> dict:
        run_id = str(uuid.uuid4())
        
        # We start an atomic transaction for the entire run
        # Wait, the session provided is usually already bound to a transaction.
        # But to be safe, we rely on the caller to manage the transaction boundary or commit.
        
        run_record = ReconciliationRun(
            id=run_id,
            status=ReconciliationRunStatus.RUNNING,
            total_records_processed=0,
            matches_created=0,
            discrepancies_found=0
        )
        self.session.add(run_record)
        
        try:
            # 1. Payment -> Settlement
            p_to_s = PaymentToSettlementMatcher(self.session, run_id)
            ps_stats = await p_to_s.run()
            
            # 2. Settlement -> Bank Transaction
            s_to_b = SettlementToBankTransactionMatcher(self.session, run_id)
            sb_stats = await s_to_b.run()
            
            # Aggregate stats
            run_record.total_records_processed = ps_stats["processed"] + sb_stats["processed"]
            run_record.matches_created = ps_stats["relationships_created"] + sb_stats["relationships_created"]
            run_record.discrepancies_found = ps_stats["discrepancies"] + sb_stats["discrepancies"]
            
            run_record.status = ReconciliationRunStatus.COMPLETED
            # We don't commit here. The API layer (dependency injected session) will commit it, ensuring atomicity.
            
            return {
                "run_id": run_id,
                "status": "COMPLETED",
                "total_records_processed": run_record.total_records_processed,
                "matches_created": run_record.matches_created,
                "discrepancies_found": run_record.discrepancies_found
            }
            
        except Exception as e:
            # If any exception occurs, SQLAlchemy will roll back the transaction at the API layer.
            # We can log it, but the partial records will be dropped.
            raise e

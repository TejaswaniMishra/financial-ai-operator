from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession

class BaseMatcher(ABC):
    def __init__(self, session: AsyncSession, run_id: str):
        self.session = session
        self.run_id = run_id
        
    @abstractmethod
    async def run(self) -> dict[str, int]:
        """
        Execute the matcher.
        Returns a dictionary with stats:
        {"processed": int, "relationships_created": int, "discrepancies": int}
        """
        pass

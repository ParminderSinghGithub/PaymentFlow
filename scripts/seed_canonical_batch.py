"""CLI utility to seed the canonical 15-case demonstration batch."""

import asyncio
import json
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from paymentflow.db.session import get_sessionmaker
from paymentflow.eval.canonical_batch import seed_canonical_demonstration_batch


async def main():
    print("Seeding canonical 15-case demonstration batch into PostgreSQL...")
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        result = await seed_canonical_demonstration_batch(session=session, reset_first=True)
    print(f"Batch Seed Complete: {json.dumps(result, indent=2)}")


if __name__ == "__main__":
    asyncio.run(main())

import asyncio

from .seed_admin import seed as seed_admin
from .seed_types import seed as seed_types
from .seed_legal import seed as seed_legal
from .seed_focus import seed as seed_focus
from .seed_rules import seed as seed_rules


async def run_all():
    await seed_admin()
    await seed_types()
    await seed_legal()
    await seed_focus()
    await seed_rules()


if __name__ == "__main__":
    asyncio.run(run_all())

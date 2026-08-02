from src.contradiction.contradiction_service import (
    ContradictionService,
)

service = ContradictionService()

query = """
Apple announced record profits this quarter.
"""

result = service.analyse(query)

print(result)
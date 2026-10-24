import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Let's inspect what accounts are linked to other users
from code.evidence_indexer import EvidenceIndexer
from code.identity_resolver import IdentityResolver

indexer = EvidenceIndexer(PROJECT_ROOT / "dataset")
resolver = IdentityResolver(PROJECT_ROOT / "dataset")

print("Checking indexer and resolver ready.")

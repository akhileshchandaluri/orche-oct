import csv
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from code.evidence_indexer import EvidenceIndexer, EvidenceItem
from code.identity_resolver import IdentityResolver, UserProfile
from code.prediction_engine import PredictionEngine
from code.evaluation.evaluator import evaluate_predictions
from code.evaluation.schema_validator import validate_csv

print("Setting up test harness...")

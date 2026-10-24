import csv
import json
import re
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Let's test the complete prediction pipeline with these enhancements
from code.prediction_engine import PredictionEngine
from code.evaluation.evaluator import evaluate_predictions
from code.evaluation.schema_validator import validate_csv

print("Testing integrated run...")

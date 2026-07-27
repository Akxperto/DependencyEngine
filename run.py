#!/usr/bin/env python3
"""Run the task engine against workflow.json."""
import sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])

from engine import run_workflow

run_workflow(tasks_path="workflow.json", dry_run=True)
#!/usr/bin/env python3
"""
Dynamic Scope Columns Migration Generator

This script reads Template 1.xlsx and generates SQL migration statements
to dynamically add scope columns to the company_scopes table.

The scopes are normalized and added as BOOLEAN columns to track which scopes
apply to each company based on the policy-scope matrix.

Usage:
    python migrations/002_generate_scope_columns.py
    
This will read Template 1.xlsx and output migration SQL statements.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.template_matrix_loader import TemplateMatrixLoader, normalize_scope_name
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_migration():
    """
    Generate migration SQL statements for scope columns.
    """
    try:
        # Load the matrix
        loader = TemplateMatrixLoader()
        scope_to_companies = loader.get_scope_to_companies_mapping()
        
        print("-- Migration: Add Dynamic Scope Columns")
        print("-- Description: Dynamically add BOOLEAN columns for each scope")
        print("-- Generated from: Template 1.xlsx")
        print()
        
        # Generate ALTER TABLE statements
        statements = loader.generate_alter_table_statements()
        for stmt in statements:
            print(stmt)
        
        print()
        print(f"-- Total scopes: {len(scope_to_companies)}")
        print(f"-- Scope names: {', '.join(scope_to_companies.keys())}")
        
    except FileNotFoundError as e:
        logger.error(f"Template file not found: {e}")
        print(f"-- ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error generating migration: {e}")
        print(f"-- ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    generate_migration()

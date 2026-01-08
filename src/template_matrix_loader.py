"""
Template Matrix Loader

Reads Template 1.xlsx as a policy-scope matrix:
- Column 1 (SCOPES): Scope names (Registration, Legal and Security Purposes, Customization, etc.)
- Columns 2+: Company names with 'x' marks indicating scope applicability

The matrix maps which scopes apply to which companies, forming the basis for
dynamic column generation in the company_scopes table.
"""

import pandas as pd
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


def normalize_scope_name(name: str) -> str:
    """
    Normalize scope name for use as SQL column name.
    
    Examples:
        "User Identification" -> "user_identification"
        "Legal & Security Purposes" -> "legal_and_security_purposes"
        "Customization/Personalization" -> "customization_personalization"
    
    Args:
        name: Raw scope name from template
        
    Returns:
        Normalized column-safe name
    """
    if not name or not isinstance(name, str):
        return ""
    
    normalized = (
        name.lower()           # Lowercase
        .strip()               # Remove whitespace
        .replace("&", "and")   # Replace & with "and"
        .replace("/", "_")     # Replace / with underscore
        .replace("-", "_")     # Replace - with underscore
        .replace(" ", "_")     # Replace spaces with underscore
        .replace("(", "")      # Remove parentheses
        .replace(")", "")
        .replace(",", "")      # Remove commas
    )
    
    # Remove consecutive underscores
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    
    # Remove leading/trailing underscores
    normalized = normalized.strip("_")
    
    return normalized


def find_template_file() -> Optional[Path]:
    """
    Find Template 1.xlsx in common locations.
    
    Checks:
        - Current working directory
        - data/ folder
        - Project root
        - ../../data/ (relative to src/)
    
    Returns:
        Path to template file if found, None otherwise
    """
    search_paths = [
        Path("Template 1.xlsx"),
        Path("data/Template 1.xlsx"),
        Path("../Template 1.xlsx"),
        Path("../../data/Template 1.xlsx"),
        Path("../../Template 1.xlsx"),
    ]
    
    for path in search_paths:
        if path.exists():
            logger.info(f"Found template at: {path.absolute()}")
            return path
    
    logger.warning(f"Template 1.xlsx not found in any of these locations: {[str(p) for p in search_paths]}")
    return None


class TemplateMatrixLoader:
    """
    Loads and parses Template 1.xlsx as a policy-scope matrix.
    
    Structure:
        SCOPES                      | Company #1 | Company #2 | Company #3 |
        Registration                | x          | x          |            |
        Legal and Security Purposes | x          |            | x          |
        Customization               |            | x          | x          |
    """
    
    def __init__(self, template_path: Optional[Path] = None):
        """
        Initialize template loader.
        
        Args:
            template_path: Path to Template 1.xlsx. If None, searches common locations.
            
        Raises:
            FileNotFoundError: If template cannot be found
        """
        if template_path is None:
            template_path = find_template_file()
        
        if template_path is None or not Path(template_path).exists():
            raise FileNotFoundError(f"Template 1.xlsx not found at {template_path}")
        
        self.template_path = Path(template_path)
        logger.info(f"Initialized TemplateMatrixLoader with: {self.template_path}")
    
    def load_matrix(self) -> Dict[str, List[str]]:
        """
        Load and parse the policy-scope matrix.
        
        Returns:
            Dictionary mapping scope names to list of companies where scope applies:
            {
                "registration": ["Company #1", "Company #2"],
                "legal_and_security_purposes": ["Company #1", "Company #3"],
                ...
            }
        """
        try:
            df = pd.read_excel(self.template_path)
            logger.info(f"Loaded template with {len(df)} rows and {len(df.columns)} columns")
            
            # First column should be SCOPES
            scopes_column = df.columns[0]
            scope_names = df[scopes_column].dropna().tolist()
            
            # Remaining columns are company names
            company_columns = df.columns[1:]
            
            logger.info(f"Found {len(scope_names)} scopes and {len(company_columns)} companies")
            
            # Build the matrix mapping
            matrix = {}
            for scope in scope_names:
                normalized_scope = normalize_scope_name(scope)
                if not normalized_scope:
                    continue
                
                # Find which companies have 'x' for this scope
                companies_for_scope = []
                for company_col in company_columns:
                    # Get the value for this scope/company intersection
                    idx = df[scopes_column].tolist().index(scope) if scope in df[scopes_column].tolist() else None
                    if idx is not None:
                        value = df.iloc[idx][company_col]
                        # Check if marked with 'x' or 'X' or True
                        if pd.notna(value) and str(value).lower().strip() == 'x':
                            companies_for_scope.append(company_col)
                
                matrix[normalized_scope] = companies_for_scope
                logger.debug(f"Scope '{scope}' (normalized: {normalized_scope}) applies to: {companies_for_scope}")
            
            return matrix
        
        except Exception as e:
            logger.error(f"Error loading template matrix: {e}")
            raise
    
    def get_scopes(self) -> List[str]:
        """
        Get list of normalized scope names.
        
        Returns:
            List of normalized scope column names
        """
        matrix = self.load_matrix()
        return list(matrix.keys())
    
    def get_scope_to_companies_mapping(self) -> Dict[str, List[str]]:
        """
        Get the complete scope-to-companies mapping.
        
        Returns:
            Dictionary: {normalized_scope: [company1, company2, ...]}
        """
        return self.load_matrix()
    
    def get_company_to_scopes_mapping(self) -> Dict[str, List[str]]:
        """
        Get the inverted mapping: companies to scopes.
        
        Returns:
            Dictionary: {company_name: [scope1, scope2, ...]}
        """
        scope_to_companies = self.load_matrix()
        company_to_scopes = {}
        
        for scope, companies in scope_to_companies.items():
            for company in companies:
                if company not in company_to_scopes:
                    company_to_scopes[company] = []
                company_to_scopes[company].append(scope)
        
        return company_to_scopes
    
    def generate_alter_table_statements(self) -> List[str]:
        """
        Generate SQL ALTER TABLE statements to add scope columns to company_scopes.
        
        Returns:
            List of SQL statements:
            [
                "ALTER TABLE company_scopes ADD COLUMN IF NOT EXISTS registration BOOLEAN;",
                "ALTER TABLE company_scopes ADD COLUMN IF NOT EXISTS legal_and_security_purposes BOOLEAN;",
                ...
            ]
        """
        scopes = self.get_scopes()
        statements = []
        
        for scope in scopes:
            stmt = f"ALTER TABLE company_scopes ADD COLUMN IF NOT EXISTS {scope} BOOLEAN DEFAULT FALSE;"
            statements.append(stmt)
        
        logger.info(f"Generated {len(statements)} ALTER TABLE statements")
        return statements


def load_matrix_from_template(template_path: Optional[Path] = None) -> Dict[str, List[str]]:
    """
    Convenience function to load the policy-scope matrix.
    
    Args:
        template_path: Path to Template 1.xlsx. If None, searches common locations.
        
    Returns:
        Dictionary mapping scope names to list of companies
    """
    loader = TemplateMatrixLoader(template_path)
    return loader.load_matrix()


def get_scope_names(template_path: Optional[Path] = None) -> List[str]:
    """
    Convenience function to get normalized scope names.
    
    Args:
        template_path: Path to Template 1.xlsx. If None, searches common locations.
        
    Returns:
        List of normalized scope column names
    """
    loader = TemplateMatrixLoader(template_path)
    return loader.get_scopes()


def get_scope_to_companies(template_path: Optional[Path] = None) -> Dict[str, List[str]]:
    """
    Convenience function to get scope-to-companies mapping.
    
    Args:
        template_path: Path to Template 1.xlsx. If None, searches common locations.
        
    Returns:
        Dictionary: {scope: [company1, company2, ...]}
    """
    loader = TemplateMatrixLoader(template_path)
    return loader.get_scope_to_companies_mapping()


def get_company_to_scopes(template_path: Optional[Path] = None) -> Dict[str, List[str]]:
    """
    Convenience function to get company-to-scopes mapping.
    
    Args:
        template_path: Path to Template 1.xlsx. If None, searches common locations.
        
    Returns:
        Dictionary: {company: [scope1, scope2, ...]}
    """
    loader = TemplateMatrixLoader(template_path)
    return loader.get_company_to_scopes_mapping()

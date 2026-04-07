import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime, date
from sql.queries import QUERIES
from models.organization import Organization
from models.funding_opportunity import FundingOpportunity
from models.grant import Grant

class DatabaseService:
    """
    Database abstraction layer implementing GEMS database queries.
    Uses JSON for POC, PostgreSQL for production.
    """
    
    def __init__(self, use_postgres: bool = False):
        self.use_postgres = use_postgres
        self.queries = QUERIES
        
        if use_postgres:
            self._init_postgres()
        else:
            self._init_json()
    
    def _init_json(self):
        """Initialize JSON mock database"""
        self.db_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            'data', 
            'mock_database.json'
        )
        self.data = self._load_json()
        self.conn = None
    
    def _init_postgres(self):
        """Initialize PostgreSQL connection"""
        import psycopg2
        self.conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'GEMS'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD')
        )
        self.data = None
    
    def _load_json(self) -> Dict[str, Any]:
        """Load mock data from JSON"""
        if os.path.exists(self.db_file):
            with open(self.db_file, 'r') as f:
                return json.load(f)
        return {
            "external_organizations": [],
            "funding_cycles": [],
            "grants": [],
            "awards": [],
            "grant_organizations": [],
            "applications": []
        }
    
    # ========================================
    # ValidateUEI
    # ========================================
    
    def validate_uei(self, uei: str) -> bool:
        """
        Check if UEI exists in ExternalOrganizations.
        Maps to: ValidateUEI statement
        """
        if self.use_postgres:
            cursor = self.conn.cursor()
            cursor.execute(self.queries['validate_uei'], {'uei': uei})
            result = cursor.fetchone()
            return result is not None
        else:
            for org in self.data.get('external_organizations', []):
                if org.get('uei') == uei:
                    return True
            return False
    
    # ========================================
    # GetFundingCycleByCode
    # ========================================
    
    def get_funding_cycle_by_code(self, announcement_number: str) -> Optional[FundingOpportunity]:
        """
        Get funding cycle by announcement number.
        Maps to: GetFundingCycleByCode statement
        Returns: FundingOpportunity model (5 fields only) or None
        """
        if self.use_postgres:
            cursor = self.conn.cursor()
            cursor.execute(self.queries['get_funding_cycle_by_code'], 
                         {'announcement_number': announcement_number})
            
            row = cursor.fetchone()
            if row:
                return FundingOpportunity(
                    funding_cycle_id=row[0],
                    funding_cycle_code=row[1],
                    announcement_number=row[2],
                    program_id=row[3],
                    type_of_app_by_fo=row[4]
                )
            return None
        else:
            for fc_data in self.data.get('funding_cycles', []):
                if fc_data.get('announcement_number') == announcement_number:
                    # Only extract the 5 fields that match FundingCycleInfo.cs
                    return FundingOpportunity(
                        funding_cycle_id=fc_data.get('funding_cycle_id'),
                        funding_cycle_code=fc_data.get('funding_cycle_code'),
                        announcement_number=fc_data.get('announcement_number'),
                        type_of_app_by_fo=fc_data.get('type_of_app_by_fo', 1),  # Default to 1 if not present
                        program_id=int(fc_data.get('program_id', 0)) if isinstance(fc_data.get('program_id'), str) else fc_data.get('program_id', 0)
                    )
            return None
    
    # ========================================
    # GetOrganizationByUEI
    # ========================================
    
    def get_organization_by_uei(self, uei: str) -> Optional[Organization]:
        """
        Get organization details by UEI.
        Maps to: GetOrganizationByUEI statement
        Returns: Organization model (3 fields only) or None
        """
        if self.use_postgres:
            cursor = self.conn.cursor()
            cursor.execute(self.queries['get_organization_by_uei'], {'uei': uei})
            
            row = cursor.fetchone()
            if row:
                return Organization(
                    organization_id=row[0],
                    organization_name=row[1],
                    uei=row[2]
                )
            return None
        else:
            for org_data in self.data.get('external_organizations', []):
                if org_data.get('uei') == uei:
                    # Only extract the 3 fields that match OrganizationInfo.cs
                    return Organization(
                        organization_id=org_data.get('organization_id'),
                        organization_name=org_data.get('organization_name'),
                        uei=org_data.get('uei')
                    )
            return None
    
    # ========================================
    # GetGrantByNumber
    # ========================================
    
    def get_grant_by_number(self, grant_number: str) -> Optional[Dict[str, Any]]:
        """
        Get grant by grant number.
        Maps to: GetGrantByNumber statement
        """
        if self.use_postgres:
            cursor = self.conn.cursor()
            cursor.execute(self.queries['get_grant_by_number'], 
                         {'grant_number': grant_number})
            
            row = cursor.fetchone()
            if row:
                return {
                    'grant_id': row[0],
                    'program_id': row[1]
                }
            return None
        else:
            for grant in self.data.get('grants', []):
                if grant.get('grant_number') == grant_number:
                    return grant
            return None
    
    # ========================================
    # GetActiveGrantsByOrganization
    # ========================================
    
    def get_active_grants_by_organization(
        self, 
        organization_id: str, 
        funding_cycle_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get active grants for organization and funding cycle.
        Maps to: GetActiveGrantsByOrganization statement
        """
        if self.use_postgres:
            cursor = self.conn.cursor()
            cursor.execute(self.queries['get_active_grants_by_organization'],
                         {'funding_cycle_id': funding_cycle_id, 
                          'organization_id': organization_id})
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'grant_id': row[0],
                    'project_period_end_date': row[1],
                    'grant_number': row[2],
                    'indefinite_flag': row[3],
                    'indefinite_date_value': row[4],
                    'program_id': row[5],
                    'organization_id': row[6],
                    'grant_status': row[7]
                })
            return results
        else:
            results = []
            for grant_org in self.data.get('grant_organizations', []):
                if (grant_org.get('org_id') == organization_id and
                    grant_org.get('functional_org_type_code') == 1):
                    
                    grant_id = grant_org.get('grant_id')
                    grant = next((g for g in self.data.get('grants', []) 
                                 if g.get('grant_id') == grant_id), None)
                    
                    if grant:
                        award = next((a for a in self.data.get('awards', []) 
                                     if a.get('grant_id') == grant_id), None)
                        
                        if award:
                            end_date_str = award.get('project_period_end_date')
                            if end_date_str:
                                end_date = datetime.fromisoformat(end_date_str)
                                if end_date > datetime.now():
                                    results.append({
                                        'grant_id': grant_id,
                                        'grant_number': grant.get('grant_number'),
                                        'program_id': grant.get('program_id'),
                                        'organization_id': organization_id,
                                        'grant_status': 'Active',
                                        'project_period_end_date': end_date_str
                                    })
            return results
    
    # ========================================
    # CheckProgramMatch
    # ========================================
    
    def check_program_match(self, grant_id: str, fo: str) -> bool:
        """
        Check if grant's program matches funding opportunity.
        Maps to: CheckProgramMatch statement
        """
        if self.use_postgres:
            cursor = self.conn.cursor()
            cursor.execute(self.queries['check_program_match'],
                         {'grant_id': grant_id, 'fo': fo})
            
            return cursor.fetchone() is not None
        else:
            grant = next((g for g in self.data.get('grants', []) 
                         if g.get('grant_id') == grant_id), None)
            
            if not grant:
                return False
            
            fc = next((f for f in self.data.get('funding_cycles', []) 
                      if f.get('funding_cycle_id') == fo), None)
            
            if not fc:
                return False
            
            return grant.get('program_id') == fc.get('program_id')
    
    # ========================================
    # FindRelatedApplications
    # ========================================
    
    def find_related_applications(self, fo: str, org: str) -> List[Dict[str, Any]]:
        """
        Find related applications for funding opportunity and organization.
        Used for duplicate detection - returns existing active applications.
        Maps to: FindRelatedApplications statement
        """
        if self.use_postgres:
            cursor = self.conn.cursor()
            cursor.execute(self.queries['find_related_applications'],
                         {'fo': fo, 'org': org})
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'application_id': row[0],
                    'application_status_flag': row[1],
                    'application_type_code': row[2]
                })
            return results
        else:
            results = []
            # Join application_external_organizations with applications
            # WHERE a.FundingCycleId = fo AND aeo.ExternalOrgId = org
            for aeo in self.data.get('application_external_organizations', []):
                if aeo.get('external_org_id') == org:
                    # Find matching application
                    app_id = aeo.get('application_id')
                    for app in self.data.get('applications', []):
                        if (app.get('application_id') == app_id and
                            app.get('funding_cycle_id') == fo):
                            status = app.get('application_status_flag')
                            if status not in ['9', '10', 9, 10]:
                                results.append({
                                    'application_id': app.get('application_id'),
                                    'application_status_flag': app.get('application_status_flag'),
                                    'application_type_code': app.get('application_type_code')
                                })
                            break
            return results
    
    # ========================================
    # Helper Methods for Validation
    # ========================================
    
    def verify_uei_and_org_name_match(self, uei: str, org_name: str) -> tuple[bool, Optional[str]]:
        """
        Verify organization name matches UEI (case-insensitive).
        Returns (matches, expected_name)
        """
        org = self.get_organization_by_uei(uei)
        if not org:
            return False, None
        
        db_name = org.organization_name.strip().lower()
        input_name = org_name.strip().lower()
        
        return db_name == input_name, org.organization_name
    
    def close(self):
        """Close database connection if using PostgreSQL"""
        if self.use_postgres and self.conn:
            self.conn.close()

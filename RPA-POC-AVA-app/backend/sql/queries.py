"""SQL query definitions for GEMS database validation"""

QUERIES = {
    'validate_uei': """
        SELECT TOP 1 1 AS [Exists]
        FROM dbo.ExternalOrganizations
        WHERE UEI = %(uei)s
    """,
    
    'get_funding_cycle_by_code': """
        SELECT TOP 1
            fc.FundingCycleId,
            fc.FundingCycleCode,
            fc.AnnouncementNumber,
            fc.ProgramId,
            fc.applicationsupportcode AS [TypeOfAppByFO]
        FROM dbo.FundingCycles fc
        WHERE (AnnouncementNumber IS NOT NULL 
               AND fc.AnnouncementNumber = %(announcement_number)s)
    """,
    
    'get_organization_by_uei': """
        SELECT
            o.OrgId,
            o.OrgName,
            o.UEI
        FROM dbo.ExternalOrganizations o
        WHERE o.UEI = %(uei)s
    """,
    
    'get_grant_by_number': """
        SELECT
            g.GrantId,
            g.ProgramId
        FROM dbo.Grants g
        WHERE g.GrantNumber = %(grant_number)s
    """,
    
    'get_active_grants_by_organization': """
        SELECT distinct 
            A.GrantId, 
            C.ProjectPeriodEndDate, 
            substring(C.GrantNumber,3,10) as GrantNumber,
            p.IndefiniteFlag as IndefiniteFlag, 
            p.IndefiniteDateValue,
            A.ProgramId,
            B.OrgId as OrganizationId,
            'Active' as GrantStatus
        FROM dbo.Grants A
        JOIN dbo.GrantOrganizations B ON A.GrantId = B.GrantId 
            AND B.FunctionalOrgTypeCode = 1
        JOIN Awards C ON C.GrantId = A.GrantId 
            AND C.AwardNumber = a.LastRelAwdNoLatestBP
        JOIN Fundingcycles FC ON fc.programid = a.programid 
        JOIN programs p ON fc.ProgramId = p.ProgramId 
            AND p.LatestInstanceFlag = 1
        WHERE FC.FundingCycleId = %(funding_cycle_id)s
            AND B.OrgId = %(organization_id)s
            AND C.ProjectPeriodEndDate > GETDATE()
        ORDER BY C.ProjectPeriodEndDate DESC
    """,
    
    'check_program_match': """
        SELECT g.GrantId FROM Grants g
        JOIN FundingCycles fc ON g.ProgramId = fc.ProgramId
        WHERE g.GrantId = %(grant_id)s
            AND fc.FundingCycleId = %(fo)s
    """,
    
    'find_related_applications': """
        SELECT a.ApplicationId, a.ApplicationStatusFlag, a.ApplicationTypeCode
        FROM ApplicationExternalOrganizations aeo
        JOIN Applications a ON a.ApplicationId = aeo.ApplicationId
        WHERE a.FundingCycleId = %(fo)s
            AND aeo.ExternalOrgId = %(org)s
            AND a.ApplicationStatusFlag NOT IN (9, 10)
    """
}

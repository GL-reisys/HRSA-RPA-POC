"""SQL query definitions for GEMS database validation"""

QUERIES = {
    'validate_uei': """
        SELECT TOP 1 1 AS [Exists]
        FROM dbo.ExternalOrganizations
        WHERE UEI = ?
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
               AND fc.AnnouncementNumber = ?)
    """,
    
    'get_organization_by_uei': """
        SELECT
            o.OrgId,
            o.OrgName,
            o.UEI
        FROM dbo.ExternalOrganizations o
        WHERE o.UEI = ?
    """,
    
    'get_grant_by_number': """
        SELECT
            g.GrantId,
            g.ProgramId
        FROM dbo.Grants g
        WHERE g.StaticGrantNumber = ?
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
        WHERE FC.FundingCycleId = ?
            AND B.OrgId = ?
            AND C.ProjectPeriodEndDate > GETDATE()
        ORDER BY C.ProjectPeriodEndDate DESC
    """,
    
    'check_program_match': """
        SELECT g.GrantId FROM Grants g
        JOIN FundingCycles fc ON g.ProgramId = fc.ProgramId
        WHERE g.GrantId = ?
            AND fc.FundingCycleId = ?
    """,
    
    'find_related_applications': """
        SELECT a.ApplicationId, a.ApplicationStatusFlag, a.ApplicationTypeCode, a.GrantId
        FROM ApplicationExternalOrganizations aeo
        JOIN Applications a ON a.ApplicationId = aeo.ApplicationId
        WHERE a.FundingCycleId = ?
            AND aeo.ExternalOrgId = ?
            AND a.ApplicationStatusFlag NOT IN (9, 10)
    """,
    
    'get_max_attachment_page_count': """
        SELECT MaxAttachmentPageCount 
        FROM FundingCycles 
        WHERE AnnouncementNumber = ?
    """,
    
    'get_package_forms': """
        SELECT DISTINCT F.FormName, F.FormDescription, F.FormVersion, F.FormURI
        FROM GrantsGovPackage AS P
        JOIN GrantsGovPackageForm_R AS PFR ON P.GrantsGovPackageId = PFR.GrantsGovPackageId
        JOIN GrantsGovForm AS F ON PFR.GrantsGovFormId = F.GrantsGovFormId AND F.FormVersion = (
            SELECT DISTINCT MAX(latestForm.FormVersion) latestFormVersion
            FROM GrantsGovForm latestForm 
            WHERE latestForm.FormName = F.FormName AND latestForm.InactiveDate IS NULL
        )
        JOIN LU_GrantsGovFormLibrary lib ON lib.LookupCode = F.GrantsGovFormLibraryCode
        JOIN LU_GrantsGovPackageFamily AS PF ON P.GrantsGovPackageFamilyCode = PF.LookupCode
        JOIN GrantsGovPackageEHBPackage_R gper ON P.GrantsGovPackageFamilyCode = gper.GrantsGovPackageFamilyCode
        JOIN Lu_Package lup ON lup.PackageId = gper.EHBPackageId
        JOIN Lu_Package_Inst lupi ON lupi.PackageId = lup.PackageId AND lupi.PackageInstDesc NOT LIKE '%GAC%'
        JOIN FundingCycles fc ON fc.PackageId = lup.PackageId 
        JOIN FundingCycleAnnouncement ann ON ann.GrantsGovPackageId = P.GrantsGovPackageId AND ann.AnnouncementNo = FC.AnnouncementNumber
        WHERE FC.AnnouncementNumber = ?
    """,
    
    'get_package_attachments': """
        SELECT DISTINCT FC.AnnouncementNumber
        , P.PackageDescription AS GrantsGovPackageName
        , lup.LongDisplayValue EHBPackageName
        , map1.AttachmentPurposeCode, map1.LongDisplayValue, map1.Description
        , map.FilePrefix
        FROM GrantsGovPackage AS P
        JOIN GrantsGovPackageForm_R AS PFR ON P.GrantsGovPackageId = PFR.GrantsGovPackageId
        JOIN GrantsGovForm AS F ON PFR.GrantsGovFormId = F.GrantsGovFormId
        JOIN LU_GrantsGovFormLibrary lib ON lib.LookupCode = F.GrantsGovFormLibraryCode
        JOIN LU_GrantsGovPackageFamily AS PF ON P.GrantsGovPackageFamilyCode = PF.LookupCode
        JOIN GrantsGovPackageEHBPackage_R gper ON P.GrantsGovPackageFamilyCode = gper.GrantsGovPackageFamilyCode
        JOIN Lu_Package lup ON lup.PackageId = gper.EHBPackageId
        JOIN Lu_Package_Inst lupi ON lupi.PackageId = lup.PackageId
        JOIN FundingCycles fc ON fc.PackageId = lup.PackageId
        JOIN GrantsGovAttachmentMapping map ON map.EHBPackageId = lup.PackageId AND map.ExcludeFlag = 0
        JOIN FundingCycleAnnouncement ann ON ann.GrantsGovPackageId = P.GrantsGovPackageId AND ann.AnnouncementNo = FC.AnnouncementNumber
        JOIN (
            SELECT DISTINCT MAX(map.CreatedDate) CreatedDate, map.AttachmentPurposeCode, lap.LongDisplayValue, lap.Description, lap.ActiveDate
            FROM LookupAttachmentPurpose lap 
            JOIN GrantsGovAttachmentMapping map on map.AttachmentPurposeCode = lap.LookupCode 
            WHERE lap.lookupCode IN (22,133,134,135,136,137,138,139,140,141,142,143,144,145,146,147,155,90,96,98,99,100,101,104,109,111,89,25,62,63,95,157,159,113,115,117,119,121)
            GROUP BY map.AttachmentPurposeCode, lap.LongDisplayValue, lap.Description, lap.ActiveDate
        ) map1 on map1.AttachmentPurposeCode = map.AttachmentPurposeCode AND map1.CreatedDate = map.CreatedDate
        WHERE IsNull(lib.DefaultExpirationDate, Getdate()) > Getdate()-1
            AND lib.LookupCode != 1
            AND F.DummyFormFlag = 0
            AND IsNull(P.InactiveDate, Getdate()) > Getdate()-1
            AND IsNull(F.InactiveDate, Getdate()) > Getdate()-1
            AND F.DummyFormFlag = 0
            AND FC.AnnouncementNumber = ?
    """
}

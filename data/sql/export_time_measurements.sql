-- This query is used to extract the time measurements of the Metavision disharge form.
use PUB
go
 
SELECT distinct forms.[Name]
  ,unit.Name as Afdeling
  ,pat.AddmissionDate
  ,pat.DischargeDate
  ,pat.PatientID
  ,forms.[LastUpdate] AS FormRelease
  ,fs.Time AS SessieCreate
  ,dtsStart.Value As 'StartSchrijven'
  ,dtsEnd.Value As 'EindeSchrijven'
  ,DATEDIFF(minute, dtsStart.Value, dtsEnd.Value)+.5 As Schrijven_minuten
FROM [icc_mv6].FB_FORMS forms
  JOIN [icc_mv6].FB_SESSIONS fs ON fs.FormID = forms.FormID
  JOIN [icc_mv6].Patients pat ON pat.PatientID = fs.PatientID AND pat.IsJunk=0 AND LEN(pat.[HospitalNumber])=7 AND NOT pat.[LastName]='Proefpersoon'
  LEFT JOIN [icc_mv6].FB_DATE_TIME_SIGNALS dtsStart ON dtsStart.SessionID = fs.SessionID AND dtsStart.ParameterID = '14259'
  LEFT JOIN [icc_mv6].FB_DATE_TIME_SIGNALS dtsEnd ON dtsEnd.SessionID = fs.SessionID AND dtsEnd.ParameterID = '6181'
  LEFT JOIN [icc_mv6].LogicalUnits unit ON pat.LogicalUnitID = unit.LogicalUnitID
WHERE forms.[Name]='MS Opname'
  AND forms.[LastUpdate]>='2024-09-18'
--    AND forms.[LastUpdate]< '2024-10-15' -- tbv extractie pre implementatie data
 
ORDER BY pat.[AddmissionDate], pat.[PatientID], fs.[Time], dtsStart.[Value], forms.[LastUpdate]
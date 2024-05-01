
SELECT --TOP 1000
    enc1.subject_Patient_value,  -- Only used in datamanager folder
    enc2.specialty_Organization_value,
    enc1.identifier_value AS enc_id,
    enc1.period_start,
    enc1.period_end,
    enc1.[status],
    cons_maincat.[NAAM] as hoofdcat,
    cons_cat.[NAAM] as subcat,
    cons_regp.[CLASSID],
    cons_regp.[TEXT],
    cons_regp.[DATE],
    cons_regp.[TIME],
    cons_regp.[SPECIALISM]
FROM
    DWH.models.Encounter enc1
    JOIN DWH.models.Encounter enc2 ON enc2.partOf_Encounter_value = enc1.identifier_value
    JOIN STG.hix.CONSULT_REGPART cons_regp ON enc1.subject_Patient_value = cons_regp.PATIENTNR AND cons_regp.DATE BETWEEN CONVERT(DATE, enc1.period_start) AND CONVERT(DATE, enc1.period_end)
    JOIN [STG].[hix].[CONSULT_CATEGORY] cons_cat ON cons_regp.CATEGORYID = cons_cat.CATID
    JOIN [STG].[hix].[CONSULT_CATEGORY] cons_maincat ON cons_cat.MAINCATID = cons_maincat.CATID
WHERE
    enc1.identifier_system = 'https://metadata.umcutrecht.nl/ids/HixOpname'
    --AND enc1.status = 'finished'
    AND enc2.identifier_system = 'https://metadata.umcutrecht.nl/ids/HixOpnamePeriode'
    --AND enc2.class_code = 'IMP'
    AND enc2.specialty_Organization_value IN ('CAR')

    --AND cons_maincat.CATID NOT IN (
    --    'CONS000017')  -- Uitslagen
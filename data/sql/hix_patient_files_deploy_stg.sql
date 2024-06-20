SELECT
    enc1.subject_Patient_value,  -- Only used in datamanager folder
    enc2.specialty_Organization_value,
    enc1.identifier_value AS enc_id,
    enc1.period_start,
    enc1.period_end,
    enc1.[status],
    cons_cat.[NAAM] as subcat,
    cons_cat.CATID as subcat_id,
    cons_cat.MAINCATID as maincat_id,
    cons_regp.[CLASSID],
    cons_regp.[SPECIALISM],
    cons_regp.[TEXT],
    cons_regp.[TEXTTYPE],
    cons_regp.[DATE],
    cons_regp.[TIME]
FROM
    DWH.models.Encounter enc1
    JOIN DWH.models.Encounter enc2 ON enc2.partOf_Encounter_value = enc1.identifier_value 
    JOIN STG.hix.CONSULT_REGPART cons_regp ON enc1.subject_Patient_value = cons_regp.PATIENTNR
    JOIN [STG].[hix].[CONSULT_CATEGORY] cons_cat ON cons_regp.CATEGORYID = cons_cat.CATID
WHERE
    1=1
    AND enc1.identifier_system = 'https://metadata.umcutrecht.nl/ids/HixOpname'
    AND enc1.status = 'in-progress'
    AND enc2.identifier_system = 'https://metadata.umcutrecht.nl/ids/HixOpnamePeriode'
    AND enc2.class_code = 'IMP'
    AND enc2.specialty_Organization_value IN ('CAR') -- voor later: 'PSY', 'GGZ'
    AND cons_regp.SPECIALISM = 'CAR'
    
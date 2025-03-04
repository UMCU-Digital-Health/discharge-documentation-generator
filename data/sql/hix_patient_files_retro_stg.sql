SELECT DISTINCT
    CONVERT(
        VARCHAR(64),
        HASHBYTES(
            'SHA2_256',
            CONCAT(enc1.subject_Patient_value, 'aiva')
        ),
        2
    ) AS pseudo_id,
    enc1.subject_Patient_value as patient_id,  -- Only used in datamanager folder
    enc2.specialty_Organization_value as department,
    enc1.identifier_value AS enc_id,
    enc1.period_start as admissionDate,
    enc1.period_end as dischargeDate,
    cons_cat.[NAAM] as description,
    cons_regp.[TEXT] as content,
    cons_regp.[DATE] as date
FROM
    [PUB].[aiva_discharge_docs].Encounter enc1
    JOIN [PUB].[aiva_discharge_docs].Encounter enc2 ON enc2.partOf_Encounter_value = enc1.identifier_value 
    JOIN [PUB].[aiva_discharge_docs].CONSULT_REGPART cons_regp ON enc1.subject_Patient_value = cons_regp.PATIENTNR
    JOIN [PUB].[aiva_discharge_docs].[CONSULT_CATEGORY] cons_cat ON cons_regp.CATEGORYID = cons_cat.CATID
WHERE
    1=1
    AND enc1.identifier_system = 'https://metadata.umcutrecht.nl/ids/HixOpname'
    AND enc1.status = 'finished'
    AND enc1.period_end >= :start_date
    AND enc1.period_end < :end_date
    AND enc2.identifier_system = 'https://metadata.umcutrecht.nl/ids/HixOpnamePeriode'
    AND enc2.class_code = 'IMP'
    AND enc2.specialty_Organization_value IN ('CAR')
    AND cons_regp.SPECIALISM = 'CAR'
    AND cons_regp.[DATE] <= enc1.period_end
    AND cons_regp.[DATE] >= enc1.period_start    
-- This query is used in the NiFi flow to retrieve the patient files for Metavision departments.
    SELECT
        CONVERT(
        VARCHAR(64),
        HASHBYTES(
            'SHA2_256',
            CONCAT(enc.subject_Patient_value, 'aiva')
        ),
        2
    ) AS pseudo_id,
        enc.subject_Patient_value AS patient_id,
        enc.identifier_value AS enc_id,
        enc.period_start AS admissionDate,
        enc.location_Location_value_original AS department,
        obs.code_display_original AS description,
        obs.effectiveDateTime AS date,
        obs.valueString AS content
    FROM
        [PUB].[aiva_discharge_docs].[Encounter] enc
        JOIN [PUB].[aiva_discharge_docs].[Observation] obs ON obs.context_Encounter_system = enc.identifier_system
            AND obs.context_Encounter_value = enc.identifier_value
        LEFT JOIN [PUB].[aiva_discharge_docs].[Patient] pat ON enc.subject_Patient_value = pat.identifier_value
    WHERE
    1 = 1
        AND enc.[identifier_system] = 'https://metadata.umcutrecht.nl/ids/MetavisionOpname'
        AND enc.[serviceProvider_Organization_value] IN ('W', 'U')
        AND enc.[location_Location_value_original] IN (
            'Neonatologie',
            'Intensive Care Centrum'
        )
        AND enc.[status] = 'in-progress'
        AND obs.identifier_system = 'https://metadata.umcutrecht.nl/ids/MetavisionVrijeTekstMeting'
        AND obs.category_display_original IN ('Form Medische Status', 'Form Medische Status Ontslag')
        AND obs.code_display_original IS NOT NULL
        AND enc.period_start < CAST(GETDATE() - 1 AS DATE) -- Only include encounters that are at least 1 day old
        AND pat.isTestpatient IS NULL -- Exclude test patients, NULL occurs for regular patient encounters as PUB only contains isTestpatient = 1
        AND enc.subject_Patient_value NOT IN ('6476687', 'Intensive Ca_21', 'testbed3', '55667788899', '1234123')

UNION ALL

    -- This query retrieves the patient files for HiX departments that are currently admitted (currenctly only CAR)
    SELECT
        CONVERT(
        VARCHAR(64),
        HASHBYTES(
            'SHA2_256',
            CONCAT(enc1.subject_Patient_value, 'aiva')
        ),
        2
    ) AS pseudo_id,
        enc1.subject_Patient_value as patient_id,
        enc1.identifier_value AS enc_id,
        enc1.period_start as admissionDate,
        enc2.specialty_Organization_value as department,
        cons_cat.[NAAM] as description,
        cons_regp.[DATE] as date,
        cons_regp.[TEXT] as content
    FROM
        [PUB].[aiva_discharge_docs].Encounter enc1
        JOIN [PUB].[aiva_discharge_docs].Encounter enc2 ON enc2.partOf_Encounter_value = enc1.identifier_value
        JOIN [PUB].[aiva_discharge_docs].CONSULT_REGPART cons_regp ON enc1.subject_Patient_value = cons_regp.PATIENTNR
        JOIN [PUB].[aiva_discharge_docs].[CONSULT_CATEGORY] cons_cat ON cons_regp.CATEGORYID = cons_cat.CATID
        LEFT JOIN [PUB].[aiva_discharge_docs].[Patient] pat ON enc2.subject_Patient_value = pat.identifier_value
    WHERE
    1=1
        AND enc1.identifier_system = 'https://metadata.umcutrecht.nl/ids/HixOpname'
        AND enc1.status = 'in-progress'
        AND enc2.identifier_system = 'https://metadata.umcutrecht.nl/ids/HixOpnamePeriode'
        AND enc2.class_code = 'IMP'
        AND enc2.specialty_Organization_value IN ('CAR')
        AND enc2.status = 'in-progress'
        AND cons_regp.SPECIALISM = 'CAR'
        AND cons_regp.[DATE] >= enc1.period_start
        AND pat.isTestpatient IS NULL  -- Exclude test patients, NULL occurs for regular patient encounters as PUB only contains isTestpatient = 1
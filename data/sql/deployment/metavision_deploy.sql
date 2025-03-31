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
    obs.identifier_value AS obs_id,
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
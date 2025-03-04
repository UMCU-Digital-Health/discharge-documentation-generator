SELECT
    CONVERT(
        VARCHAR(64),
        HASHBYTES(
            'SHA2_256',
            CONCAT(enc.subject_Patient_value, 'aiva')
        ),
        2
    ) AS pseudo_id,
    enc.subject_Patient_value as patient_id,  -- Only used in datamanager folder
    enc.identifier_value AS enc_id,
    enc.period_start as admissionDate,
    enc.period_end as dischargeDate,
    enc.location_Location_value_original as department,
    obs.code_display_original as description,
    obs.effectiveDateTime as date, -- currently it is a timestamp, but will be converted to date in processing
    obs.valueString as content
FROM
    [PUB].[aiva_discharge_docs].[Encounter] enc
    JOIN [PUB].[aiva_discharge_docs].[Observation] obs ON obs.context_Encounter_system = enc.identifier_system
    AND obs.context_Encounter_value = enc.identifier_value
WHERE
    1 = 1
    AND enc.[identifier_system] = 'https://metadata.umcutrecht.nl/ids/MetavisionOpname'
    AND enc.period_end >= :start_date
    AND enc.period_end < :end_date
    AND enc.[serviceProvider_Organization_value] IN ('W', 'U')
    AND enc.[location_Location_value_original] IN (
        'Neonatologie',
        'Intensive Care Centrum'
    )
    AND obs.identifier_system = 'https://metadata.umcutrecht.nl/ids/MetavisionVrijeTekstMeting'
    AND obs.category_display_original IN ('Form Medische Status', 'Form Medische Status Ontslag');

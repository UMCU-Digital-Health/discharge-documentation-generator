  SELECT
    enc.subject_Patient_value,
    enc.identifier_value AS enc_id,
    enc.period_start,
    enc.period_end,
    enc.[status],
    enc.location_Location_value_original,
    obs.identifier_value AS obs_id,
    obs.code_display_original,
    obs.category_display_original,
    obs.effectiveDateTime,
    obs.valueString
FROM
    [DWH].[models].[Encounter] enc
    JOIN [DWH].[models].[Observation] obs ON obs.context_Encounter_system = enc.identifier_system
    AND obs.context_Encounter_value = enc.identifier_value
WHERE
    1 = 1
    AND enc.[identifier_system] = 'https://metadata.umcutrecht.nl/ids/MetavisionOpname'
    AND enc.[serviceProvider_Organization_value] IN ('W', 'U')
    AND enc.[location_Location_value_original] IN (
        'Neonatologie',
        'Intensive Care Centrum'
    )
    --AND (enc.[status] = 'in-progress' OR (enc.[status] = 'finished' AND enc.period_end >= DATEADD(day, -1, GETDATE())))
    AND enc.[status] = 'in-progress'
    AND obs.identifier_system = 'https://metadata.umcutrecht.nl/ids/MetavisionVrijeTekstMeting'
    AND obs.category_display_original IN ('Form Medische Status', 'Form Medische Status Ontslag');

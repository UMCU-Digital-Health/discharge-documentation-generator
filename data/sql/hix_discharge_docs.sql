SELECT
    CONVERT(
        VARCHAR(64),
        HASHBYTES(
            'SHA2_256',
            CONCAT(enc1.subject_Patient_value, 'aiva')
        ),
        2
    ) AS pseudo_id,
    enc1.subject_Patient_value,  -- Only used in datamanager folder
    enc1.identifier_value AS enc_id,
    enc1.period_start,
    enc1.period_end,
    enc1.[status],
    enc2.identifier_value AS enc2_id,
    enc2.specialty_Organization_value,
    enc2.location_Location_value,
    dr.[description],
    dr.created,
    dr.docStatus,
    dr.content_attachment1_plain_data
FROM
    DWH.models.Encounter enc1
    JOIN DWH.models.Encounter enc2 ON enc2.partOf_Encounter_value = enc1.identifier_value
    JOIN [DWH].[models].[DocumentReference] dr ON dr.context_encounter_Encounter_system = enc1.identifier_system
    AND dr.context_encounter_Encounter_value = enc1.identifier_value
WHERE
    enc1.identifier_system = 'https://metadata.umcutrecht.nl/ids/HixOpname'
    AND enc1.status = 'finished'
    AND enc1.period_end >= '2023-11-01'
    AND enc2.identifier_system = 'https://metadata.umcutrecht.nl/ids/HixOpnamePeriode'
    AND enc2.class_code = 'IMP'
    AND enc2.specialty_Organization_value = 'CAR'
    AND dr.identifier_system = 'https://metadata.umcutrecht.nl/ids/HixDocument'
    AND dr.type2_code_original IN (
        '1000100089',  -- Ontslagbericht
        '1000100013'   -- Voorlopige Ontslagbrief
    );
-- This query retrospectively retrieves the discharge docs for HiX departments (currenctly only CAR)
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
    dr.type2_display_original as description,
    dr.created as date, -- currently it is a timestamp, but will be converted to date in processing
    dr.content_attachment1_plain_data as content
FROM
    [PUB].[aiva_discharge_docs].Encounter enc1
    JOIN [PUB].[aiva_discharge_docs].Encounter enc2 ON enc2.partOf_Encounter_value = enc1.identifier_value
    JOIN [PUB].[aiva_discharge_docs].[DocumentReference] dr ON dr.context_encounter_Encounter_system = enc1.identifier_system
    AND dr.context_encounter_Encounter_value = enc1.identifier_value
WHERE
    enc1.identifier_system = 'https://metadata.umcutrecht.nl/ids/HixOpname'
    AND enc1.status = 'finished'
    AND enc1.period_end >= :start_date
    AND enc1.period_end < :end_date
    AND enc2.identifier_system = 'https://metadata.umcutrecht.nl/ids/HixOpnamePeriode'
    AND enc2.class_code = 'IMP'
    AND enc2.specialty_Organization_value IN ('CAR')
    AND dr.identifier_system = 'https://metadata.umcutrecht.nl/ids/HixDocument'
    AND dr.type2_code_original IN (
        '1000100089',  -- Ontslagbericht
        '1000100013',   -- Voorlopige Ontslagbrief
        'CS00000003'  -- Klinische brief
    )
    AND dr.docStatus = 'final'
    AND dr.author_Organization_value = 'CAR'
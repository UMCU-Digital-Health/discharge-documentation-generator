-- This query retrospectively retrieves the discharge docs from HiX for Metavision departments
SELECT DISTINCT
    enc.subject_Patient_value as patient_id,
    enc.location_Location_value_original as department,
    enc.identifier_value AS enc_id,
    enc.period_start as admissionDate,
    enc.period_end as dischargeDate,
    dr.created as date,
    dr.content_attachment1_plain_data as content,
    dr.author_Organization_value as author,
    dr.type2_code_original as document_type_code,
    dr.type2_display_original as document_type_description
FROM
    [PUB].[aiva_discharge_docs].Encounter enc
    JOIN [PUB].[aiva_discharge_docs].[DocumentReference] dr ON dr.context_encounter_Encounter_value = enc.partOf_Encounter_value
WHERE
    1=1
    AND enc.identifier_system = 'https://metadata.umcutrecht.nl/ids/MetavisionOpname'
    AND enc.status = 'finished'
    AND enc.period_end >= '2025-04-01'
    AND enc.period_end < '2025-07-02'
    AND enc.[serviceProvider_Organization_value] IN ('W', 'U')
    AND enc.[location_Location_value_original] IN (
        'Neonatologie',
        'Intensive Care Centrum'
    )
    AND dr.identifier_system = 'https://metadata.umcutrecht.nl/ids/HixDocument'
    AND dr.docStatus = 'final'
    AND dr.author_Organization_value IN ('ICA', 'ICN', 'NEO')

-- Note that this query does not return all of the sent out discharge letters as for some patients of the NICU the admission is registered under the mother's patient number.
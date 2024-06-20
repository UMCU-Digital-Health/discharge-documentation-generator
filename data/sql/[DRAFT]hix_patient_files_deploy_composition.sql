
SELECT
    enc1.subject_Patient_value,
    comp.[subject_Patient_value],
    enc2.specialty_Organization_value,
    enc1.identifier_value AS enc_id,
    enc1.period_start,
    enc1.period_end,
    enc1.[status],
    comp_section.[section_title_code_original],
    comp_section.[section_title_display_original],
    comp_section.[section_text],
    comp_section.[section_text_contentType],
    comp.[type_code_original],
    comp.[type_display_original],
    comp.[subject_Patient],
    comp.[consultdate],
    comp.[author_PractitionerRole],
    comp.[author_PractitionerRole_value],
    comp.[specialty_Organization],
    comp.[specialty_Organization_value]
FROM
    DWH.models.Encounter enc1
    JOIN DWH.models.Encounter enc2 ON enc2.partOf_Encounter_value = enc1.identifier_value 
    JOIN DWH.L1.Composition comp ON enc1.subject_Patient_value = comp.subject_Patient_value
    JOIN DWH.L1.Composition_Section comp_section ON comp.identifier_value = comp_section.parent_identifier_value
WHERE
    1=1
    AND enc1.identifier_system = 'https://metadata.umcutrecht.nl/ids/HixOpname'
    AND enc1.status = 'in-progress'
    AND enc2.identifier_system = 'https://metadata.umcutrecht.nl/ids/HixOpnamePeriode'
    AND enc2.class_code = 'IMP'
    AND enc2.specialty_Organization_value IN ('CAR', 'PSY', 'GGZ')

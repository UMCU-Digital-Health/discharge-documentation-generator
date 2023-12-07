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
    qn.identifier_value as qn_id,
    qn.category_display,
    qn.name,
    qr.identifier_value AS qr_id,
    qr.authored,
    qr.created,
    qri.identifier_value as qri_id,
    qri.item_text,
    qri.item_answer_value_valueString
FROM
    DWH.models.Encounter enc1
    JOIN DWH.models.Encounter enc2 ON enc2.partOf_Encounter_value = enc1.identifier_value
    JOIN [DWH].[models].[QuestionnaireResponse] qr ON qr.subject_Patient_value = enc2.subject_Patient_value
        AND qr.subject_Patient_system = enc2.subject_Patient_system
        AND qr.created BETWEEN enc1.period_start
        AND enc1.period_end
    JOIN [DWH].[models].[Questionnaire] qn ON qr.questionnaire_Questionnaire_system = qn.identifier_system
        AND qr.questionnaire_Questionnaire_value = qn.identifier_value
    JOIN [DWH].[models].[QuestionnaireResponse_Item] qri ON qri.parent_identifier_system = qr.identifier_system
        AND qri.parent_identifier_value = qr.identifier_value
WHERE
    enc1.identifier_system = 'https://metadata.umcutrecht.nl/ids/HixOpname'
    AND enc1.status = 'finished'
    AND enc1.period_end >= '2023-11-01'
    AND enc2.identifier_system = 'https://metadata.umcutrecht.nl/ids/HixOpnamePeriode'
    AND enc2.class_code = 'IMP'
    AND enc2.specialty_Organization_value = 'CAR'
    AND qn.identifier_system = 'https://metadata.umcutrecht.nl/ids/HixVragenlijst'
    AND qn.name = 'CAR Consult'
    AND qri.item_text in (
        'Anamnese',
        'Lichamelijk onderzoek',
        'Aanvullend onderzoek',
        'Conclusie',
        'Beleid'
    );

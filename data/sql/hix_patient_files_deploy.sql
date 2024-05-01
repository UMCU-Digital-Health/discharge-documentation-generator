SELECT --TOP 1000
    enc1.subject_Patient_value,
    enc2.specialty_Organization_value,
    enc1.identifier_value AS enc_id,
    enc1.period_start,
    enc1.period_end,
    enc1.[status],
    cons_cat.[NAAM] as subcat,
    cons_cat.CATID as subcat_id,
    cons_cat.MAINCATID as maincat_id,
    cons_regp.[CLASSID],
    cons_regp.[SPECIALISM],
    cons_regp.[TEXT],
    cons_regp.[TEXTTYPE],
    cons_regp.[DATE],
    cons_regp.[TIME]
FROM
    DWH.models.Encounter enc1
    JOIN DWH.models.Encounter enc2 ON enc2.partOf_Encounter_value = enc1.identifier_value 
    JOIN STG.hix.CONSULT_REGPART cons_regp ON enc1.subject_Patient_value = cons_regp.PATIENTNR
    JOIN [STG].[hix].[CONSULT_CATEGORY] cons_cat ON cons_regp.CATEGORYID = cons_cat.CATID
WHERE
    1=1
    AND enc1.identifier_system = 'https://metadata.umcutrecht.nl/ids/HixOpname'
    AND enc1.status = 'in-progress'
    AND enc2.identifier_system = 'https://metadata.umcutrecht.nl/ids/HixOpnamePeriode'
    AND enc2.class_code = 'IMP'
    -- AND enc2.specialty_Organization_value IN ('CAR', 'PSY', 'GGZ')
    AND (
        (enc2.specialty_organization_value = 'CAR'
            AND cons_cat.CATID IN (
                'CONS000021', -- Beleid
                'CONS000024', -- Beloop
                'CONS000018', -- Conclusie
                'CONS000019', -- Diagnose
                'CONS000001', -- Samenvatting
                'CONS000013', -- Lichamelijk onderzoek
                'CONS000015', -- Aanvullend onderzoek
                'CONS000046', -- Overweging / Differentiaal diagnose
                'CONS000002', -- Reden van komst / Verwijzing
                'CONS000045', -- Uitgevoerde behandeling/verrichting
                'CONS000003'  -- Anamnese
            )
            AND cons_regp.SPECIALISM = 'CAR')
        OR (enc2.specialty_organization_value  IN ('PSY', 'GGZ') 
            AND cons_cat.CATID IN (
                'CONS000016', -- Aangevraagde onderzoeken
                'CONS000015', -- Aanvullend onderzoek
                'CONS000003', -- Anamnese
                'CONS000008', -- Actuele medicatie
                'CONS000021', -- Beleid
                'CONS000024', -- Beloop
                'CONS000056', -- Correspondentie
                'CONS000018', -- Conclusie
                'CONS000011', -- Familieanamnese
                'CONS000049', -- Functieonderzoeken
                'CONS000013', -- Lichamelijk onderzoek
                'CONS000025', -- Laboratorium
                'CONS000023', -- Medicatie
                'CONS000026', -- Microbiologie
                'CONS000046', -- Overweging / Differentiaal diagnose
                'CONS000043', -- Overige acties
                'CONS000027', -- Radiologie
                'CONS000002', -- Reden van komst / Verwijzing
                'CONS000012', -- Sociale anamnese
                'CONS000001', -- Samenvatting
                'CONS000045', -- Uitgevoerde behandeling/verrichting
                'CONS000047', -- Overdracht
                'CONS000004', -- Voorgeschiedenis
                'CONS000014' -- Vitale functies
            )
            AND cons_regp.SPECIALISM IN ('PSY', 'GGZ'))
    )
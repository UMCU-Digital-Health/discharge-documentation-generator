for VAR in MANIFEST_FILE_eval MANIFEST_FILE_pp1 MANIFEST_FILE_pp2 APP_ID_eval APP_ID_pp1 APP_ID_pp2 APP_NAME_eval APP_NAME_pp1 APP_NAME_pp2 API_KEY MANIFEST_FILE_api APP_ID_api APP_NAME_api;
do
    if [[ -z ${!VAR+x} ]]; then
        echo "env variable" $VAR "missing"
        return
    fi
done

read -p "What do you want to deploy? Options: 'eval'/1 ; 'pre-pilot-fase1'/2 ; 'pre-pilot-fase2'/3 ; 'api'/4 " APPLICATION
APPLICATION=${APPLICATION:-N}
if [[ $APPLICATION == 'eval' || $APPLICATION == "1" ]]; then
    echo "Deploying Evaluation APPLICATION"
    cp $MANIFEST_FILE_eval manifest.json
    APP_ID=$APP_ID_eval
    APP_NAME=$APP_NAME_eval
elif [[ $APPLICATION == 'pre-pilot-fase1' || $APPLICATION == "2" ]]; then
    echo "Deploying Pre-pilot fase 1 APPLICATION"
    cp $MANIFEST_FILE_pp1 manifest.json
    APP_ID=$APP_ID_pp1
    APP_NAME=$APP_NAME_pp1
elif [[ $APPLICATION == 'pre-pilot-fase2' || $APPLICATION == "3" ]]; then
    echo "Deploying Pre-pilot fase 2 APPLICATION"
    cp $MANIFEST_FILE_pp2 manifest.json
    APP_ID=$APP_ID_pp2
    APP_NAME=$APP_NAME_pp2
elif [[ $APPLICATION == 'api' || $APPLICATION == "4" ]]; then
    echo "Deploying API"
    cp $MANIFEST_FILE_api manifest.json
    APP_ID=$APP_ID_api
    APP_NAME=$APP_NAME_api
else
    echo "Invalid option"
    return
fi

rsconnect deploy manifest manifest.json \
    --server https://rsc.ds.umcutrecht.nl/ \
    -i \
    --api-key $API_KEY \
    --app-id $APP_ID \
    --title "$APP_NAME" 

rm manifest.json
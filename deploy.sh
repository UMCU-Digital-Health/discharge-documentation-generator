for VAR in MANIFEST_FILE_eval MANIFEST_FILE_pp1 MANIFEST_FILE_pp2 APP_ID_eval APP_ID_pp1 APP_ID_pp2 APP_NAME_eval APP_NAME_pp1 APP_NAME_pp2 API_KEY
do
    if [[ -z ${!VAR+x} ]]; then
        echo "env variable" $VAR "missing"
        return
    fi
done

read -p "What do you want to deploy? Options: 'eval'/1 ; 'pre-pilot-fase1'/2 ; 'pre-pilot-fase2'/3 " DASHBOARD
DASHBOARD=${DASHBOARD:-N}
if [[ $DASHBOARD == 'eval' || $DASHBOARD == "1" ]]; then
    echo "Deploying Evaluation dashboard"
    cp $MANIFEST_FILE_eval manifest.json
    APP_ID=$APP_ID_eval
    APP_NAME=$APP_NAME_eval
elif [[ $DASHBOARD == 'pre-pilot-fase1' || $DASHBOARD == "2" ]]; then
    echo "Deploying Pre-pilot fase 1 dashboard"
    cp $MANIFEST_FILE_pp1 manifest.json
    APP_ID=$APP_ID_pp1
    APP_NAME=$APP_NAME_pp1
elif [[ $DASHBOARD == 'pre-pilot-fase2' || $DASHBOARD == "3" ]]; then
    echo "Deploying Pre-pilot fase 2 dashboard"
    cp $MANIFEST_FILE_pp2 manifest.json
    APP_ID=$APP_ID_pp2
    APP_NAME=$APP_NAME_pp2
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
for VAR in PERSONAL_API_KEY MANIFEST_FILE_eval APP_ID_eval APP_NAME_eval  MANIFEST_FILE_api_periodic APP_ID_api_periodic_acc APP_ID_api_periodic_prod APP_NAME_api_periodic_acc APP_NAME_api_periodic_prod MANIFEST_FILE_api_on_demand APP_ID_api_on_demand_acc APP_ID_api_on_demand_prod APP_NAME_api_on_demand_acc APP_NAME_api_on_demand_prod MANIFEST_FILE_admin APP_ID_admin APP_NAME_admin MANIFEST_FILE_discharge APP_ID_discharge APP_NAME_discharge;
do
    if [[ -z ${!VAR+x} ]]; then
        echo "env variable" $VAR "missing"
        return
    fi
done

read -p "What do you want to deploy? Options: 'eval'/1 ; 'api-periodic-acc'/2 ; 'api-periodic-prod'/3  ; 'api-on-demand-acc'/4 ; 'api-on-demand-prod'/5 ; 'admin'/6 ; 'discharge-dashboard'/7 ;" APPLICATION

read -p "Here is a reminder to check whether the environment variables need to be updated in Posit Connect. Continue? (y/n)" ANSWER
if [[ $ANSWER == 'n' || $ANSWER == "N" ]]; then
    echo "Please update the environment variables in Posit Connect"
    return
fi

read -p "Here is a reminder to check whether you need to update the NiFi flow. Continue? (y/n)" ANSWER
if [[ $ANSWER == 'n' || $ANSWER == "N" ]]; then
    echo "Please update the NiFi flow"
    return
fi


APPLICATION=${APPLICATION:-N}
if [[ $APPLICATION == 'eval' || $APPLICATION == "1" ]]; then
    echo "Deploying Evaluation APPLICATION"
    cp $MANIFEST_FILE_eval manifest.json
    APP_ID=$APP_ID_eval
    APP_NAME=$APP_NAME_eval
elif [[ $APPLICATION == 'api-periodic-acc' || $APPLICATION == "2" ]]; then
    echo "Deploying periodic API in acceptation environment"
    cp $MANIFEST_FILE_api_periodic manifest.json
    APP_ID=$APP_ID_api_periodic_acc
    APP_NAME=$APP_NAME_api_periodic_acc
elif [[ $APPLICATION == 'api-periodic-prod' || $APPLICATION == "3" ]]; then
    echo "Deploying periodic API in production environment"
    cp $MANIFEST_FILE_api_periodic manifest.json
    APP_ID=$APP_ID_api_periodic_prod
    APP_NAME=$APP_NAME_api_periodic_prod
elif [[ $APPLICATION == 'api-on-demand-acc' || $APPLICATION == "4" ]]; then
    echo "Deploying on-demand API in acceptation environment"
    cp $MANIFEST_FILE_api_on_demand manifest.json
    APP_ID=$APP_ID_api_on_demand_acc
    APP_NAME=$APP_NAME_api_on_demand_acc
elif [[ $APPLICATION == 'api-on-demand-prod' || $APPLICATION == "5" ]]; then
    echo "Deploying on-demand API in production environment"
    cp $MANIFEST_FILE_api_on_demand manifest.json
    APP_ID=$APP_ID_api_on_demand_prod
    APP_NAME=$APP_NAME_api_on_demand_prod
elif [[ $APPLICATION == 'admin' || $APPLICATION == "6" ]]; then
    echo "Deploying admin application"
    cp $MANIFEST_FILE_admin manifest.json
    APP_ID=$APP_ID_admin
    APP_NAME=$APP_NAME_admin
elif [[ $APPLICATION == 'discharge-dashboard' || $APPLICATION == "7" ]]; then
    echo "Deploying discharge dashboard"
    cp $MANIFEST_FILE_discharge manifest.json
    APP_ID=$APP_ID_discharge
    APP_NAME=$APP_NAME_discharge
else
    echo "Invalid option"
    return
fi

rsconnect deploy manifest manifest.json \
    --server https://rsc.ds.umcutrecht.nl/ \
    -i \
    --api-key $PERSONAL_API_KEY \
    --app-id $APP_ID \
    --title "$APP_NAME" 

rm manifest.json
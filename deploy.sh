for VAR in PERSONAL_API_KEY MANIFEST_FILE_eval APP_ID_eval APP_NAME_eval  MANIFEST_FILE_api_periodic APP_ID_api_periodic_acc APP_ID_api_periodic_prod APP_NAME_api_periodic_acc APP_NAME_api_periodic_prod MANIFEST_FILE_api_on_demand APP_ID_api_on_demand_acc APP_ID_api_on_demand_prod APP_NAME_api_on_demand_acc APP_NAME_api_on_demand_prod;
do
    if [[ -z ${!VAR+x} ]]; then
        echo "env variable" $VAR "missing"
        return
    fi
done

read -p "What do you want to deploy? Options: 'eval'/1 ; 'api-periodic-acc'/2 ; 'api-periodic-prod'/3  ; 'api-on-demand-acc'/4 ; 'api-on-demand-prod'/5 - " APPLICATION

read -p "Have you updated the environment variables in Posit Connect? (y/n)" ANSWER
if [[ $ANSWER == 'n' || $ANSWER == "N" ]]; then
    echo "Please don't forget to update the environment variables in Posit Connect"
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
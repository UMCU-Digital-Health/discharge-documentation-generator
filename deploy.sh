for VAR in API_KEY APP_ID APP_NAME
do
    if [[ -z ${!VAR+x} ]]; then
        echo "env variable" $VAR "missing"
        return
    fi
done

echo "Warning: re-deploying the application will overwrite the existing database"?
read -p "Have you backup up the SQLite database? [y/N]" BACKUP
BACKUP=${BACKUP:-N}
if [[ $BACKUP != "y" && $BACKUP != "Y" ]]; then
    echo "Backup your db and try again"
    return
fi

rsconnect deploy manifest manifest.json \
    --server https://rsc.ds.umcutrecht.nl/ \
    --api-key $API_KEY \
    --app-id $APP_ID \
    --title "$APP_NAME"
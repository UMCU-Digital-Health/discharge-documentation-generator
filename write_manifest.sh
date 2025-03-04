
read -p "For which application do you want to write a manifest file? Use the exact name of the file within the run folder. You do not need to write 'run/'. " APPLICATION
APPLICATION=${APPLICATION:-N}

# Prompt to check if dash or api
read -p "Is this a dash dashboard or an api? (dash/fastapi) " APP_TYPE
APP_TYPE=${APP_TYPE:-N}

# Prompt to check if data is needed
read -p "Do you need data in your dashboard? (Y/N) " DATA_BOOL
DATA_BOOL=${DATA_BOOL:-N}

# Base command
COMMAND="rsconnect write-manifest $APP_TYPE \
--entrypoint run.$APPLICATION:app --overwrite \
--exclude logs --exclude notebooks --exclude output --exclude tests --exclude build \
--exclude .dvc --exclude .github --exclude .ruff_cache --exclude .coverage \
--exclude .pytest_cache --exclude .env --exclude .venv --exclude .vscode \
--exclude docs --exclude run/cache --exclude \"**/*.db\" --exclude \"**/*.pyc\""

# Conditionally exclude data/raw directory
if [ "$DATA_BOOL" == "N" ] || [ "$DATA_BOOL" == "n" ]; then
    COMMAND="$COMMAND --exclude data/raw --exclude data/sql"
fi

# Execute the command
eval $COMMAND .

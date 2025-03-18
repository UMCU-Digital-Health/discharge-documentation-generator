# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.2.1] - 2025-03-11

### Added
- Added analysis of differences between AI-generated letter and Metavision letter

### Changed
- Added explanations to SQL queries

## [2.2.0] - 2025-03-17

### Changed
- Updated the promptbuilder to raise custom exceptions for cleaner exception handling in the API
- Updated dependencies
- Updated initialise_azure_connection to raise an error when not all environment variables are set
- Fixed some minor typing errors in evaluation dashboard

## [2.1.0] - 2025-03-11

### Changed
- updated the API version to "2024-10-21"
- updates the format that OpenAI API returns the response (in json format) and updates to the prompt and response handling accordingly
- updated CAR prompt based on pre-pilot results
- removed logic for 'addition prompt' which was not used

## [2.0.2] - 2025-03-11

### Changed
- Updated unit tests to improve coverage
- Various typing fixes
- Various improvements to DOCSTRINGS
- Bugfixes from unit tests

## [2.0.1] - 2025-01-29

### Added
- Added notebook for analysing time measurements in Metavision
- Added Scipy as dev dependency for analysis
- Added Metavision time measurements export

## [2.0.0] - 2025-02-11

### Added
- included data export pipeline in data_pipeline.py
- endpoint to remove outdated and all discharge letters
  
### Changed
- Very large refacor cleaning up the codebase
- removed unneccesary logic in evaluation dashboard
- combined processing flows for Metavision and HiX data
- split API into periodic and on-demand API
- prevented SQL injection into queries
- updated unittest
- changed the database structure & fix multiple issues regarding the database (e.g. duplicate enc_id)
- query to not return test patients and to not run the first day of the admission
- url of API endpoints updated in line with convention: - in url and _ in function definition.
- changed way of calling to config variables

## [1.1.2] - 2025-02-17

### Changed
- Fixed SQLAlchemy warnings and maybe also solved the recent issue on production where multiple identical encounters were added to the database

## [1.1.1] - 2025-02-12

### Changed
- Fixed database deadlock issues by committing transactions after each generated discharge letter

## [1.1.0] - 2025-02-11

### Changed
- Updated production GPT model version to GPT4 (turbo-2024-04-09)
- Updated dependencies in requirements.txt
- Updated Python to 3.11 (Some packages have not been compiled for 3.12 yet)

## [1.0.4] - 2025-01-29

### Added
- Added endpoints for HiX integration
- Added example data for HiX integration
- Added unit tests

## [1.0.3] - 2025-01-29

### Fixed
- Fixed Metavision file loaded in evaluation dashboard

## [1.0.2] - 2025-01-27

### Changed
- Hotfix for updating the evaluation dashboard to test different versions of GPT4
- Created new data export of december 2024 and rerun pipelines
- Added deduce pipeline to deduce_text.py
- Updated preprocessing pipeline to preprocessing_dev.py and added a step to generate enc_ids toml file. Removed unused code


## [1.0.1] - 2024-11-20

### Added
- Added a demo dashboard, influenced by the eval dashboard, but limited in functionality

### Changed
- Updated the write-manifest script to exclude pycache and other unneccesary files
- Fixed typo in dashboard layout

### Removed
- Removed pilot application, since this is no longer used, since it is implemented directly into the EHR system

## [1.0.0] - 2024-10-17
### Changed
- version number to 1.0.0 for release pilot
- logging for retrieve API
- deployment config for acc and prod different model implementation

### Added
- prevention of dead database connection

## [0.5.10] - 2024-10-14

### Changed
- Date in generated document now in Dutch format

## [0.5.9] - 2024-10-10

### Changed
- Small textual changes to the discharge letter
- Small fixes to the code
- No longer log the response while generating discharge letters

## [0.5.8] - 2024-10-08

### Fixes
- Retrieve endpoint now returns plain text, which should work better in Metavision
- Small type fixes
- Small documentation fixes

## [0.5.7] - 2024-09-27

### Changed
- X_API_KEY variable across endpoints
- removal of duplicate encounter id's used in pre-pilot evaluation
- change to GPT4
- retrieval filtering now based on dates
- split feedback column into two columns
- environment variables check

### Added
- manually filter out [LEEFTIJD-1]-jarige
- generation_date column in ApiGeneratedDoc

### Fixed
- Fixed retrieve endpoint using patient_number instead of enc_id

## [0.5.6] - 2024-08-28

### Changed
- retrieving API patient id call option for metavision integration to be via enc_id instead of patient number and go back at most 7 days
- new export for the CAR data
- add column to ApiGeneratedDoc for success

### Added
- the feedback endpoint of the API

## [0.5.5] - 2024-15-06

### Changed
- retrieving API patient id call option for metavision integration

## [0.5.4] - 2024-08-06

### Changed
- changed the discharge doc to be saved as a string instead of a json. 
- Error handeling in the PromptBuilder class
- authentication check X-API-KEY
- database connection get_db() updated
- query for dataplatform to not contain NULL

### Added
- include the API for retrieving from the database
- Error handling and check in API
- Pydantic type class to ensure error handling of patient data file
- unit tests for processing
- unit tests for API
- unit tests for PromptBuilder and prompt helper file

## [0.5.3] - 2024-07-23

### Added
- Added a model card
- Added a dataset card


## [0.5.2] - 2024-07-18

### Added 
- working API that processes the data, pseudonomises it, generates a discharge letter and saves it to the database. 

### Changed
- the test data for the API is changed to what the real test data will look like
- updated the dashboard that gathers the last entry in the database. 

## [0.5.1] - 2024-06-19

### Added
- Added a dashboard for phase 2 of the evaluation
- Added tables for storing results of phase 2

### Changed
- Updated highlight function to change background color and font color


## [0.5.0] - 2024-06-19

### Changed
- large refactor

## [0.4.4] - 2024-06-19

### Added
- demo dashboard in english

### Changed
- restructuring of the notebooks
- updating of sql queries


## [0.4.3] - 2024-04-18

### Added
- Added filtering on the data to remove duplicated data in patient file. 
- Added a dashboard to communicate with the Posit database. 
- Added functionality to show stored GPT4 letter in eval dashboard
- Added 'refresh' functionality when switching to a new patient in eval dashboard 


## [0.4.2] - 2024-04-15

### Added
- Added endpoint to the API for deleting old generated discharge documents
- Added unit tests

## [0.4.1] - 2024-04-12

### Changed
- First working version of the API including database tables

### Added
- Added unit tests for the API

## [0.4.0] - 2024-04-11

### Changed
- changed database to the Posit Connect database
- Updated the department prompts
- automatic evaluation using GPT first version

## [0.3.3] - 2024-03-11

### Added
- Notebook to test incremental creation of the discharge documents
- Created a template for the API

### Changed
- Updated the evaluation dashboard to optionally use incremental creation instead of direct, by default this is turned off (uses the ITERATIVE constant)

### Fixed
- Use OpenAI API version `2024-02-1` instead of the outdated version, due to deprecation from Azure

## [0.3.2] - 2024-03-18
- update dashboard with authentications
- update dashboard with psychiatry
- included demo patient in dashbaord
- removal of old demo dashboard

## [0.3.1] - 2024-02-19

### Added
- Added option to download local SQLite database as temporary solution until external DB is in place
- Added a warning message when deploying warning the user to export the database

### Fixed
- Fixed some small static typing errors
- Set temperature to 0.2 in dashboard to prevent users from changing it

## [0.3.0] - 2024-02-16

### Added
- Added a local sqlite database to store evaluation of the dashboard
- Added authorization to the dashboard

### Changed
- Changed the dashboard to use Bootstrap components

## [0.2.1] - 2024-01-31

### Added
- Added SQLAlchemy models and notebook to try out

## [0.2.0] - 2024-02-05

### Added
- Exploratory analysis and preprocessing code
- Visualisation dashboards of metavision and Hix data

## [0.1.3] - 2024-01-19

### Added
- Added DVC experiment setup and config files

### Changed
- Updated to python 3.10
- Updated openai package version and rewrote notebook and demo dash
- Updated DEDUCE version in notebook

### Fixed
- Demo dashboard now sometimes works, still not robust
- Removed print statement from dashboard

## [0.1.2] - 2024-01-10

### Fixed
- Load patient_ids as string, so leading 0's are kept

### Added
- Apply DEDUCE to new export from Metavision

## [0.1.1] - 2023-11-29

### Added
- Added queries to extract data from dataplatform
- Extracted data from the IC's from MetaVision
- Added notebook to apply deduce to extracted data

## [0.1.0] - 2023-11-06

### Added
- demo dashboard
# Replicating SCC Findings to BigQuery

This guide will help you configure a GCP cloud function to replicate Security Command
Center findings to BigQuery.

## Setup

### Pre-work

1.  Set the org and project IDs. The selected project is where the BigQuery tables will
    be created.

    ```shell
    export ORG_ID=<your org id>
    export PROJECT_ID=<your project id>
    gcloud config set project $PROJECT_ID
    ```

1.  Create the service account.

    ```shell
    export SERVICE_ACCOUNT=scc-findings-to-bigquery-sa
    gcloud iam service-accounts create $SERVICE_ACCOUNT \
      --display-name "Service Account for Replicating SCC Findings to BigQuery" \
      --project $PROJECT_ID
    ```

1.  Grant the service account BigQuery Data Owner and Job User on the project.

    ```shell
    gcloud projects add-iam-policy-binding $PROJECT_ID \
      --member="serviceAccount:$SERVICE_ACCOUNT@$PROJECT_ID.iam.gserviceaccount.com" \
      --role='roles/bigquery.jobUser'
    gcloud projects add-iam-policy-binding $PROJECT_ID \
      --member="serviceAccount:$SERVICE_ACCOUNT@$PROJECT_ID.iam.gserviceaccount.com" \
      --role='roles/bigquery.dataOwner'
    ```

1.  Grant the service account Security Center Admin on the org.

    ```shell
    gcloud organizations add-iam-policy-binding $ORG_ID \
      --member="serviceAccount:$SERVICE_ACCOUNT@$PROJECT_ID.iam.gserviceaccount.com" \
      --role='roles/securitycenter.admin'
    ```

### Create the BigQuery Finding Log Table

1.  Make an SCC dataset.

    ```shell
    bq mk scc
    ```

1.  Make a table for the finding logs.

    ```shell
    bq mk --time_partitioning_field eventTime --table scc.findings_log schema.json
    ```

### Configure the Pub/Sub Topic

1.  Create the topic where all the findings will be published.

    ```shell
    gcloud pubsub topics create scc-findings-topic
    export TOPIC=projects/$PROJECT_ID/topics/scc-findings-topic
    ```

1.  Configure SCC to publish notifications to our topic.

    ```shell
    gcloud scc notifications create scc-findings-notify \
      --pubsub-topic $TOPIC --organization $ORG_ID
    ```

### Publish the Cloud Function

1.  Deploy the `publish_findings` cloud function. If you have not enabled Cloud Build
    API, then this command may fail. Follow the link in the error message to enable it
    and then try again.

    ```shell
    gcloud functions deploy publish_findings \
      --service-account="$SERVICE_ACCOUNT@$PROJECT_ID.iam.gserviceaccount.com" \
      --source=publish_findings \
      --trigger-topic=scc-findings-topic \
      --runtime=python39
    ```

## Useful Views

### Current State of the World

1.  Create a view for the current state of the world.

    ```shell
    bq mk \
      --use_legacy_sql=false \
      --view \
      'SELECT
         log.*,
         JSON_EXTRACT_SCALAR(log.sourceProperties, "$.ResourcePath[0]") AS project,
       FROM (
         SELECT ARRAY_AGG(t ORDER BY eventTime DESC LIMIT 1)[OFFSET (0)] AS log
         FROM scc.findings_log AS t
         GROUP BY name
       )' \
      scc.findings
    ```

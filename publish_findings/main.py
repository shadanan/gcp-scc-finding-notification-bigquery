import base64
import json
import logging

from google.cloud import bigquery, securitycenter_v1

BQ_DATASET = "scc"
BQ_TABLE = "findings_log"
BQ_JOB_CONFIG = bigquery.job.LoadJobConfig(
    schema_update_options=[bigquery.job.SchemaUpdateOption.ALLOW_FIELD_ADDITION]
)


def get_source(finding):
    client = securitycenter_v1.SecurityCenterClient()
    source = client.get_source(name=finding["parent"])
    return json.loads(securitycenter_v1.Source.to_json(source))


def get_asset(finding):
    client = securitycenter_v1.SecurityCenterClient()
    resp = client.list_assets(
        securitycenter_v1.ListAssetsRequest(
            parent="/".join(finding["parent"].split("/")[0:2]),
            filter=f'securityCenterProperties.resourceName="{finding["resourceName"]}"',
        )
    )
    page = next(resp.pages)
    if page.total_size == 0:
        return None
    asset = page.list_assets_results[0].asset
    return json.loads(securitycenter_v1.Asset.to_json(asset))


def normalize_asset(asset):
    asset["resourceProperties"] = json.dumps(asset["resourceProperties"])
    asset["securityMarks"]["marks"] = json.dumps(
        asset["securityMarks"].get("marks", {})
    )
    asset["iamPolicyBlob"] = asset["iamPolicy"].get("policyBlob")
    del asset["iamPolicy"]
    return asset


def normalize_finding(finding):
    finding["sourceProperties"] = json.dumps(finding["sourceProperties"])
    finding["securityMarks"]["marks"] = json.dumps(
        finding["securityMarks"].get("marks", {})
    )
    return finding


def publish_rows(rows):
    logging.info(f"Inserting: {rows}")
    client = bigquery.Client()
    table = client.dataset(BQ_DATASET).table(BQ_TABLE)
    client.load_table_from_json(rows, table, job_config=BQ_JOB_CONFIG)


def publish_findings(event, context):
    pubsub_message = base64.b64decode(event["data"]).decode("utf-8")
    message_json = json.loads(pubsub_message)
    finding = normalize_finding(message_json["finding"])

    finding["source"] = get_source(finding)

    asset = get_asset(finding)
    if asset is not None:
        finding["asset"] = normalize_asset(asset)

    publish_rows([finding])

"""template.yaml agrees with the code and the cost and security rules (plan 05.1, 05.2, 05.11)."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import pytest
import yaml

from handlers import store

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "template.yaml"

# Resources the plan forbids because they cost money all day (TRD 12).
NEVER_CREATE = (
    "AWS::EC2::Instance", "AWS::EC2::NatGateway", "AWS::SageMaker::", "AWS::OpenSearch",
    "AWS::Elasticsearch", "AWS::RDS::", "AWS::DocDB::", "AWS::Redshift::", "AWS::ElastiCache::",
    "AWS::Kinesis::", "AWS::MSK::",
)


class _Loader(yaml.SafeLoader):
    """Reads CloudFormation short-form tags such as !Ref and !Sub as plain dicts."""


def _tag(loader: _Loader, suffix: str, node: yaml.Node) -> Any:
    name = "Ref" if suffix == "Ref" else f"Fn::{suffix}"
    if isinstance(node, yaml.ScalarNode):
        value: Any = loader.construct_scalar(node)
        if suffix == "GetAtt":
            value = value.split(".", 1)
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node, deep=True)
    else:
        value = loader.construct_mapping(node, deep=True)
    return {name: value}


_Loader.add_multi_constructor("!", _tag)


@pytest.fixture(scope="module")
def template() -> dict[str, Any]:
    return yaml.load(TEMPLATE.read_text(encoding="utf-8"), Loader=_Loader)  # noqa: S506


def resources(template: dict[str, Any], kind: str) -> dict[str, dict[str, Any]]:
    return {k: v for k, v in template["Resources"].items() if v["Type"] == kind}


def test_it_is_a_sam_template(template: dict[str, Any]) -> None:
    assert template["Transform"] == "AWS::Serverless-2016-10-31"
    assert set(template["Parameters"]) >= {
        "Stage", "AllowedOrigins", "BedrockModelId", "BedrockRegion", "ServerSecretParam",
    }
    assert template["Parameters"]["AllowedOrigins"]["Type"] == "CommaDelimitedList"
    assert template["Parameters"]["AllowedOrigins"]["Default"] == "http://localhost:5173"
    assert template["Parameters"]["ServerSecretParam"]["Default"] == "/thirst/server_secret"


def test_the_four_tables_match_the_store_layout(template: dict[str, Any]) -> None:
    tables = resources(template, "AWS::DynamoDB::Table")
    assert len(tables) == 4
    by_name = {t["Properties"]["TableName"]["Fn::Sub"]: t for t in tables.values()}
    for short, spec in store.TABLE_SPECS.items():
        table = by_name[f"thirst-${{Stage}}-{short}"]["Properties"]
        want = spec.create_args()
        assert table["KeySchema"] == want["KeySchema"], short
        assert table["AttributeDefinitions"] == want["AttributeDefinitions"], short
        assert table["BillingMode"] == "PAY_PER_REQUEST"
        ttl = table.get("TimeToLiveSpecification")
        if spec.ttl:
            assert ttl == {"AttributeName": spec.ttl, "Enabled": True}, short
        else:
            assert ttl is None, short
        assert "PointInTimeRecoverySpecification" not in table  # off: cost


def test_real_data_tables_survive_a_stack_mistake(template: dict[str, Any]) -> None:
    for name, table in resources(template, "AWS::DynamoDB::Table").items():
        retained = name in ("SitesTbl", "ReceiptsTbl")
        assert (table.get("DeletionPolicy") == "Retain") is retained, name
        assert (table.get("UpdateReplacePolicy") == "Retain") is retained, name


def test_global_function_settings(template: dict[str, Any]) -> None:
    g = template["Globals"]["Function"]
    assert g["Runtime"] == "python3.12" and g["Architectures"] == ["arm64"]
    assert g["MemorySize"] == 512 and g["Tracing"] == "Active"
    env = g["Environment"]["Variables"]
    assert set(env) >= {
        "TABLE_WEATHER", "TABLE_SITES", "TABLE_PLANS", "TABLE_RECEIPTS", "SERVER_SECRET_PARAM",
        "POWERTOOLS_SERVICE_NAME", "LOG_LEVEL",
    }
    assert {spec.env for spec in store.TABLE_SPECS.values()} <= set(env)


FUNCTIONS = {
    "ApiFn": "handlers.api.handler",
    "RefreshFn": "handlers.refresh.handler",
    "ExplainFn": "handlers.explain.handler",
}


def test_every_handler_path_resolves_to_a_callable(template: dict[str, Any]) -> None:
    for name, handler in FUNCTIONS.items():
        props = template["Resources"][name]["Properties"]
        assert props["Handler"] == handler and props["CodeUri"] == "src/"
        module, attr = handler.rsplit(".", 1)
        assert callable(getattr(importlib.import_module(module), attr)), handler


def test_routes_match_the_api_contract(template: dict[str, Any]) -> None:
    def routes(fn: str) -> set[tuple[str, str]]:
        events = template["Resources"][fn]["Properties"]["Events"].values()
        for e in events:
            assert e["Type"] == "HttpApi"
            assert e["Properties"]["ApiId"] == {"Ref": "HttpApi"}
        return {(e["Properties"]["Method"], e["Properties"]["Path"]) for e in events}

    assert routes("ApiFn") == {
        ("POST", "/plan"), ("POST", "/sites"), ("GET", "/sites/{site_id}"),
        ("POST", "/receipts"), ("GET", "/receipts/{site_id}/{job_id}"),
        ("GET", "/leaderboard"), ("GET", "/assumptions"),
    }
    assert routes("ExplainFn") == {("POST", "/explain")}


def test_cors_and_throttling(template: dict[str, Any]) -> None:
    api = template["Resources"]["HttpApi"]["Properties"]
    cors = api["CorsConfiguration"]
    assert cors["AllowOrigins"] == {"Ref": "AllowedOrigins"} and "*" not in str(cors)
    assert set(cors["AllowMethods"]) == {"GET", "POST", "OPTIONS"}
    assert set(cors["AllowHeaders"]) == {
        "content-type", "x-thirst-timestamp", "x-thirst-signature", "x-thirst-site",
    }
    assert cors["MaxAge"] == 600
    limits = api["DefaultRouteSettings"]
    assert limits["ThrottlingRateLimit"] == 10 and limits["ThrottlingBurstLimit"] == 20


def test_refresh_runs_hourly_with_one_retry(template: dict[str, Any]) -> None:
    event = template["Resources"]["RefreshFn"]["Properties"]["Events"]["Hourly"]
    assert event["Type"] == "ScheduleV2"
    assert event["Properties"]["ScheduleExpression"] == "rate(1 hour)"
    assert event["Properties"]["RetryPolicy"]["MaximumRetryAttempts"] == 1


def policy_text(template: dict[str, Any], fn: str) -> str:
    return str(template["Resources"][fn]["Properties"]["Policies"])


def test_each_function_gets_only_the_tables_it_needs(template: dict[str, Any]) -> None:
    refresh = policy_text(template, "RefreshFn")
    assert "WeatherTbl" in refresh
    for other in ("SitesTbl", "PlansTbl", "ReceiptsTbl"):
        assert other not in refresh
    api = policy_text(template, "ApiFn")
    for table in ("WeatherTbl", "SitesTbl", "PlansTbl", "ReceiptsTbl"):
        assert table in api
    assert "bedrock" not in api.lower()  # only the explain function may call the model


def test_iam_has_no_wildcards_except_the_scoped_kms_grant(template: dict[str, Any]) -> None:
    for fn in FUNCTIONS:
        for policy in template["Resources"][fn]["Properties"]["Policies"]:
            for statement in policy.get("Statement", []) if isinstance(policy, dict) else []:
                resource = statement.get("Resource")
                if resource == "*":
                    assert statement["Action"] == "kms:Decrypt", (fn, statement)
                    assert "kms:ViaService" in str(statement["Condition"]), (fn, statement)
                assert "bedrock:*" not in str(statement.get("Action")), (fn, statement)


def test_the_secret_policy_is_scoped_to_the_one_parameter(template: dict[str, Any]) -> None:
    text = policy_text(template, "ApiFn")
    assert "ssm:GetParameter" in text and "ServerSecretParam" in text
    assert "ssm:*" not in text


def test_the_explain_function_has_the_layer_and_a_longer_timeout(template: dict[str, Any]) -> None:
    props = template["Resources"]["ExplainFn"]["Properties"]
    assert props["Timeout"] == 29 and props["Layers"] == [{"Ref": "StrandsLayer"}]
    layer = template["Resources"]["StrandsLayer"]
    assert layer["Type"] == "AWS::Serverless::LayerVersion"
    assert layer["Properties"]["CompatibleArchitectures"] == ["arm64"]
    assert (ROOT / layer["Properties"]["ContentUri"] / "requirements.txt").is_file()


def test_log_groups_keep_seven_days(template: dict[str, Any]) -> None:
    groups = resources(template, "AWS::Logs::LogGroup")
    assert len(groups) == 3
    assert all(g["Properties"]["RetentionInDays"] == 7 for g in groups.values())


def test_an_alarm_watches_api_errors(template: dict[str, Any]) -> None:
    (alarm,) = resources(template, "AWS::CloudWatch::Alarm").values()
    p = alarm["Properties"]
    assert p["MetricName"] == "Errors" and p["Namespace"] == "AWS/Lambda"
    assert p["Threshold"] == 5 and p["Period"] == 300 and p["EvaluationPeriods"] == 1
    assert p["AlarmActions"]


def test_nothing_on_the_never_create_list(template: dict[str, Any]) -> None:
    kinds = {r["Type"] for r in template["Resources"].values()}
    for forbidden in NEVER_CREATE:
        assert not [k for k in kinds if k.startswith(forbidden)], forbidden
    for fn in resources(template, "AWS::Serverless::Function").values():
        assert "ProvisionedConcurrencyConfig" not in fn["Properties"]
        assert "AutoPublishAliasAllProperties" not in fn["Properties"]


def test_outputs_publish_what_the_clients_need(template: dict[str, Any]) -> None:
    assert set(template["Outputs"]) >= {"ApiUrl", "StackRegion"}

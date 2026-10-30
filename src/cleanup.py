"""Expiração agendada exclusiva do Arena; não aceita alvos vindos de eventos."""
from datetime import datetime, timezone
import json
import os


def lambda_handler(event, context):
    targets=json.loads(os.environ["ARENA_CLEANUP_TARGETS"])
    assert targets["stack_name"]=="arena-vila-nova"
    assert targets["bucket"].startswith("arena-vila-nova-artifacts-")
    assert targets["parameter"]=="/arena-vila-nova/webhook-secret"
    assert targets["function"]=="arena-vila-nova-bot"
    if event.get("dry_run") is True:
        return {"validated":True,"expires_at":targets["expires_at"],"stack":targets["stack_name"]}
    if datetime.now(timezone.utc) < datetime.fromisoformat(targets["expires_at"]):
        raise ValueError("Expiração ainda não chegou")
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError
    session=boto3.Session(region_name="sa-east-1")
    config=Config(connect_timeout=3,read_timeout=15,retries={"total_max_attempts":2,"mode":"standard"})
    clients={name:session.client(name,config=config) for name in ("lambda","s3","ssm","cloudformation","scheduler","iam")}

    def missing_ok(operation, **kwargs):
        try:
            return operation(**kwargs)
        except ClientError as exc:
            if exc.response.get("Error",{}).get("Code") not in {
                "ResourceNotFoundException","ParameterNotFound","NoSuchBucket","NoSuchEntity","404"}:
                raise
            return None

    missing_ok(clients["lambda"].put_function_concurrency,FunctionName=targets["function"],ReservedConcurrentExecutions=0)
    missing_ok(clients["ssm"].delete_parameter,Name=targets["parameter"])
    try:
        for page in clients["s3"].get_paginator("list_object_versions").paginate(Bucket=targets["bucket"]):
            objects=[{"Key":v["Key"],"VersionId":v["VersionId"]} for k in ("Versions","DeleteMarkers") for v in page.get(k,[])]
            if objects:
                result=clients["s3"].delete_objects(Bucket=targets["bucket"],Delete={"Objects":objects,"Quiet":True})
                if result.get("Errors"): raise RuntimeError("Falha ao remover artefatos")
        clients["s3"].delete_bucket(Bucket=targets["bucket"])
    except clients["s3"].exceptions.NoSuchBucket:
        pass
    cfn=clients["cloudformation"]
    try:
        cfn.describe_stacks(StackName=targets["stack_name"])
    except ClientError as exc:
        if "does not exist" not in exc.response.get("Error",{}).get("Message",""): raise
    else:
        cfn.delete_stack(StackName=targets["stack_name"])
        cfn.get_waiter("stack_delete_complete").wait(StackName=targets["stack_name"],WaiterConfig={"Delay":5,"MaxAttempts":45})
    missing_ok(clients["scheduler"].delete_schedule,Name=targets["schedule"],GroupName="default")
    iam=clients["iam"]
    missing_ok(iam.delete_role_policy,RoleName=targets["scheduler_role"],PolicyName="arena-expiry-invoke")
    missing_ok(iam.delete_role,RoleName=targets["scheduler_role"])
    missing_ok(clients["lambda"].delete_function,FunctionName=targets["cleanup_function"])
    # Desautorizar a própria role ao final. Role IAM vazia não gera cobrança.
    missing_ok(iam.delete_role_policy,RoleName=targets["cleanup_role"],PolicyName="arena-expiry-cleanup")
    try:
        missing_ok(iam.delete_role,RoleName=targets["cleanup_role"])
    except ClientError as exc:
        if exc.response.get("Error",{}).get("Code") != "AccessDenied": raise
    return {"deleted":True}

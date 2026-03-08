"""
Tag all resources created for an agent by the Bedrock AgentCore starter toolkit.
"""

import logging

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

AGENTCORE_AGENT_NAME = "TestAgent"
TAGS = {
    "Project": "TestProject",
    "AppName": "TestAppName",
    "CreatedBy": "BedrockAgentCoreStarterToolkit",
}
ACCOUNT_ID = "123456789012"
PROFILE = None
REGION = "us-east-1"

S3_BUCKET_NAME = f"bedrock-agentcore-codebuild-sources-{ACCOUNT_ID}-{REGION}"
ECR_REPO_NAME = f"bedrock-agentcore-{AGENTCORE_AGENT_NAME.lower()}"
CODEBUILD_PROJECT_NAME = f"bedrock-agentcore-{AGENTCORE_AGENT_NAME.lower()}-builder"
AGENTCORE_MEMORY_PREFIX = f"{AGENTCORE_AGENT_NAME}_mem-"

session = boto3.Session(profile_name=PROFILE, region_name=REGION)
s3 = session.client("s3")
ecr = session.client("ecr")
codebuild = session.client("codebuild")
agentcore = session.client("bedrock-agentcore-control")


def tag_s3_bucket() -> None:
    s3.put_bucket_tagging(
        Bucket=S3_BUCKET_NAME,
        Tagging={
            "TagSet": [{"Key": key, "Value": value} for key, value in TAGS.items()]
        },
    )


def tag_ecr_repo() -> None:
    repo_arn = f"arn:aws:ecr:{REGION}:{ACCOUNT_ID}:repository/{ECR_REPO_NAME}"
    ecr.tag_resource(
        resourceArn=repo_arn,
        tags=[{"Key": key, "Value": value} for key, value in TAGS.items()],
    )


def tag_codebuild_project() -> None:
    codebuild.update_project(
        name=CODEBUILD_PROJECT_NAME,
        tags=[{"key": key, "value": value} for key, value in TAGS.items()],
    )


def tag_agentcore_runtime() -> str:
    """Tag the AgentCore runtime and return the runtime ARN."""
    runtime_arn = None
    pages = agentcore.get_paginator("list_agent_runtimes").paginate()
    for page in pages:
        if runtime_arn is not None:
            break

        for runtime in page["agentRuntimes"]:
            if runtime["agentRuntimeName"] == AGENTCORE_AGENT_NAME:
                runtime_arn = runtime["agentRuntimeArn"]
                break

    if runtime_arn is None:
        raise RuntimeError(f"AgentCore runtime not found for {AGENTCORE_AGENT_NAME}.")

    agentcore.tag_resource(
        resourceArn=runtime_arn,
        tags=TAGS,
    )

    return runtime_arn


def tag_agentcore_endpoint(runtime_arn: str) -> None:
    endpoint_arn = f"{runtime_arn}/runtime-endpoint/DEFAULT"
    agentcore.tag_resource(
        resourceArn=endpoint_arn,
        tags=TAGS,
    )


def tag_agentcore_memories() -> None:
    memory_arns = []
    pages = agentcore.get_paginator("list_memories").paginate()
    for page in pages:
        for memory in page["memories"]:
            if "id" not in memory or "arn" not in memory:
                logger.warning(f"⚠️ Skipping memory with missing id or arn: {memory}")
                continue

            if memory["id"].startswith(AGENTCORE_MEMORY_PREFIX):
                memory_arns.append(memory["arn"])

    for memory_arn in memory_arns:
        try:
            # NOTE: Memory tag values incorrectly appear lowercase in the AWS console.
            agentcore.tag_resource(
                resourceArn=memory_arn,
                tags=TAGS,
            )
        except ClientError as error:
            logger.error(f"❌ Error tagging memory: {error}", exc_info=True)


def main() -> None:
    try:
        tag_s3_bucket()
        logger.info(f"🪣 Tagged S3 bucket {S3_BUCKET_NAME}.")

        tag_ecr_repo()
        logger.info(f"🐋 Tagged ECR repository {ECR_REPO_NAME}.")

        tag_codebuild_project()
        logger.info(f"🏗️ Tagged CodeBuild project {CODEBUILD_PROJECT_NAME}.")

        runtime_arn = tag_agentcore_runtime()
        logger.info(f"🤖 Tagged AgentCore runtime {AGENTCORE_AGENT_NAME}.")

        tag_agentcore_endpoint(runtime_arn)
        logger.info(f"📡 Tagged AgentCore default endpoint.")

        tag_agentcore_memories()
        logger.info(f"🧠 Tagged AgentCore memories {AGENTCORE_MEMORY_PREFIX}*.")
    except Exception as error:
        logger.error(f"❌ {error.__class__.__name__}: {error}", exc_info=True)


if __name__ == "__main__":
    main()

"""S3 version-aware operations. Grants reference public endpoint; workers use private endpoint."""

import base64
from typing import Any

import boto3
from botocore.config import Config

from workbench.platform.config import Settings


class ObjectStorage:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        common = {
            "region_name": settings.s3_region,
            "aws_access_key_id": settings.s3_access_key.get_secret_value(),
            "aws_secret_access_key": settings.s3_secret_key.get_secret_value(),
            "config": Config(
                signature_version="s3v4",
                retries={"max_attempts": 2},
                connect_timeout=3,
                read_timeout=15,
            ),
        }
        self.client = boto3.client("s3", endpoint_url=settings.s3_endpoint, **common)
        self.signer = boto3.client("s3", endpoint_url=settings.s3_public_endpoint, **common)
        self.quarantine, self.clean, self.reports = settings.s3_buckets

    def head(
        self, key: str, version: str | None = None, bucket: str | None = None
    ) -> dict[str, Any]:
        args: dict[str, Any] = {"Bucket": bucket or self.quarantine, "Key": key}
        if version:
            args["VersionId"] = version
        return dict(self.client.head_object(**args))

    def read(
        self, key: str, version: str, bucket: str, start: int = 0, end: int | None = None
    ) -> Any:
        args: dict[str, Any] = {"Bucket": bucket, "Key": key, "VersionId": version}
        if start or end is not None:
            args["Range"] = f"bytes={start}-" + (str(end) if end is not None else "")
        return self.client.get_object(**args)["Body"]

    def grant(self, upload: dict[str, Any], expires: int) -> dict[str, Any]:
        params = {
            "Bucket": self.quarantine,
            "Key": upload["object_key"],
            "ContentType": upload["media_type"],
            "ContentLength": upload["expected_size"],
            "ChecksumSHA256": base64.b64encode(bytes.fromhex(upload["expected_sha256"])).decode(),
        }
        return {
            "method": "PUT",
            "url": self.signer.generate_presigned_url(
                "put_object", Params=params, ExpiresIn=expires
            ),
            "headers": {
                "Content-Type": upload["media_type"],
                "x-amz-checksum-sha256": params["ChecksumSHA256"],
            },
            "expires_in_seconds": expires,
        }

    def initiate_multipart(self, key: str, media_type: str) -> str:
        return str(
            self.client.create_multipart_upload(
                Bucket=self.quarantine, Key=key, ContentType=media_type
            )["UploadId"]
        )

    def part_grant(
        self, upload: dict[str, Any], number: int, size: int, expires: int
    ) -> dict[str, Any]:
        url = self.signer.generate_presigned_url(
            "upload_part",
            Params={
                "Bucket": self.quarantine,
                "Key": upload["object_key"],
                "UploadId": upload["multipart_id"],
                "PartNumber": number,
                "ContentLength": size,
            },
            ExpiresIn=expires,
        )
        return {
            "method": "PUT",
            "url": url,
            "headers": {},
            "size_bytes": size,
            "part_number": number,
            "expires_in_seconds": expires,
        }

    def parts(self, upload: dict[str, Any]) -> list[dict[str, Any]]:
        result = []
        paginator = self.client.get_paginator("list_parts")
        for page in paginator.paginate(
            Bucket=self.quarantine, Key=upload["object_key"], UploadId=upload["multipart_id"]
        ):
            result.extend(page.get("Parts", []))
        return result

    def finish_multipart(self, upload: dict[str, Any], parts: list[dict[str, Any]]) -> str:
        result = self.client.complete_multipart_upload(
            Bucket=self.quarantine,
            Key=upload["object_key"],
            UploadId=upload["multipart_id"],
            MultipartUpload={
                "Parts": [{"PartNumber": p["PartNumber"], "ETag": p["ETag"]} for p in parts]
            },
        )
        return str(result["VersionId"])

    def copy_clean(self, upload: dict[str, Any], key: str) -> str:
        result = self.client.copy_object(
            Bucket=self.clean,
            Key=key,
            CopySource={
                "Bucket": self.quarantine,
                "Key": upload["quarantine_key"],
                "VersionId": upload["quarantine_version"],
            },
            ServerSideEncryption="AES256",
            MetadataDirective="REPLACE",
            Metadata={"sha256": upload["sha256"]},
        )
        return str(result["VersionId"])

    def delete(self, key: str, bucket: str | None = None, version: str | None = None) -> None:
        args: dict[str, Any] = {"Bucket": bucket or self.clean, "Key": key}
        if version:
            args["VersionId"] = version
        self.client.delete_object(**args)

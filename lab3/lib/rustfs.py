import boto3
import duckdb
from botocore.client import Config

from lib import config


def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=config.S3_ENDPOINT,
        aws_access_key_id=config.S3_ACCESS_KEY,
        aws_secret_access_key=config.S3_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name=config.S3_REGION,
    )


def duckdb_s3():
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    host = config.S3_ENDPOINT.replace("http://", "").replace("https://", "")
    con.execute(f"""
    CREATE OR REPLACE SECRET rustfs (
      TYPE s3,
      KEY_ID '{config.S3_ACCESS_KEY}',
      SECRET '{config.S3_SECRET_KEY}',
      REGION '{config.S3_REGION}',
      ENDPOINT '{host}',
      URL_STYLE 'path',
      USE_SSL false
    );
    """)
    return con

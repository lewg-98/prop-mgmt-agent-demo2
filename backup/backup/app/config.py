import os
from dotenv import load_dotenv
from functools import lru_cache
from typing import Dict

load_dotenv()

@lru_cache()
def get_settings() -> Dict:
    return {
        "db_config": {
            "dbname": os.getenv("DB_NAME"),
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD"),
            "host": os.getenv("DB_HOST"),
            "port": os.getenv("DB_PORT", "5432")
        },
        "aws_config": {
            "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
            "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
            "region_name": os.getenv("AWS_REGION", "us-east-1"),
            "bucket": os.getenv("S3_BUCKET")
        },
        "email_config": {
            "host": os.getenv("SMTP_HOST"),
            "port": int(os.getenv("SMTP_PORT", "587")),
            "user": os.getenv("SMTP_USER"),
            "password": os.getenv("SMTP_PASSWORD"),
            "sender": os.getenv("SMTP_SENDER")
        },
        "openai_config": {
            "api_key": os.getenv("OPENAI_API_KEY"),
            "model": os.getenv("OPENAI_MODEL", "gpt-4")
        }
    }
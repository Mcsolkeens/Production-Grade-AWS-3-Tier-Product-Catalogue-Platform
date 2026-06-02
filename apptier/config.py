import boto3
import json
import os

def get_db_config():
    """
    Fetches database credentials from AWS Secrets Manager.
    The EC2 IAM role grants access — no keys needed.
    """
    client = boto3.client(
        'secretsmanager',
        region_name=os.environ.get('AWS_REGION', 'us-east-1')
    )

    secret = client.get_secret_value(
        SecretId='prod/aurora/credentials'
    )

    creds = json.loads(secret['SecretString'])

    return {
        'username': creds['username'],
        'password': creds['password'],
        'dbname':   creds['dbname'],
        # Writer endpoint — for INSERT, UPDATE, DELETE
        'writer_host': os.environ.get('DB_WRITER_HOST', ''),
        # Reader endpoint — for SELECT queries (offloads reads to replica)
        'reader_host': os.environ.get('DB_READER_HOST', ''),
    }



    # Replace YOUR_WRITER_ENDPOINT with the actual value from Phase 1 Step 3
export DB_WRITER_HOST="database-1.cluster-c6zuw62io7is.us-east-1.rds.amazonaws.com"
echo "DB_WRITER_HOST=$DB_WRITER_HOST" | sudo tee -a /etc/environment
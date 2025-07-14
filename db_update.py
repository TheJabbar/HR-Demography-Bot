import httpx  # Replaced requests with httpx
import os
import json
from minio import Minio
from datetime import datetime
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential
from loguru import logger

load_dotenv('.env', override=True)

# Configuration
DATA_API_URL = os.getenv('DATA_API_URL')
BEARER_TOKEN = os.getenv('BEARER_TOKEN')
DATA_DIR = "/data/"
# Set Up Minio Keys
minio_endpoint = os.getenv("MINIO_ENDPOINT")
minio_bucket = os.getenv("MINIO_BUCKET")
minio_prefix = os.getenv("MINIO_PREFIX")
minio_access_key = os.getenv("MINIO_ACCESS_KEY")
minio_secret_key = os.getenv("MINIO_SECRET_KEY")

def get_previous_year_month():
    now = datetime.now()
    if now.day > 10:
        adjusted = now - relativedelta(months=1)
    else:
        adjusted = now - relativedelta(months=2)
    
    return adjusted.year, adjusted.strftime("%m")

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=60))
def fetch_api_data(year, month, consol):
    # Generate filename based on input parameters
    filename = f"HCM_Insight_{year}_{month}_{consol}.json"
    file_path = os.path.join("/data", filename)

    # Check if the file already exists
    if os.path.exists(file_path):
        logger.info(f"File {filename} already exists in /data. Skipping API call.")
        return None  # Return None to indicate that no new data was fetched

    try:
        # Build the API URL and headers
        url = f"{DATA_API_URL}?n_tahun={year}&n_bulan={month}&limit=13000&v_consolidated={consol}"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {BEARER_TOKEN}"
        }

        # Make the API request
        response = httpx.get(url, headers=headers, timeout=httpx.Timeout(10.0, read=30.0))
        response.raise_for_status()  # Raises exception for HTTP errors

        # Parse JSON response
        json_response = response.json()

        # Validate API response status
        if json_response.get('status') != 'success':
            raise ValueError(f"API returned status: {json_response.get('status')}")

        # Return the data from the API
        return json_response.get('data', [])

    except httpx.RequestError as e:
        logger.error(f"Network/HTTP error: {e}")
        raise  # Re-raise to trigger retry or external handling

    except Exception as e:
        logger.error(f"Validation error: {e}")
        raise  # Re-raise to trigger retry or external handling

def save_to_json(data, year, month, consol):
    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Create filename with year and month
    filename = f"HCM_Insight_{year}_{month}_{consol}.json"
    file_path = os.path.join(DATA_DIR, filename)
    
    # Write JSON data to file
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)
    print(f"Data saved to {file_path}")
    
    return file_path

def download_minio_data():
    """
    Download all files from a MinIO bucket prefix to a local folder.
    """

    # Initialize MinIO client
    client = Minio(
        minio_endpoint,
        access_key=minio_access_key,
        secret_key=minio_secret_key,
        secure=True  # Use HTTPS
    )
    
    local_folder = '/data'
    overwrite = False
    
    logger.info(f"Minio Download started from endpoint '{minio_endpoint}' for bucket '{minio_bucket}' with prefix '{minio_prefix}'.")
    
    try:
        # List objects recursively under the prefix
        objects = list(client.list_objects(minio_bucket, prefix=minio_prefix, recursive=True))
        logger.info(f"Found {len(objects)} objects under prefix '{minio_prefix}' in bucket '{minio_bucket}'.")

        if not objects:
            logger.warning("No objects found to download.")
            return

        for obj in objects:
            # Skip directories
            if obj.is_dir:
                logger.debug(f"Skipping directory: {obj.object_name}")
                continue

            # Build local file path
            relative_path = obj.object_name[len(minio_prefix):]
            local_file_path = os.path.join(local_folder, relative_path.lstrip('/'))  # Avoid leading slashes

            # Check if file already exists
            if os.path.exists(local_file_path):
                local_size = os.path.getsize(local_file_path)
                remote_size = obj.size

                if local_size == remote_size and not overwrite:
                    print(f"⏭️ Skipping (already exists and same size): {local_file_path}")
                    continue
                elif overwrite:
                    print(f"🔁 Overwriting file: {local_file_path}")
                else:
                    print(f"⚠️ File size differs. Re-downloading: {local_file_path}")

            # Create parent directory if needed
            os.makedirs(os.path.dirname(local_file_path), exist_ok=True)

            # Download the file
            print(f"📥 Downloading {obj.object_name} → {local_file_path}")
            client.fget_object(minio_bucket, obj.object_name, local_file_path)

        print("✅ All files processed.")

    except Exception as e:
        print(f"❌ Error downloading files: {e}")
        logger.exception("Exception occurred during MinIO download.")
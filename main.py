import os
import sys
import time
import sqlite3
import pandas as pd
import glob
from datetime import datetime, timedelta, date
from fastapi import FastAPI, Depends, Security, HTTPException, Response
from fastapi.security.api_key import APIKey, APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from starlette.status import HTTP_403_FORBIDDEN
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import warnings
from secure import Secure
from loguru import logger
from lib.prompt import generate_sql_prompt, generate_insight_prompt, sql_fix_prompt
from llm_engine import telkomllm_generate_sql, telkomllm_infer_sql, telkomllm_fix_sql
from db_update import fetch_api_data, save_to_json, download_minio_data

# Load environment variables and suppress unimportant warnings
load_dotenv('.env', override=True)
warnings.filterwarnings("ignore", category=UserWarning)

# Set up API key security
ACCESS_KEY = os.getenv('X_API_KEY')
API_KEY_HEADER = APIKeyHeader(name="x-api-key", auto_error=True)

secure_headers = Secure.with_default_headers()
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request, call_next):
        response: Response = await call_next(request)
        await secure_headers.set_headers_async(response)
        response.headers['Cross-Origin-Embedder-Policy'] = 'require-corp'
        response.headers['Cross-Origin-Resource-Policy'] = 'same-origin'
        response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
        response.headers["X-DAG-AI-SERVER"] = "OK"
        return response


# Set Up Minio Keys
minio_access_key = os.getenv("MINIO_ACCESS_KEY")
minio_secret_key = os.getenv("MINIO_SECRET_KEY")

async def get_api_key(api_key_header: str = Security(API_KEY_HEADER)):
    if api_key_header == ACCESS_KEY:
        return api_key_header
    else:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail="Could not validate API KEY"
        )

# Initialize logger
logger.add(sys.stderr, level="TRACE")
logger.add(sys.stderr, format="{time} | {level} | {message}")
logger.add("log/HCM Insight bot.log", rotation="1 hour")

# Initialize FastAPI app with CORS settings
app = FastAPI(
    title='HCM INSIGHT GENERATOR BOT',
    description='HCM INSIGHT GENERATOR bot services using FastAPI',
    version='0.1',
    docs_url=None,
    redoc_url=None
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=["DELETE", "GET", "POST", "PUT"],
    allow_headers=["*"],
)

# Configuration constants
TABLE_NAME = "employee_demography"
DATABASE_API = "/app/data/HCM_Insight_API.db"

class QueryInput(BaseModel):
    query: str

class ChatResponse(BaseModel):
    output: str

def process_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Standard processing for dataframes containing 'n_usia' column"""
    df['n_usia'] = pd.to_numeric(df['n_usia'], errors='coerce')
    df['n_usia'] = df['n_usia'].fillna(-1).astype(int)
    df['n_usia'] = df['n_usia'].round().astype(int)
    return df

def generate_year_month_combinations(start_date: str) -> list:
    """Generate year/month combinations from start date to last completed month"""
    start = datetime.strptime(start_date, "%Y %m")
    now = datetime.now()
    end = datetime(now.year, now.month, 1) - timedelta(days=1)
    end = datetime(end.year, end.month, 1)
    
    result = []
    current = start
    while current <= end:
        result.append(current.strftime("%Y %m"))
        if current.month == 12:
            current = datetime(current.year + 1, 1, 1)
        else:
            current = datetime(current.year, current.month + 1, 1)
    return result

def get_previous_month():
    today = date.today()
    current_year = today.year
    current_month = today.month

    if current_month == 1:
        prev_month = 12
        prev_year = current_year - 1
    else:
        prev_month = current_month - 2
        prev_year = current_year

    # Create a date object for the first day of the previous month
    previous_date = date(prev_year, prev_month, 1)    
    return previous_date.strftime("%B %Y").split()


def insert_api_data_to_db(file_path: str, db_path: str, table_name: str) -> None:
    """
    Reads all JSON files from the specified directory, processes them,
    concatenates into a single DataFrame, and saves the result into a SQLite database.
    If no files are found initially, the function will recheck every 30 seconds until files are found.

    Args:
        file_path (str): Path to the directory containing JSON files.
        db_path (str): Path to the SQLite database file to be created.
        table_name (str): Name of the table in the SQLite database.
    """
    dataframes = []

    try:
        logger.debug(f"Start api_data_to_db: {file_path}")

        # Wait until at least one JSON file is found
        while True:
            json_files = glob.glob(os.path.join(file_path, "*.json"))

            if json_files:
                break

            logger.warning(f"No JSON files found in directory: {file_path}. Rechecking in 30 seconds...")
            time.sleep(30)

        # Process each JSON file
        for file in json_files:
            try:
                df = pd.read_json(file, encoding='latin1')
                df = process_dataframe(df)  # Assume this function is defined elsewhere
                dataframes.append(df)
            except Exception as e:
                logger.error(f"Failed to process file {file}: {e}")

        # Combine all processed DataFrames
        final_df = pd.concat(dataframes, ignore_index=True) if dataframes else pd.DataFrame()

        if not final_df.empty:
            # Ensure the directory for the database exists
            os.makedirs(os.path.dirname(db_path), exist_ok=True)

            # Save to SQLite database
            with sqlite3.connect(db_path) as conn:
                final_df.to_sql(table_name, conn, if_exists='replace', index=False)

            logger.info(f"Data successfully inserted into {db_path} from {len(json_files)} JSON files.")
        else:
            logger.warning("No valid data found to insert into the database.")

    except Exception as e:
        logger.error(f"Failed to insert API data into database: {e}")
        raise HTTPException(status_code=500, detail="API data processing error")

def startup_event():
    # API data loading is now async
    try:
        logger.info("Starting up HCM Insight Dashboard. Loading initial API data...")
        insert_api_data_to_db(
            file_path="/app/data",
            table_name=TABLE_NAME,
            db_path=DATABASE_API
        )
    except Exception as e:
        logger.error(f"Initial API data load failed: {e}")

async def lifespan(app: FastAPI):
    # Startup logic
    startup_event()
    yield  # Required to separate startup and shutdown phases

# Attach the lifespan to the app
app = FastAPI(lifespan=lifespan)

# API endpoints
@app.post("/HCM_Insight/get_insight_api", response_model=ChatResponse, tags=["Insights"])
async def get_insight_api(
    input_data: QueryInput,
    x_api_key: APIKey = Depends(get_api_key)
):
    try:
        conn = sqlite3.connect(DATABASE_API)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({TABLE_NAME})")
        columns_info = cursor.fetchall()
        conn.close()
    except Exception as e:
        logger.error(f"Error retrieving table info: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving table info")

    if not columns_info:
        raise HTTPException(status_code=404, detail="Table not found")

    column_list = [col[1] for col in columns_info]
    
    try:
        prev_month = get_previous_month()
        month, year = prev_month[0], prev_month[1]
        generated_sql = await telkomllm_generate_sql(
            prompt = generate_sql_prompt, 
            table_name = TABLE_NAME, 
            columns_list = column_list, 
            month = month,
            year = year,
            user_query = input_data.query
        )
        logger.debug(f"Generated SQL: {generated_sql}")
    except Exception as e:
        logger.error(f"LLM API call failed: {e}")
        raise HTTPException(status_code=500, detail="LLM API call failed")

    try:
        conn = sqlite3.connect(DATABASE_API)
        cursor = conn.cursor()
        cursor.execute(generated_sql)
        rows = cursor.fetchall()
        logger.debug(f"Data Rows: {rows}")
        conn.close()
    except Exception as e:
        try:
            error_sql = generated_sql
            error_message = str(e)
            generated_sql = await telkomllm_fix_sql(
                sql_fix_prompt, 
                error_sql, 
                error_message
            )
            conn = sqlite3.connect(DATABASE_API)
            cursor = conn.cursor()
            cursor.execute(generated_sql)
            rows = cursor.fetchall()
            logger.debug(f"Data Rows: {rows}")
            conn.close()
        except Exception as E:
            logger.error(f"SQL execution failed: {E}")
            raise HTTPException(status_code=500, detail=f"SQL execution failed: {E}")

    insight = await telkomllm_infer_sql(
        prompt = generate_insight_prompt, 
            table_name = TABLE_NAME, 
            columns_list = column_list,
            table_data=rows,
            month = month,
            year = year,
            user_query = input_data.query
    )
    logger.info(f"Generated Insight: {insight}")
    return ChatResponse(output=insight)

@app.get("/HCM_Insight/get_data_update", tags=["Data Update"])
async def get_new_data():
    download_minio_data()
    start_date = "2022 05"  # Starting from May 2022
    consol_list=["CONSOLIDATED", "UNCONSOLIDATED", "TELKOMSEL"]
    year_month_list = generate_year_month_combinations(start_date)
    list_data = []
    for year_month in year_month_list:
        year, month = year_month.split()
        for consol in consol_list:
            api_data = fetch_api_data(year, month, consol)
            if api_data is None:
                logger.info(f"Data for {year} {month} {consol} already exists. Skipping API call.")
                continue
            else:
                file_path = save_to_json(api_data, year, month, consol)
                list_data.append(file_path)
                logger.info(f"API Data {file_path} fetched successfully")
    return {"message": "Data update completed", "files": list_data}


@app.get("/ht", tags=["Health"])
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=7799, workers=5)
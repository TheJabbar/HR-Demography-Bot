import os
import httpx
from dotenv import load_dotenv

load_dotenv('.env')

URL_CUSTOM_LLM_APILOGY = os.getenv('URL_CUSTOM_LLM')
TOKEN_CUSTOM_LLM_APILOGY = os.getenv('TOKEN_CUSTOM_LLM')

URL_CUSTOM_LLM_K3S = os.getenv('URL_CUSTOM_LLM')
TOKEN_CUSTOM_LLM_K3S = os.getenv('TOKEN_CUSTOM_LLM')


async def make_async_api_call(url, token, payload):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "x-api-key": token
    }
    async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
            else:
                error_message = response.text
                print(f"API Error {response.status_code}: {error_message}")
                return {"error": f"API call failed with status {response.status_code}"}
        except Exception as e:
            print(f"Exception during API call: {e}")
            return {"error": str(e)}


async def telkomllm_generate_sql(prompt, table_name, columns_list, month, year, user_query):
    url = URL_CUSTOM_LLM_APILOGY
    token = TOKEN_CUSTOM_LLM_APILOGY
    payload = {
        "model": "telkom-ai-instruct",
        "messages": [
            {
                "role": "system",
                "content": prompt.format(
                    table_name=table_name,
                    columns_list=columns_list,
                    month=month,
                    year=year
                )
            },
            {
                "role": "user",
                "content": user_query
            }
        ],
        "max_tokens": 5000,
        "temperature": 0,
        "stream": False
    }

    result = await make_async_api_call(url, token, payload)
    if isinstance(result, dict) and "error" in result:
        # Fallback to secondary endpoint
        result = await make_async_api_call(URL_CUSTOM_LLM_K3S, TOKEN_CUSTOM_LLM_K3S, payload)
    return result


async def telkomllm_infer_sql(prompt, user_query, table_name, columns_list, table_data, year, month):
    url = URL_CUSTOM_LLM_APILOGY
    token = TOKEN_CUSTOM_LLM_APILOGY
    payload = {
        "model": "telkom-ai-instruct",
        "messages": [
            {
                "role": "system",
                "content": prompt.format(
                    table_name=table_name,
                    columns_list=columns_list,
                    table_data=table_data,
                    year=year,
                    month=month,
                    user_query=user_query
                ),
            },
            {
                "role": "user",
                "content": user_query
            }
        ],
        "max_tokens": 28000,
        "temperature": 0,
        "stream": False
    }

    result = await make_async_api_call(url, token, payload)
    if isinstance(result, dict) and "error" in result:
        # Fallback to secondary endpoint
        result = await make_async_api_call(URL_CUSTOM_LLM_K3S, TOKEN_CUSTOM_LLM_K3S, payload)
    return result


async def telkomllm_fix_sql(prompt, error_sql, error_message):
    url = URL_CUSTOM_LLM_APILOGY
    token = TOKEN_CUSTOM_LLM_APILOGY
    payload = {
        "model": "telkom-ai-instruct",
        "messages": [
            {
                "role": "system",
                "content": prompt.format(
                    error_sql=error_sql,
                    error_message=error_message
                ),
            }
        ],
        "max_tokens": 5000,
        "temperature": 0,
        "stream": False
    }

    result = await make_async_api_call(url, token, payload)
    if isinstance(result, dict) and "error" in result:
        # Fallback to secondary endpoint
        result = await make_async_api_call(URL_CUSTOM_LLM_K3S, TOKEN_CUSTOM_LLM_K3S, payload)
    return result
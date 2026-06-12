import requests
import time
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

def call_groq_api(payload):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    
    max_retries = 3
    backoff_delays = [1, 2, 4]  # Delays in seconds
    
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            # Catch HTTP errors
            response.raise_for_status()
            
            # Successful response
            return {
                "success": True,
                "response": response.json(),
                "error": None
            }
            
        except requests.exceptions.HTTPError as http_err:
            status_code = http_err.response.status_code
            logger.error(f"HTTP error occurred on attempt {attempt + 1}: {http_err} (Status: {status_code})")
            
            # Skip retries if error is client-side (4xx)
            if 400 <= status_code < 500:
                return {
                    "success": False,
                    "response": None,
                    "error": f"Client-side HTTP error: {http_err}"
                }
                
            # If 5xx, we can retry if we haven't exceeded max_retries
            if attempt < max_retries:
                delay = backoff_delays[attempt]
                logger.info(f"Retrying after 5xx error in {delay}s...")
                time.sleep(delay)
            else:
                return {
                    "success": False,
                    "response": None,
                    "error": f"HTTP error after retries: {http_err}"
                }
                
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as conn_err:
            logger.error(f"Timeout/Connection error on attempt {attempt + 1}: {conn_err}")
            
            # Retry on timeout/connection issue
            if attempt < max_retries:
                delay = backoff_delays[attempt]
                logger.info(f"Retrying after connection/timeout error in {delay}s...")
                time.sleep(delay)
            else:
                return {
                    "success": False,
                    "response": None,
                    "error": f"Connection/Timeout error after retries: {conn_err}"
                }
                
        except Exception as e:
            logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
            return {
                "success": False,
                "response": None,
                "error": str(e)
            }

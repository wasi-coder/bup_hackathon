import os

import uvicorn
from dotenv import load_dotenv

load_dotenv()
uvicorn.run("gridwise.api:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")),
            log_level="warning", access_log=False)

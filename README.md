# GridWise Energy Optimizer

A smart-campus energy optimization system powered by a large language model (LLM) and linear programming.

## Running Locally

### 1. Requirements

- Python 3.10+
- An API key from Groq (for the LLM interpreter)

### 2. Setup

Clone the repository and install dependencies:

```bash
pip install -r requirements.txt
```

Create your environment configuration:

```bash
cp .env.example .env
```

Open `.env` and add your Groq API key:

```env
GROQ_API_KEY=gsk_your_api_key_here
```

### 3. Start the Server

Start the FastAPI application:

```bash
python -m start
```

The server will run at `http://127.0.0.1:8000`.

### 4. Test the API

You can check if the server is running by hitting the health check endpoint:

```bash
curl http://127.0.0.1:8000/health
```

---

## Running via Docker Archive (Fallback)

For offline deployment or evaluation, you can load and run the provided Docker archive (`dockerImage.tar`).

### 1. Load the Image

Load the image into your local Docker instance:

```bash
docker load -i dockerImage.tar
```

### 2. Run the Container

Run the loaded container, injecting your Groq API key:

```bash
docker run -p 8000:8000 -e GROQ_API_KEY="gsk_your_api_key_here" gridwise-fallback
```

The server will now be accessible at `http://127.0.0.1:8000`.

---

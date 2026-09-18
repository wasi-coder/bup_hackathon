# Prerequisites

You must have [Docker](https://docs.docker.com/get-docker/) installed and running on your machine.

## Step 1: Build the Docker Image

Open your terminal in the root directory of this project (where the `Dockerfile` is located) and run the following command. This will build a local Docker image named `gridwise-fallback`.

```bash
docker build -t gridwise-fallback .
```

### Step 2: Export to a `.tar` Archive

Once the image is successfully built, you can export it into a single portable file using the `docker save` command.

```bash
docker save -o dockerImage.tar gridwise-fallback
```

This will create a new file named **`dockerImage.tar`** in your current directory.

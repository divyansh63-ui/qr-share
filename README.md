# QR Share Public

## Local run
pip install -r requirements.txt
python app.py

## Deploy to Render
1. Create a GitHub repository and upload these files.
2. On Render, create a new Web Service and connect the repository.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`
5. Add environment variable `SECRET_KEY` with a long random value.

## Important production note
This starter stores uploads and SQLite data on the server filesystem. On many cloud hosts, local storage is ephemeral. For a serious public service, use persistent object storage (Cloudflare R2/S3) and a managed database.

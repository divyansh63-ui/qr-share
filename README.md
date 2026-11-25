# QuickDrop

QuickDrop is a lightweight web application for sharing files between phones and computers using a QR code, a shareable link, or a Room ID.

## Sharing options
- **QR code:** Scan the room QR code with another device's camera.
- **Link:** Copy the direct room URL or use the device's native Share menu.
- **Room ID:** Copy the ID and enter it in the Join with Room ID section on the homepage.
- **Optional password:** Rooms can be protected with a password.
- **Expiry:** Choose a room lifetime from 1 hour up to 7 days.

## Technology
- Python and Flask — backend and routes
- HTML, CSS, JavaScript — user interface and browser interactions
- SQLite — room and file metadata
- `qrcode` — QR code generation
- Gunicorn — production WSGI server
- Render — hosting platform

## Run locally
```bash
pip install -r requirements.txt
python app.py
```
Open `http://127.0.0.1:5000`.

## Deploy to Render
1. Push this project to GitHub.
2. Create a Render Web Service connected to the repository.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`
5. Set a long random `SECRET_KEY` environment variable.

## Storage note
This project stores uploaded files and SQLite data on the server filesystem. On cloud hosts, local storage may be ephemeral. For durable production storage, configure a persistent disk or object storage and a managed database.

## Security note
Password-protected rooms require the room password for room access, file listing, uploads, downloads, and deletion. Use HTTPS in deployment. This is a starter project, not an end-to-end encrypted storage service.

import os
import threading

from db import init_db
from bot import run_polling
from webapp import app

if __name__ == "__main__":
    init_db()
    threading.Thread(target=run_polling, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

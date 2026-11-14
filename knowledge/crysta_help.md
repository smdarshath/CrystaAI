# Using Crysta AI

Start Crysta with `python3 run.py` (Windows: `py run.py`) and open http://localhost:8765. Press the microphone button (or the Space bar) to talk. Press T or / to open the typing chat. Press Esc to go back home.

# Running a local web app or website

To run a simple static website, open a terminal in the project folder and run `python3 -m http.server 8000`, then visit http://localhost:8000. For a Node project, run `npm install` once, then `npm run dev` or `npm start`; the terminal prints the local address. For a Python project, create a virtual environment with `python3 -m venv .venv`, activate it, run `pip install -r requirements.txt`, then start the main script. If a port is already in use, choose another port instead of killing unknown programs.

# Offline behaviour

Without internet Crysta can calculate, convert units, search its bundled knowledge and your saved notes, manage tasks, open apps, list approved folders, run approved commands and check system health. Web research and YouTube need internet. Open-ended answers and code writing need a local language model such as Ollama.

# Privacy

Memory is off by default. When on, memories, notes and chat history are stored in data/crysta.db on this computer only. You can view, export and delete them in Settings. Browser speech recognition in Chrome or Edge may send audio to the browser vendor's servers; Crysta itself never records in the background.

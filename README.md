# Food Pantry Web-Based
A web application that connects food pantry volunteers with delivery tasks, and lets the pantry organization manage tasks and verify deliveries.

# GitHub Workflow
- Switch to main and pull the latest changes
- Create your own branch for your work
- Commit changes with a clear message
- Push your branch and open a pull request
- After it's reviewed, merge it into main

NEVER commit .env as it holds your keys!

# Tech Stack
- Python
- Flask 
- Supabase 
- python-dotenv 

# How to Get Set Up
Install VS Code: https://code.visualstudio.com/

Step 1: Create a virtual environment (recommended)
``` 
python -m venv venv
```
On macOS, use python3 if python is not working.

Step 2: Activate the virtual environment
```
On macOS/Linux: source venv/bin/activate
```
```
On Windows (PowerShell): venv\Scripts\Activate.ps1
```
```
On Windows (Command Prompt): venv\Scripts\activate.bat
```

If VS Code asks to use the virtual environment, choose "Yes". Install everything and run the code from inside it.

Step 3: Install python-dotenv
```
pip install python-dotenv
```

Step 4: Install Flask 
```
pip install flask
```

Step 5: Install Supabase
```
pip install supabase
```

Done! 

# How to Run
Run this in your terminal: python backend/main.py

Then open your browser and navigate to http://127.0.0.1:5050

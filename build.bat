call .venv\scripts\activate
pip install pyinstaller
pyinstaller --onefile --distpath . form.py

pip freeze > temp-requirements.txt
pip uninstall -y -r temp-requirements.txt
pip install -r requirements.txt
del temp-requirements.txt form.spec
rmdir /s /q build __pycache__
deactivate

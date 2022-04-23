## TO USE THE PROJECT:

### Download and install Anaconda. Checkmark both “Add to path” and “default”.

### Clone the project using:
git clone https://github.com/wolbek/Financial-Risk-Assessment.git

### Change your path to the project in cli:
cd .\Financial-Risk-Assessment\

### Inititalize conda in VS code:
conda init

### Create a conda virtual environment (named as 'venv' with python 3.8):
conda create -n venv python=3.8

### Activate conda environment:
conda activate venv

### Install mingw in environment:
conda install libpython m2w64-toolchain -c msys2

### Install requirements.txt using:
pip install -r requirements.txt

### Initialize database:  
.\run.bat init-db

### Create users:  
.\run.bat create-users

### Seed data (optional):   
.\run.bat seed-data

### Run the application:   
.\run.bat run

### In the browser open:
localhost:5000

### To login as existing user use one of the listed emails:

email:user1@gmail.com
password:user

email:user2@gmail.com
password:user
@echo off
echo Starting Carbon Credit Marketplace with Blockchain...
echo.

echo Step 1: Starting Hardhat blockchain node...
cd contracts
start "Hardhat Blockchain" cmd /k "npx hardhat node"

echo Waiting for blockchain to start...
timeout /t 10 /nobreak > nul

echo Step 2: Deploying smart contracts...
npx hardhat run scripts/deploy.js --network localhost

echo Step 3: Starting Django server...
cd ..
python manage.py runserver

pause
@echo off
:loop
curl -s -X POST http://localhost:5000/api/bluetooth/readings ^
  -H "Content-Type: application/json" ^
  -d "{\"anchor_id\":\"right-anchor\",\"average_rssi\":-50,\"signal_score\":83.33}" > nul

timeout /t 1 /nobreak > nul
goto loop

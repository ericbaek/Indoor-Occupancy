@echo off
:loop
curl -s -X POST http://localhost:5000/api/bluetooth/readings ^
  -H "Content-Type: application/json" ^
  -d "{\"anchor_id\":\"right-anchor\",\"average_rssi\":-70,\"signal_score\":50.0}" > nul

timeout /t 1 /nobreak > nul
goto loop
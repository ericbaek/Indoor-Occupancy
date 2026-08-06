@echo off
:loop
curl -s -X POST http://localhost:5000/api/bluetooth/readings ^
  -H "Content-Type: application/json" ^
  -d "{\"message_type\":\"bluetooth_rssi\",\"scanner_id\":\"anchor-left\",\"tag_id\":\"ROOM-TAG-01\",\"rssi\":-50}" > nul

timeout /t 1 /nobreak > nul
goto loop
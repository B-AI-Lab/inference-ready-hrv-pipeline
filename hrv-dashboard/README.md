# Neuroadaptive HRV State Monitor

Premium real-time React dashboard prototype for processed HRV state payloads.

This frontend does not calculate HRV metrics. It only visualizes
`HRVDashboardPayload` objects shaped like the future Python backend output.

## Run

```sh
cd hrv-dashboard
npm install
npm run dev
```

Then open the local Vite URL shown in the terminal.

## Live Stream

The single-subject dashboard hook uses:

```ts
useHRVStream()
```

It connects to the local bridge at `http://127.0.0.1:8765/stream` and keeps a
rolling 10-minute history for charts. If the bridge is not running yet, it
falls back to the mock stream.

Start the ESP32/AD8232 bridge from the repo root:

```sh
python3 -m pip install -r requirements-live.txt
python3 hrv_serial_sse_bridge.py --port /dev/ttyUSB0 --baud 115200
```

Hardware-free bridge test:

```sh
python3 hrv_serial_sse_bridge.py --simulate
```

Override the stream endpoint with `VITE_HRV_STREAM_URL`.

## Polar H10 Multi-Subject BLE Stream

The HRV tab now accepts multi-subject SSE events from:

```sh
python3 -m pip install -r ../requirements-live.txt
python3 ../hrv_ble_sse_bridge.py --max-devices 5
```

The BLE bridge scans for Polar H10 / BLE Heart Rate Service devices, connects
automatically, parses real RR intervals, and sends one `subject` event per belt.
The dashboard keeps the existing simulated subjects until the first live belt
payload arrives.

Hardware-free multi-belt test:

```sh
python3 ../hrv_ble_sse_bridge.py --simulate --max-devices 3
```

Override the multi-subject endpoint with `VITE_HRV_MULTI_STREAM_URL`.

## Scientific Wording

The UI intentionally uses cautious labels:

- Stress Score
- Recovery Score
- Autonomic Balance Index
- Respiration Proxy
- Signal Confidence
- Artifact Ratio
- PSD Readiness

It avoids diagnostic or overinterpreted labels and does not present LF/HF as
direct sympathetic activity or the respiration proxy as direct respiratory
measurement.

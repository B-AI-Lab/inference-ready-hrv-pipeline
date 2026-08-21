import asyncio

from bleak import BleakScanner


async def main() -> None:
    devices = await BleakScanner.discover(timeout=12, return_adv=True)
    items = devices.values() if isinstance(devices, dict) else devices
    for item in items:
        if isinstance(item, tuple) and len(item) == 2:
            device, adv = item
        else:
            device, adv = item, None
        name = getattr(device, "name", None) or (getattr(adv, "local_name", None) if adv else None) or "<no name>"
        address = getattr(device, "address", "?")
        services = getattr(adv, "service_uuids", []) if adv else []
        rssi = getattr(adv, "rssi", None) if adv else None
        print(f"{address} | {name} | rssi={rssi} | services={services}")


if __name__ == "__main__":
    asyncio.run(main())

import subprocess
import concurrent.futures
import ipaddress

def ping(ip):
    res = subprocess.run(["ping", "-n", "1", "-w", "250", str(ip)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode == 0 and b"TTL=" in res.stdout:
        return str(ip)
    return None

print("Scanning 192.168.205.1 - 254...")
active_ips = []
with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
    futures = [executor.submit(ping, f"192.168.205.{i}") for i in range(1, 255)]
    for f in concurrent.futures.as_completed(futures):
        ip = f.result()
        if ip:
            active_ips.append(ip)
            print(f"  Found active IP: {ip}")

print("Active IPs found:", sorted(active_ips))

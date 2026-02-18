#!/usr/bin/env python3
import requests
import time
import sys
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ========== KONFIGURASI ==========
ACCOUNT_ID = "15443982a1f5b02c113a96c5aa393517"
PROJECT_NAME = "govoetlive"
API_TOKEN = "z-dWlNPt5BrVlISn-W6RzBocnBEcjDFFKA-rCCJL"  # ← WAJIB GANTI!

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}
base_url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/pages/projects/{PROJECT_NAME}"

print("=" * 70)
print("  HAPUS CLOUDFLARE PAGES: CLEANUP + DELETE (ROBUST)")
print("=" * 70)
print(f"Project: {PROJECT_NAME}")
print("=" * 70)

# ========== SETUP SESSION DENGAN RETRY ==========
session = requests.Session()
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "OPTIONS", "DELETE"]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("http://", adapter)
session.mount("https://", adapter)

# ========== CEK PROJECT ==========
print("\n🔍 Memeriksa project...")
resp = session.get(base_url, headers=headers)
if resp.status_code != 200:
    print(f"❌ Project tidak ditemukan (HTTP {resp.status_code})")
    sys.exit(1)
print("✅ Project ditemukan")

# ========== HAPUS DEPLOYMENTS ==========
print("\n🔄 Menghapus deployments...")
deployments_url = f"{base_url}/deployments"

total_deleted = 0
batch = 1
max_failures = 5
consecutive_failures = 0

while consecutive_failures < max_failures:
    try:
        # Ambil deployments
        resp = session.get(deployments_url, headers=headers, timeout=30)
        
        if resp.status_code != 200:
            print(f"⚠️  Gagal ambil deployments (HTTP {resp.status_code})")
            consecutive_failures += 1
            time.sleep(3)
            continue
        
        data = resp.json()
        if not data.get("success"):
            errors = data.get("errors", [])
            print(f"⚠️  Error API: {errors}")
            consecutive_failures += 1
            time.sleep(3)
            continue
        
        deployments = data.get("result", [])
        count = len(deployments)
        
        if count == 0:
            print(f"\n✅ Tidak ada deployments tersisa")
            break
        
        # Simpan 1 terbaru, hapus sisanya
        to_delete = deployments[:-1] if count > 1 else deployments
        
        if not to_delete:
            print(f"\n✅ Hanya tersisa 1 deployment")
            break
        
        print(f"\n📦 Batch #{batch}: Menghapus {len(to_delete)} dari {count} deployments...")
        
        batch_deleted = 0
        batch_failed = 0
        
        for i, dep in enumerate(to_delete, 1):
            dep_id = dep["id"]
            alias = dep_id[:6] + "..." if len(dep_id) > 6 else dep_id
            
            try:
                # Hapus deployment dengan retry
                del_resp = session.delete(
                    f"{deployments_url}/{dep_id}", 
                    headers=headers, 
                    timeout=15
                )
                
                if del_resp.status_code == 200:
                    batch_deleted += 1
                    consecutive_failures = 0  # Reset failure counter
                else:
                    batch_failed += 1
                    consecutive_failures += 1
                
                status = "✓" if del_resp.status_code == 200 else "✗"
                print(f"  [{i}/{len(to_delete)}] {alias} {status}", end="\r")
                
            except Exception as e:
                batch_failed += 1
                consecutive_failures += 1
                print(f"  [{i}/{len(to_delete)}] {alias} ✗ (error)", end="\r")
            
            time.sleep(0.3)  # Delay antar hapus
        
        total_deleted += batch_deleted
        print(f"\n  ✅ Batch #{batch} selesai | Hapus: {batch_deleted} | Gagal: {batch_failed} | Total: {total_deleted}")
        
        batch += 1
        consecutive_failures = 0  # Reset setelah batch berhasil
        time.sleep(2)  # Delay lebih lama antar batch
    
    except Exception as e:
        print(f"\n⚠️  Error: {e}")
        consecutive_failures += 1
        time.sleep(5)

if consecutive_failures >= max_failures:
    print(f"\n⚠️  Terlalu banyak kegagalan berturut-turut. Coba lagi nanti.")
    print(f"   Total berhasil dihapus: {total_deleted}")
else:
    print(f"\n✅ Semua deployments berhasil dihapus! Total: {total_deleted}")

# ========== HAPUS PROJECT ==========
print("\n" + "=" * 70)
print("🔥 Menghapus project...")
print("=" * 70)

confirm = input("\nKetik 'DELETE' untuk konfirmasi: ")
if confirm.strip() != "DELETE":
    print("\n❌ Dibatalkan")
    sys.exit(0)

try:
    delete_resp = session.delete(base_url, headers=headers, timeout=30)
    
    print("\n" + "=" * 70)
    if delete_resp.status_code == 200:
        print(f"✅✅✅ BERHASIL! Project '{PROJECT_NAME}' telah dihapus!")
        print("\n🔒 LANGKAH WAJIB:")
        print("   1. HAPUS SCRIPT: del delete_govoet_final.py")
        print("   2. REVOKE TOKEN: https://dash.cloudflare.com/profile/api-tokens")
    else:
        print(f"❌ GAGAL hapus project (HTTP {delete_resp.status_code})")
        try:
            print("Error:", delete_resp.json().get("errors"))
        except:
            print("Response:", delete_resp.text)
except Exception as e:
    print(f"\n❌ Error: {e}")
    print("💡 Coba jalankan script ini lagi")

print("=" * 70)
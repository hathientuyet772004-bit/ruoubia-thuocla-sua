import subprocess
import time
import webbrowser
import os
import sys
from pathlib import Path

def run():
    print("🚀 Khởi động Admin Center (Centralized Management System)...")
    
    # Paths
    base_dir = Path(__file__).parent
    backend_dir = base_dir / "backend"
    frontend_dir = base_dir / "frontend"
    project_root = base_dir.parent.parent.parent
    
    processes = []
    try:
        # 1. Start Backend
        print("📡 Đang chạy API Backend (port 8000)...")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(project_root / "src") + os.pathsep + env.get("PYTHONPATH", "")
        
        backend_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"],
            cwd=str(backend_dir),
            env=env
        )
        processes.append(backend_proc)
        
        # 2. Start Frontend
        print("🎨 Đang chạy React Frontend (port 3000)...")
        frontend_proc = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=str(frontend_dir),
            shell=True
        )
        processes.append(frontend_proc)
        
        # Wait for services
        time.sleep(5)
        
        url = "http://localhost:3000"
        print(f"✅ Admin Center đã sẵn sàng: {url}")
        webbrowser.open(url)
        
        while True:
            time.sleep(1)
            if backend_proc.poll() is not None:
                print("❌ Backend error.")
                break
            if frontend_proc.poll() is not None:
                print("❌ Frontend error.")
                break
                
    except KeyboardInterrupt:
        print("\n🛑 Shutdown Admin Center...")
    finally:
        for p in processes:
            p.terminate()

if __name__ == "__main__":
    run()

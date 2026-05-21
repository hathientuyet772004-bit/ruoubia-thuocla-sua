import subprocess
import time
import webbrowser
import os
import sys

def run():
    print("🚀 Đang khởi động Web Collector Tool...")
    
    # Path to current directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(base_dir, "backend")
    frontend_dir = os.path.join(base_dir, "frontend")
    
    # Check if node_modules exists
    if not os.path.exists(os.path.join(frontend_dir, "node_modules")):
        print("📦 Chưa cài đặt dependencies cho frontend. Vui lòng đợi...")
        # npm install takes time
        
    processes = []
    try:
        # 1. Start Backend
        print("📡 Đang chạy backend (port 8080)...")
        # Ensure src/ is in Python path (imports: shared.*, modules.*)
        project_root = os.path.abspath(os.path.join(base_dir, "..", "..", ".."))
        src_dir = os.path.join(project_root, "src")
        env = os.environ.copy()
        env["PYTHONPATH"] = src_dir + os.pathsep + env.get("PYTHONPATH", "")
        
        backend_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--loop", "asyncio"],
            cwd=backend_dir,
            env=env
        )
        processes.append(backend_proc)
        
        # 2. Start Frontend
        print("🎨 Đang chạy frontend (port 3000)...")
        frontend_proc = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=frontend_dir,
            shell=True
        )
        processes.append(frontend_proc)
        
        # Wait for services to start
        time.sleep(5)
        
        url = "http://localhost:3000"
        print(f"✅ Đã sẵn sàng! Đang mở trình duyệt tại: {url}")
        webbrowser.open(url)
        
        # Keep the script running
        while True:
            time.sleep(1)
            if backend_proc.poll() is not None:
                print("❌ Backend đã dừng.")
                break
            if frontend_proc.poll() is not None:
                print("❌ Frontend đã dừng.")
                break
                
    except KeyboardInterrupt:
        print("\n🛑 Đang đóng mọi thứ...")
    finally:
        for p in processes:
            p.terminate()
            p.kill()

if __name__ == "__main__":
    run()

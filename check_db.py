import sys
from pathlib import Path
project_root = Path(r"d:\datasets\ruoubia-thuocla-sua")
sys.path.append(str(project_root / "src"))
sys.path.append(str(project_root / "src" / "modules" / "collector" / "backend"))

from db.database import SessionLocal
from models.orm import Source

db = SessionLocal()
sources = db.query(Source).all()
print(f"Total Sources in DB: {len(sources)}")
for s in sources[:5]:
    print(f"- {s.name}: {s.url}")
db.close()

import codecs

prepend="""import React, { useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import {
  AlertTriangle,
  Boxes,
  ChevronRight,
  Check,
  Download,
  FileSearch,
  Globe,
  LayoutGrid,
  List,
  MapPin,
  Plus,
  Play,
  RefreshCw,
  Search,
  Sparkles,
  ShieldAlert,
  Table2,
  X,
  Upload,
  MoreVertical,
  Activity,
  CalendarClock
} from 'lucide-react';
"""

text = codecs.open('src/apps/admin_center/frontend/src/pages/adminRoutes.jsx', 'r', encoding='utf-8').read()
text = text.replace('\ufeff', '')

if 'import React' not in text:
    codecs.open('src/apps/admin_center/frontend/src/pages/adminRoutes.jsx', 'w', encoding='utf-8').write(prepend + text)

"""Smart Crawler — Adaptive AI-powered crawling system.

Architecture:
  Input URL → DomainAnalyzer → Strategy Decision
    ├── DIRECT: StructureGenerator → TemplateCrawler
    └── MHTML:  Collector (manual) → MHTMLDecoder → StructureGenerator → TemplateCrawler
"""
